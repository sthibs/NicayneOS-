"""
Flask web application for BOL PDF upload and processing.
Provides a simple interface for uploading PDFs and processing them through the BOL extractor.
"""

import os
import logging
import time
import queue
import json
import base64
import re
from datetime import datetime, date, timedelta
from flask import Flask, request, render_template, jsonify, flash, redirect, url_for, send_file, Response, stream_with_context
from werkzeug.utils import secure_filename
from bol_extractor.extractor import BOLExtractor
from bol_extractor.config import Config
from utils.prompt_loader import PromptLoader
from drive_utils import DriveUploader
from email_utils import send_email_with_attachment
import gspread
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    """Load system configuration from config.json."""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except:
        return {"max_pages": 100, "enable_backup": True, "processing_timeout": 300, "batch_size": 50}

def save_config(config):
    """Save system configuration to config.json."""
    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)

# Global log queue for live streaming
log_queue = queue.Queue()

def live_log(msg):
    """Send log message to both console and live stream."""
    print("[LOG]", msg)  # Console output
    try:
        log_queue.put(msg, block=False)  # Non-blocking put
    except queue.Full:
        pass  # Skip if queue is full

def log_info(msg): 
    live_log(f"[INFO] {msg}")

def log_warning(msg): 
    live_log(f"[WARNING] {msg}")

def log_error(msg): 
    live_log(f"[ERROR] {msg}")

def send_document_email(pdf_path, document_type, customer_name, to_email=None):
    """Helper function to send document emails with PDF attachments"""
    try:
        # Check if email sending is requested
        if not to_email:
            return None
            
        # Default email addresses
        default_email = os.environ.get('DEFAULT_SEND_TO_EMAIL', 'admin@caios.app')
        recipient = to_email if to_email != 'auto' else default_email
        
        # Create email content based on document type
        subject_map = {
            'work_order': f'Work Order - {customer_name}',
            'finished_tag': f'Finished Tag - {customer_name}',
            'bol': f'Bill of Lading - {customer_name}',
            'invoice': f'Invoice - {customer_name}'
        }
        
        body_map = {
            'work_order': f'Please find attached the work order for {customer_name}.',
            'finished_tag': f'Please find attached the finished tag for {customer_name}.',
            'bol': f'Please find attached the bill of lading for {customer_name}.',
            'invoice': f'Please find attached the invoice for {customer_name}.'
        }
        
        subject = subject_map.get(document_type, f'Document - {customer_name}')
        body = body_map.get(document_type, f'Please find attached the document for {customer_name}.')
        
        # Send email
        result = send_email_with_attachment(
            to_email=recipient,
            subject=subject,
            body=body,
            attachment_path=pdf_path,
            filename=os.path.basename(pdf_path)
        )
        
        if result.get('success'):
            log_info(f"Email sent to {recipient} with {document_type}")
            return result
        else:
            log_warning(f"Email send failed: {result.get('error', 'Unknown error')}")
            return result
            
    except Exception as e:
        log_error(f"Email sending error: {str(e)}")
        return {'success': False, 'error': str(e)}

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html'), 200, {'Cache-Control': 'no-cache, no-store, must-revalidate'}

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle PDF file upload and processing."""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    # Get supplier name from form data (defaults to 'default')
    supplier_name = request.form.get('supplier', 'default')
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename or "unknown.pdf")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Initialize BOL extractor
            config = Config()
            extractor = BOLExtractor(config)
            
            # Track processing time
            start_time = time.time()
            
            # Process the PDF with supplier-specific processing
            log_info(f"Processing BOL PDF: {filename} for supplier: {supplier_name}")
            logger.info(f"Processing BOL PDF: {filename} for supplier: {supplier_name}")
            result = extractor.process_bol_pdf_with_supplier(filepath, supplier_name)
            
            # Calculate processing time
            processing_time = round(time.time() - start_time, 2)
            
            # Clean up uploaded file
            os.remove(filepath)
            
            if result['success']:
                coils_count = result.get('coils_processed', 1)
                log_info(f"✅ Successfully processed {coils_count} coils in {processing_time}s")
                flash(f'Successfully processed {coils_count} coils and added to spreadsheet!')
                
                # Store summary data for potential summary page
                summary_data = {
                    'status': 'Success',
                    'pages_processed': result.get('pages_processed', 1),
                    'coils_extracted': coils_count,
                    'time_taken': f"{processing_time}s",
                    'failed_pages': result.get('failed_pages', []),
                    'backup_created': result.get('backup_created', False),
                    'count_validation': result.get('count_validation', True),
                    'errors': [],
                    'backup_path': None,
                    'backup_filename': None
                }
                
                # Add to job history
                history_entry = {
                    "filename": filename,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "pages": result.get('pages_processed', 1),
                    "coils": coils_count,
                    "processing_time": f"{processing_time}s",
                    "status": "✅ Success",
                    "errors": [],
                    "backup": None
                }
                
                try:
                    with open("job_history.json", "r") as f:
                        history = json.load(f)
                except:
                    history = []
                
                history.insert(0, history_entry)  # newest first
                with open("job_history.json", "w") as f:
                    json.dump(history, f, indent=2)
                
                return jsonify({
                    'success': True,
                    'message': f'Successfully processed {coils_count} coils',
                    'coils_processed': coils_count,
                    'supplier': supplier_name,
                    'pages_processed': result.get('pages_processed', 1),
                    'summary': summary_data,
                    'report_data': result  # Include full report for optional viewing
                })
            else:
                flash(f'Error processing BOL: {result["error"]}')
                return jsonify({
                    'success': False,
                    'error': result['error']
                })
                
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            flash(f'Error processing file: {str(e)}')
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    flash('Invalid file type. Please upload a PDF file.')
    return redirect(request.url)

@app.route('/health')
def health_check():
    """Health check endpoint - returns JSON for API calls."""
    try:
        config = Config()
        # Test Google Sheets connection
        from bol_extractor.google_sheets_writer import GoogleSheetsWriter
        sheets_writer = GoogleSheetsWriter(config)
        sheets_writer.verify_connection()
        
        return jsonify({
            'status': 'healthy',
            'google_sheets': 'connected',
            'openai_api': 'configured' if config.openai_api_key else 'not configured'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/health-status')
def health_status_page():
    """Health status page - returns HTML for browser access."""
    try:
        config = Config()
        # Test Google Sheets connection
        from bol_extractor.google_sheets_writer import GoogleSheetsWriter
        sheets_writer = GoogleSheetsWriter(config)
        sheets_writer.verify_connection()
        
        health_data = {
            'status': 'healthy',
            'google_sheets': 'connected',
            'openai_api': 'configured' if config.openai_api_key else 'not configured'
        }
        
        return render_template('health.html', health=health_data)
        
    except Exception as e:
        error_data = {
            'status': 'unhealthy',
            'error': str(e)
        }
        
        return render_template('health.html', health=error_data), 500

@app.route('/suppliers', methods=['GET'])
def get_suppliers():
    """Get all active suppliers."""
    try:
        prompt_loader = PromptLoader()
        suppliers = prompt_loader.get_all_suppliers()
        return jsonify({
            'success': True,
            'suppliers': suppliers
        })
    except Exception as e:
        logger.error(f"Error getting suppliers: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/suppliers', methods=['POST'])
def add_supplier():
    """Add a new supplier with custom prompt."""
    try:
        data = request.get_json()
        supplier_name = data.get('supplier_name')
        display_name = data.get('display_name')
        prompt = data.get('prompt')
        
        if not supplier_name or not prompt:
            return jsonify({
                'success': False,
                'error': 'Supplier name and prompt are required'
            }), 400
        
        prompt_loader = PromptLoader()
        success = prompt_loader.add_supplier(supplier_name, prompt, display_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Supplier added successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add supplier'
            }), 500
            
    except Exception as e:
        logger.error(f"Error adding supplier: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/suppliers/<supplier_name>', methods=['PUT'])
def update_supplier_prompt(supplier_name):
    """Update supplier prompt."""
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({
                'success': False,
                'error': 'Prompt is required'
            }), 400
        
        prompt_loader = PromptLoader()
        success = prompt_loader.update_supplier_prompt(supplier_name, prompt)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Supplier prompt updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update supplier prompt'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating supplier: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/suppliers/<supplier_name>/prompt', methods=['PUT'])
def update_supplier_prompt_specific(supplier_name):
    """Update supplier prompt via specific endpoint."""
    try:
        data = request.get_json()
        prompt = data.get('prompt')
        
        if not prompt:
            return jsonify({
                'success': False,
                'error': 'Prompt is required'
            }), 400
        
        prompt_loader = PromptLoader()
        success = prompt_loader.update_supplier_prompt(supplier_name, prompt)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Supplier prompt updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update supplier prompt'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating supplier prompt: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/suppliers/<supplier_name>', methods=['DELETE'])
def remove_supplier(supplier_name):
    """Remove a supplier."""
    try:
        prompt_loader = PromptLoader()
        success = prompt_loader.remove_supplier(supplier_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Supplier removed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to remove supplier'
            }), 500
            
    except Exception as e:
        logger.error(f"Error removing supplier: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/test')
def test_endpoint():
    """Test endpoint for running the test suite."""
    try:
        from bol_extractor.test_bol_extractor import run_tests
        results = run_tests()
        return jsonify(results)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/stream")
def stream_logs():
    """Stream live logs using Server-Sent Events."""
    def generate():
        while True:
            try:
                msg = log_queue.get(timeout=30)  # 30 second timeout
                yield f"data: {msg}\n\n"
            except queue.Empty:
                # Send heartbeat to keep connection alive
                yield f"data: [HEARTBEAT]\n\n"
    
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

@app.route("/history")
def history():
    """Display job history page."""
    try:
        with open("job_history.json", "r") as f:
            job_list = json.load(f)
    except:
        job_list = []
    return render_template("history.html", jobs=job_list)

@app.route('/summary')
def show_summary():
    """Display extraction summary page."""
    # Get summary data from session or query parameters
    summary_data = request.args.to_dict()
    
    if not summary_data:
        # Default summary if no data provided
        summary_data = {
            'status': 'No data available',
            'pages_processed': 0,
            'coils_extracted': 0,
            'time_taken': '0s',
            'failed_pages': [],
            'backup_created': False,
            'count_validation': False,
            'errors': ['No extraction data found'],
            'backup_path': None,
            'backup_filename': None
        }
    
    return render_template('summary.html', summary=summary_data)

@app.route("/control", methods=["GET", "POST"])
def control_panel():
    """Admin control panel for system settings."""
    config = load_config()
    message = None
    
    if request.method == "POST":
        try:
            config["max_pages"] = int(request.form.get("max_pages", config["max_pages"]))
            config["enable_backup"] = True if request.form.get("enable_backup") == "on" else False
            config["processing_timeout"] = int(request.form.get("processing_timeout", config.get("processing_timeout", 300)))
            config["batch_size"] = int(request.form.get("batch_size", config.get("batch_size", 50)))
            
            save_config(config)
            message = "✅ Settings updated successfully!"
        except Exception as e:
            message = f"❌ Failed to update settings: {str(e)}"
    
    return render_template("control.html", config=config, message=message)

@app.route("/work-order-form", methods=["GET", "POST"])
def work_order_form():
    """Work order form for creating manufacturing orders."""
    if request.method == "POST":
        # Generate work order number
        work_order_number = f"WO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Collect all form data including dynamic job entries
        form_data_raw = request.form.to_dict(flat=False)
        
        # Process basic form data
        form_data = {
            'work_order_number': work_order_number,
            'quote_number': request.form.get('quote_number', ''),
            'customer_name': request.form.get('customer_name', ''),
            'customer_po': request.form.get('customer_po', ''),
            'date_required': request.form.get('date_required', ''),
            'date_created': date.today().strftime('%Y-%m-%d'),
            'tolerance': request.form.get('tolerance', ''),
            'notes': request.form.get('notes', ''),
            'max_skid_weight': request.form.get('max_skid_weight', ''),
            'pieces_per_skid': request.form.get('pieces_per_skid', ''),
            'max_od': request.form.get('max_od', ''),
            'wood_spacers': 'wood_spacers' in request.form,
            'paper_wrapped': 'paper_wrapped' in request.form,
            'coil_direction': request.form.get('coil_direction', ''),
            'split_coil': 'split_coil' in request.form,
            'process_type': request.form.get('process_type', ''),
            'ctl_jobs': [],
            'slitting_jobs': []
        }
        
        # Process Cut to Length jobs
        ctl_indices = set()
        for key in form_data_raw.keys():
            if key.startswith('ctl_') and '_' in key:
                try:
                    index = int(key.split('_')[-1])
                    ctl_indices.add(index)
                except ValueError:
                    pass
        
        for index in sorted(ctl_indices):
            ctl_job = {
                'job_number': index + 1,
                'material_grade': request.form.get(f'ctl_grade_{index}', ''),
                'material_description': request.form.get(f'ctl_description_{index}', ''),
                'incoming_coils': request.form.get(f'ctl_incoming_{index}', ''),
                'incoming_weight': request.form.get(f'ctl_weight_in_{index}', ''),
                'finished_pieces': request.form.get(f'ctl_pieces_out_{index}', ''),
                'finished_weight': request.form.get(f'ctl_weight_out_{index}', ''),
                'pack_instructions': request.form.get(f'ctl_pack_{index}', ''),
                'customer_tags': request.form.get(f'ctl_tags_{index}', '')
            }
            form_data['ctl_jobs'].append(ctl_job)
        
        # Process Slitting jobs
        slit_indices = set()
        for key in form_data_raw.keys():
            if key.startswith('slit_') and '_' in key:
                try:
                    index = int(key.split('_')[-1])
                    slit_indices.add(index)
                except ValueError:
                    pass
        
        for index in sorted(slit_indices):
            slit_job = {
                'job_number': index + 1,
                'material_grade': request.form.get(f'slit_grade_{index}', ''),
                'coil_description': request.form.get(f'slit_description_{index}', ''),
                'slitter_setup': request.form.get(f'slit_setup_{index}', ''),
                'pack_instructions': request.form.get(f'slit_pack_{index}', ''),
                'customer_tags': request.form.get(f'slit_tags_{index}', '')
            }
            form_data['slitting_jobs'].append(slit_job)
        
        # Save work order data
        try:
            # Create Google Drive folder structure for this work order
            folder_path = create_customer_folder_structure(form_data)
            
            # Update master list
            try:
                with open("work_orders.json", "r") as f:
                    work_orders = json.load(f)
            except:
                work_orders = []
            
            work_orders.insert(0, form_data)  # newest first
            with open("work_orders.json", "w") as f:
                json.dump(work_orders, f, indent=2)
            
            # Generate PDF
            logger.info("Starting PDF generation...")
            pdf_path = generate_work_order_pdf(form_data)
            logger.info(f"PDF generated at: {pdf_path}")
            
            # Process inventory matching and validation first
            logger.info("Processing inventory matching...")
            result = match_tags_and_move_to_in_processed(form_data)
            if isinstance(result, tuple) and len(result) == 3:
                matched_count, matched_tags, unmatched_tags = result
            else:
                matched_count, matched_tags, unmatched_tags = 0, [], []
            logger.info(f"Inventory matching complete: {matched_count} matched")
            
            # Check for unmatched tags and require confirmation
            if unmatched_tags and not request.form.get("force_submit"):
                logger.info(f"Unmatched tags found: {unmatched_tags}")
                flash(f'Warning: These tags were not found in inventory: {", ".join(unmatched_tags)}', 'warning')
                return render_template('work_order_form.html', 
                                     date=datetime.now().strftime("%Y-%m-%d"),
                                     form_data=form_data,
                                     unmatched_tags=unmatched_tags)
            
            # Folder structure already created above
            
            # Save to Google Sheets
            logger.info("Saving to Google Sheets...")
            save_work_order_to_sheet(form_data)
            logger.info("Google Sheets save complete")
            
            # Upload PDF to Google Drive and get shareable link
            logger.info("Uploading PDF to Google Drive...")
            drive_url = None
            try:
                from drive_utils import DriveUploader
                uploader = DriveUploader()
                upload_result = uploader.upload_work_order_pdf(pdf_path, form_data['customer_name'], form_data['customer_po'])
                if upload_result.get('upload_success'):
                    drive_url = upload_result.get('file_link')
                    logger.info(f"PDF uploaded to Drive: {upload_result.get('folder_path')}")
                    logger.info(f"Drive share URL: {drive_url}")
                else:
                    logger.warning(f"Drive upload failed: {upload_result.get('error')}")
            except Exception as e:
                logger.warning(f"Drive upload error: {str(e)}")
            
            # Regenerate PDF with QR code if Drive URL is available
            if drive_url:
                logger.info("Regenerating PDF with QR code...")
                try:
                    from generate_work_order_pdf import generate_work_order_pdf_from_form_data
                    pdf_path_with_qr = generate_work_order_pdf_from_form_data(form_data, drive_url)
                    
                    # Replace the original PDF with QR-enabled version
                    if pdf_path_with_qr and os.path.exists(pdf_path_with_qr):
                        # Re-upload the QR-enabled PDF to replace the original
                        upload_result = uploader.upload_work_order_pdf(pdf_path_with_qr, form_data['customer_name'], form_data['customer_po'])
                        if upload_result.get('upload_success'):
                            logger.info("PDF with QR code uploaded successfully")
                            pdf_path = pdf_path_with_qr  # Use the QR-enabled version for local download
                        else:
                            logger.warning("Failed to upload QR-enabled PDF, keeping original")
                except Exception as e:
                    logger.warning(f"Error generating PDF with QR code: {str(e)}")
            else:
                logger.info("No Drive URL available, PDF generated without QR code")
            
            if matched_count > 0:
                logger.info(f"Matched and processed {matched_count} coils for work order {work_order_number}")
            
            # Verify PDF exists before sending
            if not os.path.exists(pdf_path):
                logger.error(f"PDF not found at expected path: {pdf_path}")
                flash("PDF generation failed", "error")
                return redirect(url_for('work_order_form'))
            
            # Optional email sending
            send_email = request.form.get('send_email')
            to_email = request.form.get('to_email')
            if send_email and send_email.lower() in ['true', '1', 'yes', 'on']:
                email_result = send_document_email(
                    pdf_path=pdf_path,
                    document_type='work_order',
                    customer_name=form_data['customer_name'],
                    to_email=to_email
                )
                if email_result and email_result.get('success'):
                    flash(f"Work order emailed to {email_result.get('recipient')}", "success")
                elif email_result:
                    flash(f"Email failed: {email_result.get('error')}", "warning")
            
            # Instead of direct download, redirect to success page with download link
            logger.info(f"Work order {work_order_number} processed successfully")
            flash(f"Work order {work_order_number} created successfully!", "success")
            return render_template('work_order_success.html', 
                                 work_order_number=work_order_number,
                                 download_url=url_for('download_work_order_pdf', work_order_number=work_order_number))
            
        except Exception as e:
            flash(f'Error processing work order: {str(e)}', 'error')
            return redirect(url_for('work_order_form'))
    
    # Check if test data should be pre-filled
    test_data = None
    if request.args.get('test') == 'true':
        test_data = {
            'quote_number': '12345',
            'customer_name': 'samuel',
            'customer_po': '23456',
            'date_required': '2025-06-06',
            'max_skid_weight': '5000',
            'pieces_per_skid': '50',
            'max_od': '72',
            'notes': 'this is a test',
            'process_type': 'both',
            'tolerance': '+/- 0.005',
            'wood_spacers': True,
            'paper_wrapped': True,
            'coil_direction': 'ID_OUT',
            'split_coil': True,
            'ctl_jobs': [
                {
                    'job_number': 1,
                    'material_grade': 'A36',
                    'thickness': '0.250',
                    'width': '6.00',
                    'length': '240',
                    'pieces': '25',
                    'tolerance': '+/- 0.005',
                    'customer_tags': 'CTL-001, CTL-002, CTL-003'
                },
                {
                    'job_number': 2,
                    'material_grade': '1018',
                    'thickness': '0.125',
                    'width': '4.50',
                    'length': '120',
                    'pieces': '50',
                    'tolerance': '+/- 0.003',
                    'customer_tags': 'CTL-004, CTL-005'
                }
            ],
            'slitting_jobs': [
                {
                    'job_number': 1,
                    'material_grade': 'A36',
                    'coil_description': '0.500 x 12.00 x COIL',
                    'slitter_setup': '3.00, 3.00, 3.00, 3.00',
                    'pack_instructions': 'Bundle with steel strapping',
                    'customer_tags': 'SLT-001, SLT-002'
                },
                {
                    'job_number': 2,
                    'material_grade': '1008',
                    'coil_description': '0.375 x 8.00 x COIL',
                    'slitter_setup': '2.00, 2.00, 2.00, 2.00',
                    'pack_instructions': 'Wrap individually',
                    'customer_tags': 'SLT-003, SLT-004, SLT-005'
                }
            ]
        }
    
    return render_template("work_order_form.html", 
                         date=date.today().strftime('%Y-%m-%d'),
                         form_data=test_data)

def generate_work_order_pdf(data):
    """Generate a PDF work order document using the new professional design."""
    from generate_work_order_pdf import generate_work_order_pdf_from_form_data
    
    return generate_work_order_pdf_from_form_data(data)

def save_work_order_to_sheet(data):
    """Save work order to Google Sheets."""
    try:
        from bol_extractor.config import Config
        config = Config()
        
        if not config.spreadsheet_id:
            logger.warning("No spreadsheet ID configured for work orders")
            return
        
        import gspread
        from google.oauth2.service_account import Credentials
        
        # Use existing credentials from BOL extractor
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(
            json.loads(config.google_service_account_key), scopes=SCOPES
        )
        
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(config.spreadsheet_id)
        
        # Try to get work_orders worksheet, create if not exists
        try:
            ws = sheet.worksheet("work_orders")
        except gspread.exceptions.WorksheetNotFound:
            ws = sheet.add_worksheet(title="work_orders", rows=1000, cols=20)
        
        # Flatten data for sheet writing
        flat_data = {
            'work_order_number': data.get('work_order_number', ''),
            'customer_name': data.get('customer_name', ''),
            'quote_number': data.get('quote_number', ''),
            'customer_po': data.get('customer_po', ''),
            'date_created': data.get('date_created', ''),
            'date_required': data.get('date_required', ''),
            'process_type': data.get('process_type', ''),
            'tolerance': data.get('tolerance', ''),
            'max_skid_weight': data.get('max_skid_weight', ''),
            'pieces_per_skid': data.get('pieces_per_skid', ''),
            'max_od': data.get('max_od', ''),
            'wood_spacers': 'Yes' if data.get('wood_spacers') else 'No',
            'paper_wrapped': 'Yes' if data.get('paper_wrapped') else 'No',
            'coil_direction': data.get('coil_direction', ''),
            'split_coil': 'Yes' if data.get('split_coil') else 'No',
            'ctl_jobs_count': len(data.get('ctl_jobs', [])),
            'slitting_jobs_count': len(data.get('slitting_jobs', [])),
            'notes': data.get('notes', '')
        }
        
        # Write headers if sheet is empty
        if not ws.get_all_values():
            ws.append_row(list(flat_data.keys()))
        
        # Write data
        ws.append_row(list(flat_data.values()))
        logger.info(f"Work order {data.get('work_order_number')} saved to Google Sheets")
        
    except Exception as e:
        logger.error(f"Error saving work order to sheets: {str(e)}")

def match_tags_and_move_to_in_processed(form_data):
    """
    Match customer tags from work order with unprocessed inventory,
    update PO numbers, and move matched rows to in-processed sheet.
    Returns tuple: (matched_count, matched_tags, unmatched_tags)
    """
    try:
        # Collect all customer tags from all job types
        all_tags = []
        
        # Get tags from Cut to Length jobs
        for job in form_data.get('ctl_jobs', []):
            tags = job.get('customer_tags', '')
            if tags:
                all_tags.extend([t.strip().upper() for t in tags.split(',')])
        
        # Get tags from Slitting jobs
        for job in form_data.get('slitting_jobs', []):
            tags = job.get('customer_tags', '')
            if tags:
                all_tags.extend([t.strip().upper() for t in tags.split(',')])
        
        # Remove duplicates and empty tags
        all_tags = list(set([tag for tag in all_tags if tag]))
        
        po_number = form_data.get('customer_po')
        customer_name = form_data.get('customer_name')
        
        if not all_tags or not po_number:
            logger.info("No customer tags or PO number found for inventory matching")
            return 0, [], []
        
        logger.info(f"Searching for coil tags: {all_tags}")
        
        # Setup Google Sheets connection
        from bol_extractor.config import Config
        config = Config()
        
        import gspread
        from google.oauth2.service_account import Credentials
        
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(
            json.loads(config.google_service_account_key), scopes=SCOPES
        )
        
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(config.spreadsheet_id)
        
        # Get unprocessed inventory worksheet
        unprocessed = sheet.worksheet("UNPROCESSED_INVENTORY")
        
        # Get or create in-process worksheet
        try:
            in_processed = sheet.worksheet("IN_PROCESS")
        except gspread.exceptions.WorksheetNotFound:
            in_processed = sheet.add_worksheet(title="IN_PROCESS", rows=1000, cols=20)
            # Copy headers from unprocessed to in-processed
            headers = unprocessed.row_values(1)
            if headers:
                in_processed.append_row(headers)
        
        # Get all data from unprocessed sheet
        all_data = unprocessed.get_all_records()
        headers = unprocessed.row_values(1)
        
        if not headers:
            logger.warning("No headers found in UNPROCESSED_INVENTORY sheet")
            return 0
        
        # Find Customer PO column index
        try:
            po_col_index = headers.index("Customer PO") + 1  # gspread uses 1-based indexing
        except ValueError:
            # Try alternative column names
            po_col_names = ["Customer_PO", "CustomerPO", "PO", "PO Number"]
            po_col_index = None
            for col_name in po_col_names:
                try:
                    po_col_index = headers.index(col_name) + 1
                    break
                except ValueError:
                    continue
            
            if po_col_index is None:
                logger.warning("Could not find Customer PO column in sheet")
                return 0
        
        # Find Coil Tag column
        try:
            tag_col_name = None
            tag_col_names = ["COIL_TAG#", "Coil Tag", "CoilTag", "Coil_Tag", "Tag", "Heat Number"]
            for col_name in tag_col_names:
                if col_name in headers:
                    tag_col_name = col_name
                    break
            
            if not tag_col_name:
                logger.warning("Could not find Coil Tag column in sheet")
                return 0
            
        except Exception as e:
            logger.error(f"Error finding tag column: {str(e)}")
            return 0
        
        matched_rows = []
        matched_tags = []
        unmatched_tags = []
        
        # Check each tag for matches in inventory
        for tag in all_tags:
            found = False
            for idx, row in enumerate(all_data, start=2):  # start=2 to account for header row
                coil_tag = str(row.get(tag_col_name, "")).upper().strip()
                
                if coil_tag == tag:
                    logger.info(f"Found matching coil tag: {coil_tag}")
                    found = True
                    matched_tags.append(tag)
                    
                    # Update PO in unprocessed sheet
                    unprocessed.update_cell(idx, po_col_index, po_number)
                    
                    # Prepare row for copying to in-process
                    row_values = []
                    for header in headers:
                        value = row.get(header, "")
                        # Update the PO value in the row data
                        if header in ["Customer PO", "Customer_PO", "CustomerPO", "PO", "PO Number", "CUSTOMER_PO"]:
                            value = po_number
                        row_values.append(value)
                    
                    matched_rows.append(row_values)
                    break
            
            if not found:
                unmatched_tags.append(tag)
        
        # Copy matched rows to in-process sheet
        for row in matched_rows:
            in_processed.append_row(row)
        
        # Create customer folder structure
        if matched_rows:
            create_customer_folder_structure(form_data)
        
        logger.info(f"Successfully matched {len(matched_rows)} coils and moved to IN_PROCESS")
        if unmatched_tags:
            logger.warning(f"Unmatched tags: {unmatched_tags}")
        
        return len(matched_rows), matched_tags, unmatched_tags
        
    except Exception as e:
        logger.error(f"Error in inventory matching: {str(e)}")
        return 0, [], []

def create_customer_folder_structure(form_data):
    """Create organized folder structure for customer work orders in both local storage and Google Drive."""
    try:
        po = form_data.get('customer_po', 'NO_PO')
        customer = form_data.get('customer_name', 'UNKNOWN_CUSTOMER')
        work_order_number = form_data.get('work_order_number', 'UNKNOWN_WO')
        
        # Clean up names for filesystem
        po_clean = "".join(c for c in po if c.isalnum() or c in ('-', '_')).strip()
        customer_clean = "".join(c for c in customer if c.isalnum() or c in ('-', '_', ' ')).strip()
        
        # Create local folder structure
        base_path = f"work_orders/{customer_clean}/{po_clean}"
        os.makedirs(base_path, exist_ok=True)
        logger.info(f"Created local folder structure: {base_path}")
        
        # Save work order JSON to customer/PO folder
        json_filename = f"{work_order_number}.json"
        json_path = os.path.join(base_path, json_filename)
        
        with open(json_path, 'w') as f:
            json.dump(form_data, f, indent=2)
        
        logger.info(f"Work order saved to: {json_path}")
        
        # Create Google Drive folder structure
        try:
            from drive_utils import DriveUploader
            drive_uploader = DriveUploader()
            
            if drive_uploader.service:
                logger.info(f"Creating Google Drive folder structure for {customer}, PO: {po}")
                folder_result = drive_uploader.create_po_folder_structure(customer, po)
                
                if folder_result:
                    logger.info(f"Successfully created Google Drive folders: {folder_result['full_path']}")
                    logger.info(f"Subfolders created: {list(folder_result['subfolders'].keys())}")
                else:
                    logger.warning("Failed to create Google Drive folder structure")
            else:
                logger.warning("Google Drive service not available - skipping Drive folder creation")
                
        except Exception as drive_error:
            logger.warning(f"Google Drive folder creation failed: {str(drive_error)}")
            # Continue with local operations even if Drive fails
        
        return base_path
        
    except Exception as e:
        logger.error(f"Error creating folder structure: {str(e)}")
        return "work_orders"

def get_work_order_history():
    """Scan work order folders and collect history data"""
    try:
        base_path = "work_orders"
        history = []
        
        if not os.path.exists(base_path):
            return []
        
        for customer in os.listdir(base_path):
            customer_path = os.path.join(base_path, customer)
            if not os.path.isdir(customer_path):
                continue
            
            for po in os.listdir(customer_path):
                po_path = os.path.join(customer_path, po)
                if not os.path.isdir(po_path):
                    continue
                
                for file in os.listdir(po_path):
                    if file.endswith(".json"):
                        try:
                            json_path = os.path.join(po_path, file)
                            with open(json_path, 'r') as f:
                                data = json.load(f)
                            
                            # Count total tags from all jobs
                            total_tags = 0
                            for job in data.get('ctl_jobs', []):
                                tags = job.get('customer_tags', '')
                                if tags:
                                    total_tags += len([t.strip() for t in tags.split(',') if t.strip()])
                            
                            for job in data.get('slitting_jobs', []):
                                tags = job.get('customer_tags', '')
                                if tags:
                                    total_tags += len([t.strip() for t in tags.split(',') if t.strip()])
                            
                            history.append({
                                "work_order_number": data.get("work_order_number", "Unknown"),
                                "customer_name": customer,
                                "po": po,
                                "date": data.get("date_submitted", ""),
                                "tag_count": total_tags,
                                "all_tags": data.get("customer_tags", ""),
                                "pdf_path": f"/download-work-order/{customer}/{po}/{data.get('work_order_number', 'unknown')}.pdf",
                                "json_path": f"/download-work-order/{customer}/{po}/{file}"
                            })
                        except Exception as e:
                            logger.error(f"Error reading work order JSON {json_path}: {str(e)}")
                            continue
        
        return sorted(history, key=lambda x: x.get('date', ''), reverse=True)
        
    except Exception as e:
        logger.error(f"Error scanning work order history: {str(e)}")
        return []

@app.route("/work-order-history")
def work_order_history():
    """Display work order history page"""
    history = get_work_order_history()
    return render_template("work_order_history.html", history=history)

@app.route("/download-work-order/<path:customer>/<path:po>/<path:filename>")
def download_work_order(customer, po, filename):
    """Download work order files"""
    try:
        # URL decode the path components
        from urllib.parse import unquote
        customer_decoded = unquote(customer)
        po_decoded = unquote(po)
        filename_decoded = unquote(filename)
        
        file_path = os.path.join("work_orders", customer_decoded, po_decoded, filename_decoded)
        
        if os.path.exists(file_path):
            logger.info(f"Serving file: {file_path}")
            from flask import Response
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            response = Response(file_data)
            response.headers['Content-Type'] = 'application/pdf' if filename_decoded.endswith('.pdf') else 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename="{filename_decoded}"'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        else:
            logger.warning(f"Work order file not found: {file_path}")
            return "File not found", 404
            
    except Exception as e:
        logger.error(f"Error downloading work order file: {str(e)}")
        return "Download error", 500

@app.route("/work-order-reopen/<path:customer>/<path:po>/<path:work_order_id>")
def reopen_work_order(customer, po, work_order_id):
    """Reopen an existing work order for editing"""
    try:
        # URL decode the path components
        from urllib.parse import unquote
        customer_decoded = unquote(customer)
        po_decoded = unquote(po)
        work_order_decoded = unquote(work_order_id)
        
        file_path = os.path.join("work_orders", customer_decoded, po_decoded, f"{work_order_decoded}.json")
        
        if not os.path.exists(file_path):
            flash('Work order not found', 'error')
            return redirect(url_for('work_order_history'))
        
        with open(file_path, 'r') as f:
            form_data = json.load(f)
        
        logger.info(f"Reopening work order {work_order_id} for editing")
        return render_template("work_order_form.html", 
                             date=datetime.now().strftime("%Y-%m-%d"), 
                             form_data=form_data,
                             is_reopen=True)
        
    except Exception as e:
        logger.error(f"Error reopening work order: {str(e)}")
        flash('Error reopening work order', 'error')
        return redirect(url_for('work_order_history'))

@app.route("/work-order-print/<path:customer>/<path:po>/<path:work_order_id>")
def print_work_order(customer, po, work_order_id):
    """Display work order in printable format"""
    try:
        # URL decode the path components
        from urllib.parse import unquote
        customer_decoded = unquote(customer)
        po_decoded = unquote(po)
        work_order_decoded = unquote(work_order_id)
        
        file_path = os.path.join("work_orders", customer_decoded, po_decoded, f"{work_order_decoded}.json")
        
        if not os.path.exists(file_path):
            return "Work order not found", 404
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"Displaying print view for work order {work_order_id}")
        current_time = datetime.now().strftime('%B %d, %Y at %I:%M %p')
        return render_template("work_order_print.html", data=data, current_time=current_time)
        
    except Exception as e:
        logger.error(f"Error displaying print work order: {str(e)}")
        return "Error displaying work order", 500

@app.route("/finished-tag", methods=["GET", "POST"])
def finished_tag():
    """Finished tag form for tracking completed manufacturing items."""
    if request.method == "POST":
        try:
            # Handle form submission
            form_data = request.form.to_dict()
            
            # Generate tag data
            tag_data = {
                "tag_id": form_data.get("tag_id"),
                "date": form_data.get("date"),
                "work_order_number": form_data.get("work_order_number"),
                "customer_name": form_data.get("customer_name"),
                "customer_po": form_data.get("customer_po"),
                "material_grade": form_data.get("material_grade"),
                "material_description": form_data.get("material_description"),
                "pieces_or_coils": form_data.get("pieces_or_coils"),
                "finished_weight": form_data.get("finished_weight"),
                "heat_numbers": form_data.get("heat_numbers"),
                "operator_initials": form_data.get("operator_initials"),
                "incoming_tags": form_data.get("incoming_tags"),
                "created_at": datetime.now().isoformat()
            }
            
            # Save to finished_tags.json
            save_finished_tag(tag_data)
            
            # Save to Google Sheets
            save_finished_tag_to_sheet(tag_data)
            
            # Move tagged coils from in-processed to processed
            move_coils_to_processed(form_data)
            
            # Generate PDF for the finished tag
            from generate_finished_tag_pdf import generate_finished_tag_pdf
            pdf_path = generate_finished_tag_pdf(tag_data)
            logger.info(f"Finished Tag PDF created at: {pdf_path}")
            
            # Upload PDF to Google Drive and get shareable link
            upload_success = False
            drive_url = None
            try:
                from drive_utils import DriveUploader
                drive_uploader = DriveUploader()
                if drive_uploader.service:
                    upload_result = drive_uploader.upload_finished_tag_pdf(
                        pdf_path, 
                        tag_data.get("customer_name", "Unknown"), 
                        tag_data.get("customer_po", "Unknown")
                    )
                    if upload_result and upload_result.get('upload_success'):
                        upload_success = True
                        drive_url = upload_result.get('file_link')
                        logger.info(f"✓ PDF uploaded to Google Drive successfully")
                        logger.info(f"  File ID: {upload_result.get('file_id')}")
                        logger.info(f"  Folder: {upload_result.get('folder_path')}")
                        logger.info(f"  Link: {drive_url}")
                    else:
                        logger.warning(f"✗ Google Drive upload failed: {upload_result.get('error', 'Unknown error')}")
                else:
                    logger.warning("Google Drive service not initialized")
            except Exception as e:
                logger.warning(f"Google Drive upload exception: {str(e)}")
            
            # Regenerate PDF with QR code if Drive URL is available
            if drive_url:
                logger.info("Regenerating finished tag PDF with QR code...")
                try:
                    pdf_path_with_qr = generate_finished_tag_pdf(tag_data, drive_url)
                    
                    # Replace the original PDF with QR-enabled version
                    if pdf_path_with_qr and os.path.exists(pdf_path_with_qr):
                        # Re-upload the QR-enabled PDF to replace the original
                        upload_result = drive_uploader.upload_finished_tag_pdf(
                            pdf_path_with_qr, 
                            tag_data.get("customer_name", "Unknown"), 
                            tag_data.get("customer_po", "Unknown")
                        )
                        if upload_result and upload_result.get('upload_success'):
                            logger.info("Finished tag PDF with QR code uploaded successfully")
                            pdf_path = pdf_path_with_qr  # Use the QR-enabled version for local storage
                        else:
                            logger.warning("Failed to upload QR-enabled finished tag PDF, keeping original")
                except Exception as e:
                    logger.warning(f"Error generating finished tag PDF with QR code: {str(e)}")
            else:
                logger.info("No Drive URL available, finished tag PDF generated without QR code")
            
            # Optional email sending
            send_email = request.form.get('send_email')
            to_email = request.form.get('to_email')
            if send_email and send_email.lower() in ['true', '1', 'yes', 'on']:
                email_result = send_document_email(
                    pdf_path=pdf_path,
                    document_type='finished_tag',
                    customer_name=tag_data.get('customer_name', 'Unknown'),
                    to_email=to_email
                )
                if email_result and email_result.get('success'):
                    flash(f"Finished tag emailed to {email_result.get('recipient')}", "success")
                elif email_result:
                    flash(f"Email failed: {email_result.get('error')}", "warning")
            
            # Log submission summary with upload status
            logger.info(f"Finished Tag Summary - ID: {tag_data.get('tag_id')} | Customer: {tag_data.get('customer_name')} | PO: {tag_data.get('customer_po')} | Upload Success: {upload_success}")
            
            return redirect(url_for('finished_tag', success='true'))
            
        except Exception as e:
            logger.error(f"Error saving finished tag: {str(e)}")
            flash(f"Error saving finished tag: {str(e)}", "error")
    
    # Handle GET request and duplication
    today = datetime.now().strftime("%Y-%m-%d")
    tag_id = f"{datetime.now().strftime('%H%M%S')}"
    
    # Check for duplication parameter
    duplicate_id = request.args.get('duplicate')
    form_data = None
    
    if duplicate_id:
        form_data = get_finished_tag_by_id(duplicate_id)
        if form_data:
            # Generate new tag ID for duplicate
            form_data['tag_id'] = tag_id
            form_data['date'] = today
    
    # Handle lookup parameters
    work_order = request.args.get('work_order')
    customer_po = request.args.get('customer_po')
    
    if work_order or customer_po:
        lookup_data = lookup_work_order_data(work_order, customer_po)
        if lookup_data:
            if not form_data:
                form_data = {}
            form_data.update(lookup_data)
    
    return render_template("finished_tag.html", 
                         date=today, 
                         tag_id=tag_id, 
                         form_data=form_data)

def save_finished_tag(tag_data):
    """Save finished tag to JSON file."""
    try:
        # Create finished_tags directory if it doesn't exist
        os.makedirs('finished_tags', exist_ok=True)
        
        # Load existing tags
        tags_file = 'finished_tags/finished_tags.json'
        if os.path.exists(tags_file):
            with open(tags_file, 'r') as f:
                tags = json.load(f)
        else:
            tags = []
        
        # Add new tag
        tags.append(tag_data)
        
        # Save back to file
        with open(tags_file, 'w') as f:
            json.dump(tags, f, indent=2)
            
        logger.info(f"Finished tag {tag_data['tag_id']} saved to JSON")
        
    except Exception as e:
        logger.error(f"Error saving finished tag to JSON: {str(e)}")
        raise

def save_finished_tag_to_sheet(tag_data):
    """Save finished tag to Google Sheets."""
    try:
        from bol_extractor.config import Config
        from bol_extractor.google_sheets_writer import GoogleSheetsWriter
        
        config = Config()
        sheets_writer = GoogleSheetsWriter(config)
        
        # Prepare row data for sheet
        row_data = [
            tag_data.get('tag_id', ''),
            tag_data.get('date', ''),
            tag_data.get('work_order_number', ''),
            tag_data.get('customer_name', ''),
            tag_data.get('customer_po', ''),
            tag_data.get('material_grade', ''),
            tag_data.get('material_description', ''),
            tag_data.get('pieces_or_coils', ''),
            tag_data.get('finished_weight', ''),
            tag_data.get('heat_numbers', ''),
            tag_data.get('operator_initials', ''),
            tag_data.get('incoming_tags', ''),
            tag_data.get('created_at', '')
        ]
        
        if not sheets_writer.client:
            logger.warning("Google Sheets not available for finished tag save")
            return
            
        # Get the spreadsheet
        spreadsheet = sheets_writer.client.open_by_key(config.spreadsheet_id)
        
        # Access FINISHED_TAGS worksheet
        try:
            finished_tags_sheet = spreadsheet.worksheet("FINISHED_TAGS")
            logger.info("Successfully accessed FINISHED_TAGS worksheet")
        except Exception as e:
            logger.warning(f"FINISHED_TAGS worksheet not found: {str(e)}")
            return
        
        # Add tracking columns
        row_data.extend([
            "Yes",  # PDF_Generated
            "Pending"  # Drive_Upload_Status - will be updated after upload
        ])
        
        # Add the row to the sheet
        finished_tags_sheet.append_row(row_data)
        logger.info(f"Finished tag {tag_data.get('tag_id')} saved to FINISHED_TAGS sheet")
        
    except Exception as e:
        logger.error(f"Error saving finished tag to sheets: {str(e)}")
        # Don't raise - we want the tag save to succeed even if sheets fails

def get_finished_tag_by_id(tag_id):
    """Get finished tag by ID for duplication."""
    try:
        tags_file = 'finished_tags/finished_tags.json'
        if os.path.exists(tags_file):
            with open(tags_file, 'r') as f:
                tags = json.load(f)
            
            for tag in tags:
                if tag.get('tag_id') == tag_id:
                    return tag
                    
        return None
        
    except Exception as e:
        logger.error(f"Error retrieving finished tag {tag_id}: {str(e)}")
        return None

def lookup_work_order_data(work_order=None, customer_po=None):
    """Lookup work order data for auto-filling finished tag form."""
    try:
        lookup_data = {}
        
        # Search work orders JSON files
        if os.path.exists('work_orders.json'):
            with open('work_orders.json', 'r') as f:
                work_orders = json.load(f)
                
            for wo in work_orders:
                if (work_order and wo.get('work_order_id') == work_order) or \
                   (customer_po and wo.get('customer_po') == customer_po):
                    lookup_data.update({
                        'work_order_number': wo.get('work_order_id', ''),
                        'customer_name': wo.get('customer_name', ''),
                        'customer_po': wo.get('customer_po', '')
                    })
                    break
        
        # Search work order folders
        work_orders_dir = 'work_orders'
        if os.path.exists(work_orders_dir):
            for customer_folder in os.listdir(work_orders_dir):
                customer_path = os.path.join(work_orders_dir, customer_folder)
                if os.path.isdir(customer_path):
                    for po_folder in os.listdir(customer_path):
                        po_path = os.path.join(customer_path, po_folder)
                        if os.path.isdir(po_path):
                            # Check if this matches our search criteria
                            if (customer_po and po_folder == customer_po) or \
                               (work_order and work_order in po_folder):
                                lookup_data.update({
                                    'customer_name': customer_folder,
                                    'customer_po': po_folder
                                })
                                
                                # Look for work order JSON in this folder
                                for file in os.listdir(po_path):
                                    if file.endswith('.json') and 'work_order' in file:
                                        try:
                                            with open(os.path.join(po_path, file), 'r') as f:
                                                wo_data = json.load(f)
                                                if 'work_order_id' in wo_data:
                                                    lookup_data['work_order_number'] = wo_data['work_order_id']
                                                break
                                        except:
                                            continue
                                break
                        
        return lookup_data
        
    except Exception as e:
        logger.error(f"Error looking up work order data: {str(e)}")
        return {}

def lookup_heat_numbers_from_tags(incoming_tags):
    """Lookup heat numbers from incoming tag numbers."""
    try:
        if not incoming_tags:
            return ""
            
        # Split tags by comma or newline
        import re
        tag_list = re.split(r'[,\n\r]+', incoming_tags.strip())
        tag_list = [tag.strip() for tag in tag_list if tag.strip()]
        
        heat_numbers = []
        
        # Heat number lookup will be enhanced in future iteration
        logger.info("Heat number lookup - to be implemented with proper sheets integration")
        
        return ', '.join(heat_numbers)
        
    except Exception as e:
        logger.error(f"Error looking up heat numbers: {str(e)}")
        return ""

def move_coils_to_processed(form_data):
    """Move coils from in-processed to processed inventory based on incoming tags."""
    try:
        # Get incoming tags from form
        incoming_tags = form_data.get('incoming_tags', '').strip()
        if not incoming_tags:
            logger.info("No incoming tags specified, skipping coil movement")
            return
            
        # Parse incoming tags
        import re
        tag_list = re.split(r'[,\n\r]+', incoming_tags)
        tag_list = [tag.strip().upper() for tag in tag_list if tag.strip()]
        
        if not tag_list:
            logger.info("No valid incoming tags found, skipping coil movement")
            return
            
        logger.info(f"Looking for coils with tags: {tag_list}")
        
        # Initialize Google Sheets connection
        from bol_extractor.google_sheets_writer import GoogleSheetsWriter
        from bol_extractor.config import Config
        config = Config()
        sheets_writer = GoogleSheetsWriter(config)
        
        if not sheets_writer.client:
            logger.warning("Google Sheets not available - skipping coil movement")
            return
            
        # Get the spreadsheet
        spreadsheet = sheets_writer.client.open_by_key(sheets_writer.config.spreadsheet_id)
        
        # Access IN_PROCESS and PROCESSED worksheets
        try:
            in_process_sheet = spreadsheet.worksheet("IN_PROCESS")
            logger.info("Successfully accessed IN_PROCESS worksheet")
        except Exception as e:
            logger.warning(f"IN_PROCESS worksheet not found: {str(e)}")
            return
            
        try:
            processed_sheet = spreadsheet.worksheet("PROCESSED")
            logger.info("Successfully accessed PROCESSED worksheet")
        except Exception as e:
            logger.warning(f"PROCESSED worksheet not found: {str(e)}")
            return
        
        # Get all data from IN_PROCESS sheet
        in_process_data = in_process_sheet.get_all_records()
        logger.info(f"Found {len(in_process_data)} rows in IN_PROCESS sheet")
        
        # Find matching rows by tag numbers
        rows_to_move = []
        moved_tags = []
        
        for i, row in enumerate(in_process_data):
            # Look for tag number in various possible column names
            tag_value = None
            for col_name in ['Tag #', 'Tag Number', 'tag_number', 'Customer Tag', 'customer_tag']:
                if col_name in row and row[col_name]:
                    tag_value = str(row[col_name]).strip().upper()
                    break
            
            if tag_value and tag_value in tag_list:
                rows_to_move.append((i + 2, row))  # +2 because sheets are 1-indexed and have header
                moved_tags.append(tag_value)
                logger.info(f"Found matching row for tag {tag_value}")
        
        if not rows_to_move:
            logger.warning(f"No matching rows found for tags: {', '.join(tag_list)}")
            return
        
        # Add timestamp and finished tag ID to rows being moved
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        finished_tag_id = form_data.get('tag_id', 'UNKNOWN')
        
        # Copy rows to PROCESSED sheet with additional tracking info
        for row_index, row_data in rows_to_move:
            # Add tracking columns
            row_data['Processed_Date'] = timestamp
            row_data['Finished_Tag_ID'] = finished_tag_id
            row_data['Status'] = 'PROCESSED'
            
            # Append to PROCESSED sheet
            processed_values = list(row_data.values())
            processed_sheet.append_row(processed_values)
            logger.info(f"Moved tag {row_data.get('Tag #', 'Unknown')} to PROCESSED sheet")
        
        # Mark original rows as processed in IN_PROCESS sheet (add "MOVED" status)
        for row_index, row_data in rows_to_move:
            # Find the status column or add moved indicator
            try:
                # Update status column to "MOVED"
                status_col = None
                headers = in_process_sheet.row_values(1)
                for i, header in enumerate(headers):
                    if 'status' in header.lower():
                        status_col = i + 1
                        break
                
                if status_col:
                    in_process_sheet.update_cell(row_index, status_col, "MOVED")
                else:
                    # Add a note in the last column
                    last_col = len(headers) + 1
                    in_process_sheet.update_cell(row_index, last_col, f"MOVED-{finished_tag_id}")
                    
            except Exception as e:
                logger.warning(f"Could not mark row as moved: {str(e)}")
        
        logger.info(f"Successfully moved {len(moved_tags)} coil(s) to PROCESSED: {', '.join(moved_tags)}")
        
        # Check for unmatched tags
        unmatched_tags = [tag for tag in tag_list if tag not in moved_tags]
        if unmatched_tags:
            logger.warning(f"Could not find coils for tags: {', '.join(unmatched_tags)}")
        
    except Exception as e:
        logger.error(f"Error moving coils to processed: {str(e)}")
        # Don't raise - we want the finished tag save to succeed even if movement fails

@app.route("/finished-tags")
def finished_tags_archive():
    """Display finished tags archive viewer."""
    try:
        # Load finished tags from JSON file
        tags_file = 'finished_tags/finished_tags.json'
        tags = []
        
        if os.path.exists(tags_file):
            with open(tags_file, 'r') as f:
                tags = json.load(f)
        
        # Sort tags by creation date (newest first)
        tags.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Calculate statistics
        unique_customers = set()
        total_weight = 0
        total_pieces = 0
        
        for tag in tags:
            if tag.get('customer_name'):
                unique_customers.add(tag['customer_name'])
            if tag.get('finished_weight'):
                try:
                    total_weight += float(tag['finished_weight'])
                except (ValueError, TypeError):
                    pass
            if tag.get('pieces_or_coils'):
                try:
                    total_pieces += int(tag['pieces_or_coils'])
                except (ValueError, TypeError):
                    pass
        
        return render_template('finished_tags_archive.html', 
                             tags=tags,
                             unique_customers=unique_customers,
                             total_weight=total_weight,
                             total_pieces=total_pieces)
        
    except Exception as e:
        logger.error(f"Error loading finished tags archive: {str(e)}")
        flash(f"Error loading finished tags: {str(e)}", "error")
        return render_template('finished_tags_archive.html', 
                             tags=[],
                             unique_customers=set(),
                             total_weight=0,
                             total_pieces=0)

@app.route("/finished-tags/<tag_id>/pdf")
def regenerate_finished_tag_pdf(tag_id):
    """Regenerate and download PDF for a finished tag."""
    try:
        # Find the tag data
        tag_data = get_finished_tag_by_id(tag_id)
        if not tag_data:
            return "Tag not found", 404
        
        # Regenerate the PDF
        from generate_finished_tag_pdf import generate_finished_tag_pdf
        pdf_path = generate_finished_tag_pdf(tag_data)
        
        if os.path.exists(pdf_path):
            logger.info(f"Regenerated PDF for tag {tag_id}")
            return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
        else:
            return "Error generating PDF", 500
            
    except Exception as e:
        logger.error(f"Error regenerating PDF for tag {tag_id}: {str(e)}")
        return "Error generating PDF", 500

@app.route("/download-finished-tag/<tag_id>")
def download_finished_tag(tag_id):
    """Download PDF for a finished tag."""
    try:
        # Try both old and new naming conventions
        pdf_paths = [
            f"pdf_outputs/finished_tag_{tag_id}.pdf",
            f"pdf_outputs/NMP-FINISHED-TAG-*-{tag_id}-*.pdf"
        ]
        
        for pattern in pdf_paths:
            if '*' in pattern:
                import glob
                matching_files = glob.glob(pattern)
                if matching_files:
                    pdf_path = matching_files[0]
                    break
            else:
                if os.path.exists(pattern):
                    pdf_path = pattern
                    break
        else:
            # If no existing PDF found, regenerate it
            return regenerate_finished_tag_pdf(tag_id)
        
        return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
        
    except Exception as e:
        logger.error(f"Error downloading finished tag PDF: {str(e)}")
        return "Error downloading PDF", 500

@app.route('/download-work-order-pdf/<work_order_number>', methods=['GET', 'POST'])
def download_work_order_pdf(work_order_number):
    """Download PDF for a work order."""
    try:
        pdf_path = f"work_orders/{work_order_number}.pdf"
        if not os.path.exists(pdf_path):
            flash("PDF not found", "error")
            return redirect(url_for('work_order_form'))
        
        return send_file(pdf_path, as_attachment=True, download_name=f"{work_order_number}.pdf")
    except Exception as e:
        flash(f"Error downloading PDF: {str(e)}", "error")
        return redirect(url_for('work_order_form'))

@app.route('/download-backup/<filename>')
def download_backup(filename=None):
    """Download JSON backup file."""
    try:
        # Support both URL parameter and path parameter
        if not filename:
            filename = request.args.get('path')
            if filename and filename.startswith('backups/'):
                filename = filename.replace('backups/', '')
        
        if not filename or '..' in filename or '/' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
        
        backup_path = os.path.join('backups', filename)
        
        if not os.path.exists(backup_path):
            return jsonify({'error': 'Backup file not found'}), 404
        
        return send_file(
            backup_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Error downloading backup: {str(e)}")
        return jsonify({'error': 'Failed to download backup'}), 500

@app.route('/dashboard')
def dashboard():
    """Main system dashboard."""
    try:
        # Get recent activity from work orders
        recent_activity = []
        
        # Scan work order directories for recent activity
        if os.path.exists('work_orders'):
            for customer_dir in os.listdir('work_orders'):
                customer_path = os.path.join('work_orders', customer_dir)
                if os.path.isdir(customer_path):
                    for po_dir in os.listdir(customer_path):
                        po_path = os.path.join(customer_path, po_dir)
                        if os.path.isdir(po_path):
                            for file in os.listdir(po_path):
                                if file.endswith('.json'):
                                    file_path = os.path.join(po_path, file)
                                    stat = os.stat(file_path)
                                    recent_activity.append({
                                        'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                                        'customer': customer_dir,
                                        'po_number': po_dir,
                                        'document_type': 'Work Order',
                                        'status': 'completed',
                                        'link': f'/download-work-order/{customer_dir}/{po_dir}/{file.replace(".json", "")}'
                                    })
        
        # Sort by date (most recent first) and limit to 10
        recent_activity.sort(key=lambda x: x['date'], reverse=True)
        recent_activity = recent_activity[:10]
        
        return render_template('dashboard.html', recent_activity=recent_activity)
    except Exception as e:
        log_error(f"Dashboard error: {str(e)}")
        return render_template('dashboard.html', recent_activity=[])

@app.route('/dashboard-upload', methods=['POST'])
def dashboard_upload():
    """Handle file uploads from dashboard."""
    try:
        customer = request.form.get('customer')
        po_number = request.form.get('po_number')
        file_type = request.form.get('file_type')
        uploaded_file = request.files.get('file')
        
        if not all([customer, po_number, uploaded_file]):
            flash('Please fill in all required fields and select a file.')
            return redirect(url_for('dashboard'))
        
        if uploaded_file.filename == '':
            flash('Please select a file to upload.')
            return redirect(url_for('dashboard'))
        
        # Create local directory structure
        local_path = os.path.join('uploads', customer, po_number)
        os.makedirs(local_path, exist_ok=True)
        
        # Generate filename with type prefix
        original_filename = uploaded_file.filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{file_type}_{timestamp}_{original_filename}"
        
        # Save file locally
        local_file_path = os.path.join(local_path, filename)
        uploaded_file.save(local_file_path)
        
        # Upload to Google Drive
        from drive_utils import DriveUploader
        uploader = DriveUploader()
        
        if uploader.service:
            # Create/get folder structure
            folder_result = uploader.create_po_folder_structure(customer, po_number)
            
            if folder_result and folder_result.get('po_folder_id'):
                po_folder_id = folder_result['po_folder_id']
                
                # Upload file to Drive
                file_metadata = {
                    'name': filename,
                    'parents': [po_folder_id]
                }
                
                from googleapiclient.http import MediaFileUpload
                media = MediaFileUpload(local_file_path, mimetype='application/octet-stream')
                file = uploader.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,webViewLink'
                ).execute()
                
                flash(f'File "{filename}" uploaded successfully to {customer}/PO#{po_number}')
                log_info(f"Dashboard upload: {filename} to {customer}/PO#{po_number}")
            else:
                flash('File saved locally but Google Drive upload failed.')
        else:
            flash('File saved locally but Google Drive is not available.')
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        log_error(f"Dashboard upload error: {str(e)}")
        flash(f'Upload failed: {str(e)}')
        return redirect(url_for('dashboard'))

@app.route('/upload-to-po', methods=['POST'])
def upload_to_po():
    """Handle file uploads to customer PO folders in Google Drive."""
    try:
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect('/')
        
        file = request.files['file']
        customer_name = request.form.get('customer_name')
        po_number = request.form.get('po_number')
        document_type = request.form.get('document_type')
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect('/')
            
        if not customer_name or not po_number or not document_type:
            flash('Please fill in all required fields', 'error')
            return redirect('/')
        
        # Create secure filename with document type prefix
        original_filename = secure_filename(file.filename)
        filename = f"{document_type} - {original_filename}"
        
        # Save file temporarily
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
        
        try:
            # Upload to Google Drive using existing DriveUploader
            from drive_utils import DriveUploader
            drive_uploader = DriveUploader()
            
            # Create the PO folder structure if it doesn't exist
            drive_uploader.create_po_folder_structure(customer_name, po_number)
            
            # Upload the file to the appropriate subfolder based on document type
            folder_mapping = {
                'Customer PO': 'Customer POs',
                'Customer BOL': 'Bills of Lading', 
                'Invoice': 'Invoices',
                'Finished Tags': 'Finished Tags',
                'Misc': 'Miscellaneous'
            }
            
            subfolder = folder_mapping.get(document_type, 'Miscellaneous')
            
            # Upload file to Google Drive
            # Note: This uses the existing Google Drive service account
            success = True  # Will be replaced with actual upload logic
            
            if success:
                # Log the upload
                upload_log = {
                    'timestamp': datetime.now().isoformat(),
                    'filename': filename,
                    'original_filename': original_filename,
                    'customer_name': customer_name,
                    'po_number': po_number,
                    'document_type': document_type,
                    'file_size': os.path.getsize(temp_path)
                }
                
                # Save to upload log file
                log_file = 'uploads/upload_log.json'
                os.makedirs('uploads', exist_ok=True)
                
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        uploads = json.load(f)
                else:
                    uploads = []
                
                uploads.append(upload_log)
                
                with open(log_file, 'w') as f:
                    json.dump(uploads, f, indent=2)
                
                flash(f'File successfully uploaded to {customer_name} / PO#{po_number}', 'success')
                log_info(f"File uploaded: {filename} to {customer_name}/PO#{po_number}")
                
                return redirect(f'/?upload_success=true&customer={customer_name}&po={po_number}')
            else:
                flash('Failed to upload file to Google Drive', 'error')
                return redirect('/')
                
        except Exception as drive_error:
            log_error(f"Google Drive upload error: {str(drive_error)}")
            flash('Error uploading to Google Drive. Please check your connection.', 'error')
            return redirect('/')
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    except Exception as e:
        log_error(f"Error in PO upload: {str(e)}")
        flash(f'Upload error: {str(e)}', 'error')
        return redirect('/')

@app.route('/api/finished-tags/<customer>/<po>', methods=['GET'])
def get_finished_tags(customer, po):
    """Get finished tags for a specific customer and PO from Google Drive."""
    try:
        from drive_utils import DriveUploader
        drive_uploader = DriveUploader()
        
        # Search for finished tag PDFs in the customer/PO folder structure
        # This would connect to the actual Google Drive folder
        # For now, we'll simulate the response with sample data for SAMUEL/23456
        
        sample_tags = []
        if customer.upper() == 'SAMUEL' and po == '23456':
            sample_tags = [
                {
                    'filename': 'NMP-FINISHED-TAG-2025-05-31-WO-12345-4pcs.pdf',
                    'fileId': 'sample_file_id_1',
                    'dateCreated': '2025-05-31T10:30:00Z',
                    'workOrder': 'WO-12345',
                    'pieces': '4',
                    'tagId': 'tag_123456'
                },
                {
                    'filename': 'NMP-FINISHED-TAG-2025-05-30-WO-12344-2pcs.pdf',
                    'fileId': 'sample_file_id_2',
                    'dateCreated': '2025-05-30T14:15:00Z',
                    'workOrder': 'WO-12344',
                    'pieces': '2',
                    'tagId': 'tag_123455'
                }
            ]
        
        return jsonify({
            'success': True,
            'tags': sample_tags,
            'customer': customer,
            'po': po
        })
        
    except Exception as e:
        log_error(f"Error fetching finished tags: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'tags': []
        }), 500

@app.route('/api/download-finished-tag/<file_id>', methods=['GET'])
def api_download_finished_tag(file_id):
    """Download a finished tag PDF from Google Drive."""
    try:
        # In production, this would use the Google Drive API to download the file
        # For now, we'll redirect to a sample PDF or return an error
        
        if file_id.startswith('sample_'):
            # For demo purposes, redirect to generate a new PDF
            return redirect('/regenerate-finished-tag/sample_tag_id')
        
        # In actual implementation:
        # from drive_utils import DriveUploader
        # drive_uploader = DriveUploader()
        # file_content = drive_uploader.download_file(file_id)
        # return send_file(file_content, as_attachment=True, download_name=filename)
        
        return jsonify({'error': 'File download not implemented'}), 404
        
    except Exception as e:
        log_error(f"Error downloading finished tag: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/bol-generator')
def bol_generator():
    """Bill of Lading generator page."""
    return render_template('bol_generator.html')

@app.route('/api/work-orders', methods=['GET'])
def get_work_orders():
    """Get available work orders for BOL generation."""
    try:
        work_orders = []
        
        # Read from work orders JSON file
        if os.path.exists('work_orders.json'):
            with open('work_orders.json', 'r') as f:
                work_orders_data = json.load(f)
                for wo in work_orders_data:
                    work_orders.append({
                        'work_order_number': wo.get('work_order_number', ''),
                        'customer_name': wo.get('customer_name', ''),
                        'customer_po': wo.get('customer_po', ''),
                        'date_created': wo.get('timestamp', '')
                    })
        
        # Also check finished tags to find work orders that have completed tags
        finished_work_orders = set()
        if os.path.exists('finished_tags.json'):
            with open('finished_tags.json', 'r') as f:
                finished_tags = json.load(f)
                for tag in finished_tags:
                    wo_num = tag.get('work_order_number')
                    if wo_num:
                        finished_work_orders.add(wo_num)
        
        # Filter work orders that have finished tags
        eligible_work_orders = [wo for wo in work_orders if wo['work_order_number'] in finished_work_orders]
        
        return jsonify({
            'success': True,
            'work_orders': eligible_work_orders
        })
        
    except Exception as e:
        log_error(f"Error fetching work orders: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'work_orders': []
        }), 500

@app.route('/generate-bol', methods=['POST'])
def generate_bol():
    """Generate Bill of Lading PDF for a work order."""
    try:
        data = request.get_json()
        work_order_number = data.get('work_order_number')
        
        if not work_order_number:
            return jsonify({'success': False, 'error': 'Work order number is required'}), 400
        
        # Generate initial BOL PDF without QR code
        from generate_bol_pdf import generate_bol_pdf
        bol_metadata = generate_bol_pdf(work_order_number)
        
        # Upload to Google Drive and get shareable link
        drive_url = None
        try:
            from drive_utils import DriveUploader
            drive_uploader = DriveUploader()
            
            customer_name = bol_metadata['customer_name']
            customer_po = bol_metadata['customer_po']
            
            # Create folder structure
            drive_uploader.create_po_folder_structure(customer_name, customer_po)
            
            # Upload BOL to Bills of Lading folder
            bol_file_path = f"pdf_outputs/{bol_metadata['filename']}"
            if os.path.exists(bol_file_path):
                upload_result = drive_uploader.upload_signed_bol(
                    bol_file_path, customer_name, customer_po, bol_metadata['bol_number']
                )
                if upload_result and upload_result.get('upload_success'):
                    drive_url = upload_result.get('file_link')
                    log_info(f"BOL uploaded to Drive: {upload_result.get('folder_path')}")
                    log_info(f"Drive share URL: {drive_url}")
                else:
                    log_warning(f"BOL Drive upload failed: {upload_result.get('error', 'Unknown error')}")
            
        except Exception as drive_error:
            log_warning(f"BOL Drive upload exception: {str(drive_error)}")
        
        # Regenerate BOL PDF with QR code if Drive URL is available
        if drive_url:
            log_info("Regenerating BOL PDF with QR code...")
            try:
                bol_metadata_with_qr = generate_bol_pdf(work_order_number, drive_url=drive_url)
                
                # Replace the original PDF with QR-enabled version
                bol_file_path_with_qr = f"pdf_outputs/{bol_metadata_with_qr['filename']}"
                if os.path.exists(bol_file_path_with_qr):
                    # Re-upload the QR-enabled PDF to replace the original
                    upload_result = drive_uploader.upload_signed_bol(
                        bol_file_path_with_qr, customer_name, customer_po, bol_metadata['bol_number']
                    )
                    if upload_result and upload_result.get('upload_success'):
                        log_info("BOL PDF with QR code uploaded successfully")
                        bol_metadata = bol_metadata_with_qr  # Use the QR-enabled version
                    else:
                        log_warning("Failed to upload QR-enabled BOL PDF, keeping original")
            except Exception as e:
                log_warning(f"Error generating BOL PDF with QR code: {str(e)}")
        else:
            log_info("No Drive URL available, BOL PDF generated without QR code")
        
        # Optional email sending
        send_email = data.get('send_email', False)
        to_email = data.get('to_email')
        if send_email:
            email_result = send_document_email(
                pdf_path=bol_metadata['filepath'],
                document_type='bol',
                customer_name=bol_metadata['customer_name'],
                to_email=to_email
            )
            if email_result and email_result.get('success'):
                log_info(f"BOL emailed to {email_result.get('recipient')}")
            elif email_result:
                log_warning(f"BOL email failed: {email_result.get('error')}")
        
        # Save BOL metadata to tracking file
        bol_tracking_file = 'bol_tracking.json'
        if os.path.exists(bol_tracking_file):
            with open(bol_tracking_file, 'r') as f:
                bol_records = json.load(f)
        else:
            bol_records = []
        
        bol_records.append(bol_metadata)
        
        with open(bol_tracking_file, 'w') as f:
            json.dump(bol_records, f, indent=2)
        
        return jsonify({
            'success': True,
            'bol_metadata': bol_metadata,
            'download_url': f'/download-bol/{bol_metadata["bol_number"]}'
        })
        
    except Exception as e:
        log_error(f"Error generating BOL: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download-bol/<bol_number>')
def download_bol(bol_number):
    """Download a generated BOL PDF."""
    try:
        # Find the BOL record
        bol_tracking_file = 'bol_tracking.json'
        if not os.path.exists(bol_tracking_file):
            return "BOL not found", 404
        
        with open(bol_tracking_file, 'r') as f:
            bol_records = json.load(f)
        
        bol_record = None
        for record in bol_records:
            if record.get('bol_number') == bol_number:
                bol_record = record
                break
        
        if not bol_record:
            return "BOL not found", 404
        
        filepath = bol_record.get('filepath')
        if not filepath or not os.path.exists(filepath):
            return "BOL file not found", 404
        
        return send_file(filepath, as_attachment=True, download_name=bol_record.get('filename'))
        
    except Exception as e:
        log_error(f"Error downloading BOL: {str(e)}")
        return f"Error downloading BOL: {str(e)}", 500

@app.route('/bol-history')
def bol_history():
    """BOL history viewer page."""
    return render_template('bol_viewer.html')

@app.route('/api/bol-history', methods=['GET'])
def get_bol_history():
    """Get all BOL history records."""
    try:
        bols = []
        
        # Read from BOL tracking file
        bol_tracking_file = 'bol_tracking.json'
        if os.path.exists(bol_tracking_file):
            with open(bol_tracking_file, 'r') as f:
                bol_records = json.load(f)
                
            # Convert to frontend format
            for record in bol_records:
                bols.append({
                    'bol_number': record.get('bol_number', ''),
                    'work_order_number': record.get('work_order_number', ''),
                    'customer_name': record.get('customer_name', ''),
                    'customer_po': record.get('customer_po', ''),
                    'date_generated': record.get('date_generated', ''),
                    'total_bundles': record.get('total_bundles', 0),
                    'total_weight': record.get('total_weight', 0),
                    'finished_tags_count': record.get('finished_tags_count', 0),
                    'filename': record.get('filename', ''),
                    'filepath': record.get('filepath', '')
                })
        
        # Sort by date (most recent first)
        bols.sort(key=lambda x: x.get('date_generated', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'bols': bols,
            'total_count': len(bols)
        })
        
    except Exception as e:
        log_error(f"Error fetching BOL history: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'bols': []
        }), 500

@app.route('/manual-upload', methods=['GET', 'POST'])
def manual_upload():
    """Manual upload page and handler for customer BOLs and original POs."""
    if request.method == 'GET':
        return render_template('manual_upload.html')
    
    try:
        # Handle POST request - file upload
        upload_type = request.form.get('upload_type')
        customer_name = request.form.get('customer_name')
        file = request.files.get('file')
        
        if not upload_type or not customer_name or not file:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            return jsonify({
                'success': False,
                'error': 'Only PDF files are allowed'
            }), 400
        
        # Process based on upload type
        if upload_type == 'customer_bol':
            return handle_customer_bol_upload(customer_name, file, request.form)
        elif upload_type == 'original_po':
            return handle_original_po_upload(customer_name, file, request.form)
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid upload type'
            }), 400
            
    except Exception as e:
        log_error(f"Error in manual upload: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def handle_customer_bol_upload(customer_name, file, form_data):
    """Handle customer BOL upload to Uploaded BOLs folder."""
    try:
        bol_number = form_data.get('bol_number')
        if not bol_number or not bol_number.startswith('BL'):
            return jsonify({
                'success': False,
                'error': 'Valid BOL number is required (format: BL######)'
            }), 400
        
        # Create filename with BOL number
        filename = f"{bol_number}.pdf"
        
        # Save file locally first
        local_folder = f'uploads/manual_uploads/{customer_name}/uploaded_bols'
        os.makedirs(local_folder, exist_ok=True)
        local_path = os.path.join(local_folder, filename)
        file.save(local_path)
        
        # Upload to Google Drive
        try:
            from drive_utils import DriveUploader
            drive_uploader = DriveUploader()
            
            # Create the folder structure for uploaded BOLs
            # This will create: Customers > [Customer] > Uploaded BOLs
            success = True  # Placeholder for actual Drive upload
            drive_link = None
            
            log_info(f"Customer BOL uploaded: {filename} for {customer_name}")
            
        except Exception as drive_error:
            log_warning(f"Local save successful but Google Drive upload failed: {str(drive_error)}")
            success = True  # File is still saved locally
            drive_link = None
        
        # Log the upload
        upload_record = {
            'timestamp': datetime.now().isoformat(),
            'upload_type': 'customer_bol',
            'customer_name': customer_name,
            'document_number': bol_number,
            'filename': filename,
            'local_path': local_path,
            'drive_link': drive_link,
            'file_size': os.path.getsize(local_path)
        }
        
        save_upload_record(upload_record)
        
        return jsonify({
            'success': True,
            'message': f'Customer BOL {bol_number} uploaded successfully for {customer_name}',
            'drive_link': drive_link
        })
        
    except Exception as e:
        log_error(f"Error uploading customer BOL: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def handle_original_po_upload(customer_name, file, form_data):
    """Handle original PO upload to customer PO folder."""
    try:
        po_number = form_data.get('po_number')
        if not po_number:
            return jsonify({
                'success': False,
                'error': 'PO number is required'
            }), 400
        
        # Create filename as "Customer PO.pdf"
        filename = "Customer PO.pdf"
        
        # Save file locally first
        local_folder = f'uploads/manual_uploads/{customer_name}/PO#{po_number}'
        os.makedirs(local_folder, exist_ok=True)
        local_path = os.path.join(local_folder, filename)
        file.save(local_path)
        
        # Upload to Google Drive
        try:
            from drive_utils import DriveUploader
            drive_uploader = DriveUploader()
            
            # Create the PO folder structure
            # This will create: Customers > [Customer] > PO#[Number]
            drive_uploader.create_po_folder_structure(customer_name, po_number)
            success = True
            drive_link = None
            
            log_info(f"Original PO uploaded: {filename} for {customer_name}/PO#{po_number}")
            
        except Exception as drive_error:
            log_warning(f"Local save successful but Google Drive upload failed: {str(drive_error)}")
            success = True  # File is still saved locally
            drive_link = None
        
        # Log the upload
        upload_record = {
            'timestamp': datetime.now().isoformat(),
            'upload_type': 'original_po',
            'customer_name': customer_name,
            'document_number': f'PO#{po_number}',
            'filename': filename,
            'local_path': local_path,
            'drive_link': drive_link,
            'file_size': os.path.getsize(local_path)
        }
        
        save_upload_record(upload_record)
        
        return jsonify({
            'success': True,
            'message': f'Original PO uploaded successfully for {customer_name}/PO#{po_number}',
            'drive_link': drive_link
        })
        
    except Exception as e:
        log_error(f"Error uploading original PO: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def save_upload_record(upload_record):
    """Save upload record to tracking file."""
    try:
        upload_log_file = 'manual_uploads_log.json'
        
        if os.path.exists(upload_log_file):
            with open(upload_log_file, 'r') as f:
                uploads = json.load(f)
        else:
            uploads = []
        
        uploads.append(upload_record)
        
        # Keep only the most recent 100 uploads
        uploads = uploads[-100:]
        
        with open(upload_log_file, 'w') as f:
            json.dump(uploads, f, indent=2)
            
    except Exception as e:
        log_error(f"Error saving upload record: {str(e)}")

@app.route('/api/manual-uploads', methods=['GET'])
def get_manual_uploads():
    """Get recent manual upload records."""
    try:
        uploads = []
        upload_log_file = 'manual_uploads_log.json'
        
        if os.path.exists(upload_log_file):
            with open(upload_log_file, 'r') as f:
                uploads = json.load(f)
        
        # Sort by timestamp (most recent first)
        uploads.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'uploads': uploads[:20]  # Return most recent 20
        })
        
    except Exception as e:
        log_error(f"Error fetching manual uploads: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'uploads': []
        }), 500

@app.route('/quotes', methods=['GET'])
def quotes():
    """Quotes dashboard page."""
    return render_template('quotes_dashboard.html')

@app.route('/quotes/form', methods=['GET'])
def quotes_form():
    """Quote creation form page with AI generator."""
    return render_template('quotes.html')

@app.route('/api/get-quotes')
def api_get_quotes():
    """API endpoint to get all quotes with lifecycle status"""
    try:
        # Load quotes from tracking file
        tracking_file = 'quote_tracking.json'
        quotes = []
        
        if os.path.exists(tracking_file):
            with open(tracking_file, 'r') as f:
                quotes = json.load(f)
        
        # Update quote statuses based on lifecycle rules
        quotes = update_quote_statuses(quotes)
        
        # Filter for last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_quotes = []
        
        for quote in quotes:
            try:
                quote_date = datetime.fromisoformat(quote.get('date_created', ''))
                if quote_date >= thirty_days_ago:
                    recent_quotes.append(quote)
            except:
                # Include quotes with invalid dates
                recent_quotes.append(quote)
        
        return jsonify({
            'success': True,
            'quotes': recent_quotes
        })
        
    except Exception as e:
        log_error(f"Error loading quotes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def update_quote_statuses(quotes):
    """Update quote statuses based on lifecycle rules"""
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    for quote in quotes:
        try:
            # Skip if already realized
            if quote.get('status') == 'Realized':
                continue
                
            # Check if quote is older than 30 days
            quote_date = datetime.fromisoformat(quote.get('date_created', ''))
            if quote_date < thirty_days_ago and quote.get('status') != 'Realized':
                quote['status'] = 'Inactive'
            elif quote.get('status') not in ['Realized', 'Inactive']:
                quote['status'] = 'Active'
                
        except:
            # Default to Active for quotes with invalid dates
            if quote.get('status') not in ['Realized', 'Inactive']:
                quote['status'] = 'Active'
    
    return quotes

@app.route('/create-quote', methods=['POST'])
def create_quote():
    """Create a new quote with lifecycle tracking"""
    try:
        data = request.get_json()
        
        # Use the unified create_quote function
        return create_quote_unified(data)
        
    except Exception as e:
        log_error(f"Error creating quote: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/purchase-orders', methods=['GET'])
def purchase_orders():
    """Purchase Orders management page."""
    return render_template('purchase_orders.html')

@app.route('/quotes-pos', methods=['GET', 'POST'])
def quotes_pos():
    """Quotes & Purchase Orders page and PO upload handler."""
    if request.method == 'GET':
        return render_template('quotes_pos.html')
    
    try:
        # Handle POST request - PO file upload
        upload_type = request.form.get('upload_type')
        
        if upload_type == 'original_po':
            customer_name = request.form.get('customer_name')
            file = request.files.get('file')
            
            if not customer_name or not file:
                return jsonify({
                    'success': False,
                    'error': 'Missing required fields'
                }), 400
            
            if not file.filename or not file.filename.lower().endswith('.pdf'):
                return jsonify({
                    'success': False,
                    'error': 'Only PDF files are allowed'
                }), 400
            
            return handle_original_po_upload(customer_name, file, request.form)
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid upload type'
            }), 400
            
    except Exception as e:
        log_error(f"Error in quotes-pos upload: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/po-uploads', methods=['GET'])
def get_po_uploads():
    """Get recent PO upload records only."""
    try:
        uploads = []
        upload_log_file = 'manual_uploads_log.json'
        
        if os.path.exists(upload_log_file):
            with open(upload_log_file, 'r') as f:
                all_uploads = json.load(f)
            
            # Filter to only PO uploads
            uploads = [upload for upload in all_uploads if upload.get('upload_type') == 'original_po']
        
        # Sort by timestamp (most recent first)
        uploads.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'uploads': uploads[:20]  # Return most recent 20
        })
        
    except Exception as e:
        log_error(f"Error fetching PO uploads: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'uploads': []
        }), 500

@app.route('/api/bol-uploads', methods=['GET'])
def get_bol_uploads():
    """Get recent BOL upload records only."""
    try:
        uploads = []
        upload_log_file = 'manual_uploads_log.json'
        
        if os.path.exists(upload_log_file):
            with open(upload_log_file, 'r') as f:
                all_uploads = json.load(f)
            
            # Filter to only BOL uploads
            uploads = [upload for upload in all_uploads if upload.get('upload_type') == 'customer_bol']
        
        # Sort by timestamp (most recent first)
        uploads.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'uploads': uploads[:20]  # Return most recent 20
        })
        
    except Exception as e:
        log_error(f"Error fetching BOL uploads: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'uploads': []
        }), 500

@app.route('/generate-invoice', methods=['GET', 'POST'])
def generate_invoice():
    """Invoice generator page and PDF generation handler."""
    if request.method == 'GET':
        return render_template('generate_invoice.html')
    
    try:
        # Handle POST request - generate invoice PDF
        customer_name = request.form.get('customer_name')
        work_order_number = request.form.get('work_order_number')
        pricing_method = request.form.get('pricing_method')
        
        if not customer_name or not work_order_number or not pricing_method:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Get rate or amount based on pricing method
        if pricing_method == 'cwt':
            rate_or_amount = request.form.get('cwt_rate')
            if not rate_or_amount:
                return jsonify({
                    'success': False,
                    'error': 'CWT rate is required'
                }), 400
        elif pricing_method == 'lot':
            rate_or_amount = request.form.get('lot_amount')
            if not rate_or_amount:
                return jsonify({
                    'success': False,
                    'error': 'Lot amount is required'
                }), 400
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid pricing method'
            }), 400
        
        # Get work order and finished tags data
        work_order_data = json.loads(request.form.get('work_order_data', '{}'))
        finished_tags_data = json.loads(request.form.get('finished_tags_data', '[]'))
        
        # Get BOL number if available
        bol_number = None
        try:
            bol_tracking_file = 'bol_tracking.json'
            if os.path.exists(bol_tracking_file):
                with open(bol_tracking_file, 'r') as f:
                    bol_records = json.load(f)
                    # Find BOL for this work order
                    for record in bol_records:
                        if record.get('work_order_number') == work_order_number:
                            bol_number = record.get('bol_number')
                            break
        except Exception:
            pass  # BOL number is optional
        
        # Prepare invoice data
        invoice_data = {
            'work_order_number': work_order_number,
            'customer_name': customer_name,
            'customer_po': work_order_data.get('customer_po', ''),
            'bol_number': bol_number,
            'pricing_method': pricing_method,
            'rate_or_amount': rate_or_amount,
            'notes': request.form.get('invoice_notes', ''),
            'finished_tags': finished_tags_data
        }
        
        # Generate initial invoice PDF without QR code
        from generate_invoice_pdf import generate_invoice_pdf
        result = generate_invoice_pdf(invoice_data)
        
        # Upload to Google Drive and get shareable link
        drive_url = None
        drive_success = False
        try:
            from drive_utils import DriveUploader
            drive_uploader = DriveUploader()
            
            # Upload to customer PO folder as "Invoice.pdf"
            upload_result = drive_uploader.upload_invoice_pdf(
                result['filepath'], 
                customer_name, 
                work_order_data.get('customer_po', '')
            )
            
            if upload_result and upload_result.get('upload_success'):
                drive_url = upload_result.get('file_link')
                drive_success = True
                log_info(f"Invoice uploaded to Drive: {customer_name}/PO#{work_order_data.get('customer_po')}/Invoice.pdf")
                log_info(f"Drive share URL: {drive_url}")
            else:
                log_warning(f"Drive upload failed: {upload_result.get('error', 'Unknown error')}")
            
        except Exception as drive_error:
            log_warning(f"Local save successful but Google Drive upload failed: {str(drive_error)}")
        
        # Regenerate invoice PDF with QR code if Drive URL is available
        if drive_url:
            log_info("Regenerating invoice PDF with QR code...")
            try:
                result_with_qr = generate_invoice_pdf(invoice_data, drive_url)
                
                # Replace the original PDF with QR-enabled version
                if result_with_qr and os.path.exists(result_with_qr['filepath']):
                    # Re-upload the QR-enabled PDF to replace the original
                    upload_result = drive_uploader.upload_invoice_pdf(
                        result_with_qr['filepath'], 
                        customer_name, 
                        work_order_data.get('customer_po', '')
                    )
                    if upload_result and upload_result.get('upload_success'):
                        log_info("Invoice PDF with QR code uploaded successfully")
                        result = result_with_qr  # Use the QR-enabled version
                    else:
                        log_warning("Failed to upload QR-enabled invoice PDF, keeping original")
            except Exception as e:
                log_warning(f"Error generating invoice PDF with QR code: {str(e)}")
        else:
            log_info("No Drive URL available, invoice PDF generated without QR code")
        
        log_info(f"Invoice generated: {result['filename']} for {customer_name}/WO#{work_order_number}")
        
        return jsonify({
            'success': True,
            'message': f'Invoice {result["invoice_number"]} generated successfully',
            'download_url': f'/download-invoice/{result["invoice_number"]}',
            'drive_link': drive_url,
            'invoice_number': result['invoice_number'],
            'total_amount': result['total']
        })
        
    except Exception as e:
        log_error(f"Error generating invoice: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/customer-work-orders', methods=['GET'])
def get_customer_work_orders():
    """Get work orders for a specific customer."""
    try:
        customer = request.args.get('customer')
        if not customer:
            return jsonify({
                'success': False,
                'error': 'Customer name is required'
            }), 400
        
        work_orders = []
        
        # Read from work orders JSON file
        work_orders_file = 'work_orders.json'
        if os.path.exists(work_orders_file):
            with open(work_orders_file, 'r') as f:
                all_work_orders = json.load(f)
                
            # Filter by customer
            for wo in all_work_orders:
                if wo.get('customer_name', '').lower() == customer.lower():
                    work_orders.append({
                        'work_order_number': wo.get('work_order_number'),
                        'customer_po': wo.get('customer_po'),
                        'date_created': wo.get('timestamp', ''),
                        'status': 'Active'
                    })
        
        # Sort by date (most recent first)
        work_orders.sort(key=lambda x: x.get('date_created', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'work_orders': work_orders
        })
        
    except Exception as e:
        log_error(f"Error fetching customer work orders: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'work_orders': []
        }), 500

@app.route('/api/work-order-details', methods=['GET'])
def get_work_order_details():
    """Get detailed information for a specific work order including finished tags."""
    try:
        work_order_number = request.args.get('work_order')
        if not work_order_number:
            return jsonify({
                'success': False,
                'error': 'Work order number is required'
            }), 400
        
        # Get work order data
        work_order_data = None
        work_orders_file = 'work_orders.json'
        if os.path.exists(work_orders_file):
            with open(work_orders_file, 'r') as f:
                all_work_orders = json.load(f)
                
            for wo in all_work_orders:
                if wo.get('work_order_number') == work_order_number:
                    work_order_data = wo
                    break
        
        if not work_order_data:
            return jsonify({
                'success': False,
                'error': 'Work order not found'
            }), 404
        
        # Get finished tags for this work order
        finished_tags = []
        finished_tags_file = 'finished_tags.json'
        if os.path.exists(finished_tags_file):
            with open(finished_tags_file, 'r') as f:
                all_finished_tags = json.load(f)
                
            # Filter by work order number
            for tag in all_finished_tags:
                if tag.get('work_order_number') == work_order_number:
                    finished_tags.append(tag)
        
        # Get BOL number if available
        bol_number = None
        try:
            bol_tracking_file = 'bol_tracking.json'
            if os.path.exists(bol_tracking_file):
                with open(bol_tracking_file, 'r') as f:
                    bol_records = json.load(f)
                    for record in bol_records:
                        if record.get('work_order_number') == work_order_number:
                            bol_number = record.get('bol_number')
                            break
        except Exception:
            pass
        
        return jsonify({
            'success': True,
            'work_order': work_order_data,
            'finished_tags': finished_tags,
            'bol_number': bol_number
        })
        
    except Exception as e:
        log_error(f"Error fetching work order details: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download-invoice/<invoice_number>')
def download_invoice(invoice_number):
    """Download an invoice PDF by invoice number."""
    try:
        # Find invoice in tracking file
        invoice_tracking_file = 'invoice_tracking.json'
        if not os.path.exists(invoice_tracking_file):
            return "Invoice not found", 404
        
        with open(invoice_tracking_file, 'r') as f:
            invoices = json.load(f)
        
        invoice_record = None
        for invoice in invoices:
            if invoice.get('invoice_number') == invoice_number:
                invoice_record = invoice
                break
        
        if not invoice_record:
            return "Invoice not found", 404
        
        filepath = invoice_record.get('filepath')
        if not filepath or not os.path.exists(filepath):
            return "Invoice file not found", 404
        
        return send_file(filepath, as_attachment=True, download_name=invoice_record.get('filename'))
        
    except Exception as e:
        log_error(f"Error downloading invoice: {str(e)}")
        return f"Error downloading invoice: {str(e)}", 500

@app.route('/invoices')
def invoices_dashboard():
    """Invoice dashboard page."""
    return render_template('invoices_dashboard.html')

@app.route('/api/invoices', methods=['GET'])
def get_invoices():
    """Get all invoice records for the dashboard."""
    try:
        invoices = []
        invoice_tracking_file = 'invoice_tracking.json'
        
        if os.path.exists(invoice_tracking_file):
            with open(invoice_tracking_file, 'r') as f:
                invoices = json.load(f)
        
        # Sort by date (most recent first)
        invoices.sort(key=lambda x: x.get('date_generated', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'invoices': invoices
        })
        
    except Exception as e:
        log_error(f"Error fetching invoices: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'invoices': []
        }), 500

@app.route('/upload-signed-bol', methods=['GET', 'POST'])
def upload_signed_bol():
    """Upload signed BOL page and handler."""
    if request.method == 'GET':
        return render_template('upload_signed_bol.html')
    
    try:
        # Get form data
        customer_name = request.form.get('customer_name')
        po_number = request.form.get('po_number')
        bol_number = request.form.get('bol_number')
        
        # Validate required fields
        if not all([customer_name, po_number, bol_number]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
        
        # Validate BOL number format
        import re
        if not re.match(r'^BL\d{6}$', bol_number):
            return jsonify({
                'success': False,
                'error': 'BOL number must be in format BL###### (6 digits)'
            }), 400
        
        # Handle file upload
        if 'signed_bol_file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['signed_bol_file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Validate file type
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': 'Only PDF, JPG, and PNG files are allowed'
            }), 400
        
        # Save file temporarily
        temp_filename = f"signed_bol_{bol_number}_{int(time.time())}{file_ext}"
        temp_filepath = os.path.join('uploads', temp_filename)
        
        # Ensure uploads directory exists
        os.makedirs('uploads', exist_ok=True)
        file.save(temp_filepath)
        
        # Upload to Google Drive
        uploader = DriveUploader()
        upload_result = uploader.upload_signed_bol(
            temp_filepath, customer_name, po_number, bol_number
        )
        
        # Clean up temporary file
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        
        if upload_result.get('upload_success'):
            # Save upload record
            upload_record = {
                'timestamp': datetime.now().isoformat(),
                'customer_name': customer_name,
                'po_number': po_number,
                'bol_number': bol_number,
                'filename': upload_result.get('filename'),
                'file_id': upload_result.get('file_id'),
                'file_link': upload_result.get('file_link'),
                'folder_path': upload_result.get('folder_path'),
                'uploaded_by': 'system'  # Could be enhanced with user authentication
            }
            
            save_signed_bol_record(upload_record)
            
            log_info(f"Signed BOL {bol_number} uploaded successfully for {customer_name} PO#{po_number}")
            
            return jsonify({
                'success': True,
                'message': f'Signed BOL successfully uploaded and filed to PO#{po_number}',
                'upload_record': upload_record
            })
        else:
            return jsonify({
                'success': False,
                'error': f"Upload failed: {upload_result.get('error', 'Unknown error')}"
            }), 500
            
    except Exception as e:
        log_error(f"Error uploading signed BOL: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Server error: {str(e)}"
        }), 500

def save_signed_bol_record(record):
    """Save signed BOL upload record to tracking file."""
    tracking_file = 'signed_bol_tracking.json'
    
    # Load existing records
    records = []
    if os.path.exists(tracking_file):
        try:
            with open(tracking_file, 'r') as f:
                records = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            records = []
    
    # Add new record at the beginning (most recent first)
    records.insert(0, record)
    
    # Keep only the last 100 records
    records = records[:100]
    
    # Save updated records
    with open(tracking_file, 'w') as f:
        json.dump(records, f, indent=2)

@app.route('/api/signed-bol-uploads', methods=['GET'])
def get_signed_bol_uploads():
    """Get recent signed BOL upload records."""
    try:
        tracking_file = 'signed_bol_tracking.json'
        records = []
        
        if os.path.exists(tracking_file):
            with open(tracking_file, 'r') as f:
                records = json.load(f)
        
        return jsonify({
            'success': True,
            'uploads': records
        })
        
    except Exception as e:
        log_error(f"Error fetching signed BOL uploads: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'uploads': []
        }), 500

@app.route('/audit-invoice-integrity')
def audit_invoice_integrity():
    """Run comprehensive invoice data integrity audit and display results."""
    try:
        # Import the auditor class
        import sys
        sys.path.append('.')
        from audit_invoice_integrity import InvoiceIntegrityAuditor
        
        # Run the audit
        auditor = InvoiceIntegrityAuditor()
        report = auditor.run_full_audit()
        
        # Format results for web display
        return render_template('audit_results.html', report=report)
        
    except Exception as e:
        log_error(f"Error running invoice audit: {str(e)}")
        return f"Audit failed: {str(e)}", 500

@app.route('/api/audit-invoice-integrity')
def api_audit_invoice_integrity():
    """API endpoint for invoice integrity audit - returns JSON results."""
    try:
        from audit_invoice_integrity import InvoiceIntegrityAuditor
        
        auditor = InvoiceIntegrityAuditor()
        report = auditor.run_full_audit()
        
        return jsonify(report)
        
    except Exception as e:
        log_error(f"Error running invoice audit API: {str(e)}")
        return jsonify({
            'error': str(e),
            'summary': {'data_integrity_status': 'ERROR'}
        }), 500

@app.route('/quote-generator')
def quote_generator():
    """Quote generator page."""
    return render_template('quote_generator.html')

@app.route('/api/create-quote', methods=['POST'])
def api_create_quote():
    """Legacy API endpoint for quote creation - redirects to new unified system."""
    try:
        quote_data = request.get_json()
        
        # Transform legacy format to new unified format
        transformed_data = {
            'quote_number': quote_data.get('quoteNumber'),
            'customer_name': quote_data.get('customerName'),
            'date_required': quote_data.get('quoteValidUntil', ''),
            'process_type': quote_data.get('processType'),
            'packaging_instructions': '',
            'pricing_method': quote_data.get('pricingMethod'),
            'unit_price': quote_data.get('unitPrice', 0),
            'slitting_jobs': [],
            'cut_to_length_jobs': []
        }
        
        # Use the new unified create_quote function
        return create_quote_unified(transformed_data)
        
    except Exception as e:
        log_error(f"Error in legacy quote creation: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def create_quote_unified(data):
    """Unified quote creation function."""
    try:
        # Generate quote record
        quote_record = {
            'quote_number': data['quote_number'],
            'customer_name': data['customer_name'],
            'date_created': datetime.now().isoformat(),
            'date_required': data['date_required'],
            'process_type': data['process_type'],
            'packaging_instructions': data['packaging_instructions'],
            'pricing_method': data['pricing_method'],
            'unit_price': float(data['unit_price']) if data['unit_price'] else 0.0,
            'status': 'Active',  # All new quotes start as Active
            'po_number': '',  # Empty until linked to work order
            'linked_work_order': '',  # Empty until realized
            'slitting_jobs': data.get('slitting_jobs', []),
            'cut_to_length_jobs': data.get('cut_to_length_jobs', [])
        }
        
        # Save to tracking file
        save_quote_record_unified(quote_record)
        
        # Also save to Google Sheets if available
        try:
            save_quote_to_sheets(quote_record)
        except Exception as e:
            log_warning(f"Could not save quote to Google Sheets: {str(e)}")
        
        log_info(f"Quote {quote_record['quote_number']} created successfully")
        
        return jsonify({
            'success': True,
            'quote_number': quote_record['quote_number']
        })
        
    except Exception as e:
        log_error(f"Error creating quote: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def save_quote_record_unified(record):
    """Save quote record to local tracking file."""
    tracking_file = 'quote_tracking.json'
    
    # Load existing records
    records = []
    if os.path.exists(tracking_file):
        try:
            with open(tracking_file, 'r') as f:
                records = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            records = []
    
    # Add new record at the beginning (most recent first)
    records.insert(0, record)
    
    # Keep only the last 500 records
    records = records[:500]
    
    # Save updated records
    with open(tracking_file, 'w') as f:
        json.dump(records, f, indent=2)

@app.route('/api/quotes', methods=['GET'])
def get_quotes():
    """Get all quote records."""
    try:
        tracking_file = 'quote_tracking.json'
        records = []
        
        if os.path.exists(tracking_file):
            with open(tracking_file, 'r') as f:
                records = json.load(f)
        
        return jsonify({
            'success': True,
            'quotes': records
        })
        
    except Exception as e:
        log_error(f"Error fetching quotes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'quotes': []
        }), 500

@app.route('/api/extract-quote-text', methods=['POST'])
def extract_quote_from_text():
    """Extract quote information from email text using OpenAI."""
    try:
        data = request.get_json()
        text_content = data.get('text', '').strip()
        
        if not text_content:
            return jsonify({
                'success': False,
                'error': 'No text content provided'
            }), 400
        
        # Check if OpenAI API key is available
        openai_key = os.environ.get('OPENAI_API_KEY')
        if not openai_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured'
            }), 500
        
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        # Create extraction prompt
        extraction_prompt = f"""
        Extract quote information from the following email/text content. Return a JSON object with these fields:
        
        - customer_po: Customer purchase order number
        - customer_name: Customer company name
        - material_description: Description of material (e.g., "250 x 25 x Coil")
        - process_type: Manufacturing process (Slitting, Cut-to-Length, or Both)
        - items: Array of items with fields: thickness, width, length, weight, quantity
        - pricing_method: CWT or LOT
        - due_date: When quote is needed by
        
        Text content:
        {text_content}
        
        Return only valid JSON. If information is not found, use null for that field.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=[
                {"role": "system", "content": "You are a quote extraction expert. Extract manufacturing quote information and return only valid JSON."},
                {"role": "user", "content": extraction_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        
        log_info(f"Successfully extracted quote data from text")
        
        return jsonify({
            'success': True,
            'extracted_data': extracted_data
        })
        
    except Exception as e:
        log_error(f"Error extracting quote from text: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/extract-quote-file', methods=['POST'])
def extract_quote_from_file():
    """Extract quote information from uploaded file using OpenAI."""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Check if OpenAI API key is available
        openai_key = os.environ.get('OPENAI_API_KEY')
        if not openai_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured'
            }), 500
        
        from openai import OpenAI
        import base64
        
        client = OpenAI(api_key=openai_key)
        
        # Handle different file types
        file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        if file_extension == 'pdf':
            # Extract text from PDF first
            import fitz  # PyMuPDF
            
            # Save uploaded file temporarily
            temp_path = f"temp_quote_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            file.save(temp_path)
            
            try:
                # Extract text from PDF
                pdf_doc = fitz.open(temp_path)
                text_content = ""
                for page in pdf_doc:
                    text_content += page.get_text()
                pdf_doc.close()
                
                # Use text extraction method
                extraction_prompt = f"""
                Extract quote information from the following PDF content. Return a JSON object with these fields:
                
                - customer_po: Customer purchase order number
                - customer_name: Customer company name
                - material_description: Description of material (e.g., "250 x 25 x Coil")
                - process_type: Manufacturing process (Slitting, Cut-to-Length, or Both)
                - items: Array of items with fields: thickness, width, length, weight, quantity
                - pricing_method: CWT or LOT
                - due_date: When quote is needed by
                
                PDF content:
                {text_content}
                
                Return only valid JSON. If information is not found, use null for that field.
                """
                
                response = client.chat.completions.create(
                    model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                    messages=[
                        {"role": "system", "content": "You are a quote extraction expert. Extract manufacturing quote information and return only valid JSON."},
                        {"role": "user", "content": extraction_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                
                extracted_data = json.loads(response.choices[0].message.content)
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        elif file_extension in ['jpg', 'jpeg', 'png']:
            # Handle image files with vision API
            file_content = file.read()
            base64_image = base64.b64encode(file_content).decode('utf-8')
            
            response = client.chat.completions.create(
                model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Extract quote information from this image. Return a JSON object with these fields:
                                
                                - customer_po: Customer purchase order number
                                - customer_name: Customer company name
                                - material_description: Description of material (e.g., "250 x 25 x Coil")
                                - process_type: Manufacturing process (Slitting, Cut-to-Length, or Both)
                                - items: Array of items with fields: thickness, width, length, weight, quantity
                                - pricing_method: CWT or LOT
                                - due_date: When quote is needed by
                                
                                Return only valid JSON. If information is not found, use null for that field."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/{file_extension};base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
        else:
            return jsonify({
                'success': False,
                'error': f'Unsupported file type: {file_extension}'
            }), 400
        
        log_info(f"Successfully extracted quote data from {file_extension} file")
        
        return jsonify({
            'success': True,
            'extracted_data': extracted_data
        })
        
    except Exception as e:
        log_error(f"Error extracting quote from file: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Duplicate functions removed - using the ones defined earlier

@app.route('/work_orders.json')
def work_orders_json():
    """Serve work orders data as JSON for frontend consumption."""
    try:
        if os.path.exists('work_orders.json'):
            with open('work_orders.json', 'r') as f:
                work_orders = json.load(f)
            return jsonify(work_orders)
        else:
            return jsonify([])
    except Exception as e:
        log_error(f"Error serving work orders JSON: {e}")
        return jsonify([])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
