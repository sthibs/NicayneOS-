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
from flask import Flask, request, render_template, jsonify, flash, redirect, url_for, send_file, Response, stream_with_context, session
from werkzeug.utils import secure_filename

# Import user authentication system
from utils.user_registry import get_user_by_email
from bol_extractor.extractor import BOLExtractor

# OAuth imports for Google integration
from requests_oauthlib import OAuth2Session
from bol_extractor.config import Config
from utils.prompt_loader import PromptLoader
from drive_utils import DriveUploader
from email_utils import send_email_with_attachment

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

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
    print(msg)
    log_queue.put(msg)

def log_info(msg): 
    live_log(f"INFO: {msg}")

def log_warning(msg): 
    live_log(f"WARNING: {msg}")

def log_error(msg): 
    live_log(f"ERROR: {msg}")

def send_document_email(pdf_path, document_type, customer_name, to_email=None):
    """Helper function to send document emails with PDF attachments"""
    try:
        if not to_email:
            to_email = os.environ.get('DEFAULT_SEND_TO_EMAIL')
        
        if to_email:
            subject = f"New {document_type} - {customer_name}"
            body = f"Please find attached the {document_type} for {customer_name}."
            send_email_with_attachment(to_email, subject, body, pdf_path)
            log_info(f"Email sent for {document_type} to {to_email}")
        else:
            log_warning(f"No email address configured for {document_type}")
    except Exception as e:
        log_error(f"Failed to send email for {document_type}: {str(e)}")

# Global variables
live_log_stream = queue.Queue()

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Authentication helper functions
def login_required(f):
    """Decorator to require login for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    """Decorator to require specific role for routes"""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            
            user_role = session['user'].get('role', '')
            
            # Admin can access everything
            if user_role == 'admin':
                return f(*args, **kwargs)
            
            # Check if user has the required role
            if user_role != required_role:
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_user():
    """Get the current logged-in user"""
    return session.get('user', None)

# Authentication Routes
@app.route('/login')
def login():
    """Start Google OAuth login flow"""
    # Build dynamic redirect URI based on current environment
    base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
    redirect_uri = f"{base_url}/oauth2callback"
    
    google = OAuth2Session(
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        redirect_uri=redirect_uri,
        scope=['https://www.googleapis.com/auth/userinfo.email']
    )
    authorization_url, state = google.authorization_url(
        'https://accounts.google.com/o/oauth2/auth',
        access_type='offline',
        prompt='consent'
    )
    session['oauth_state'] = state
    session['redirect_uri'] = redirect_uri  # Store for callback use
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth callback and log user in"""
    try:
        # Use the stored redirect URI from the login session
        redirect_uri = session.get('redirect_uri')
        if not redirect_uri:
            # Fallback to dynamic generation if not stored
            base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
            redirect_uri = f"{base_url}/oauth2callback"
        
        google = OAuth2Session(
            client_id=os.environ['GOOGLE_CLIENT_ID'],
            redirect_uri=redirect_uri,
            state=session.get('oauth_state')
        )
        token = google.fetch_token(
            'https://oauth2.googleapis.com/token',
            client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
            authorization_response=request.url
        )
        session['oauth_token'] = token

        user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()
        email = user_info.get('email')

        # Match email to registered system users
        user_record = get_user_by_email(email)

        if not user_record:
            flash('Unauthorized: Your email is not registered for this system', 'error')
            return redirect(url_for('login'))

        session['user'] = {
            'email': user_record['email'],
            'role': user_record['role'],
            'name': user_record['name']
        }

        flash(f'Welcome, {user_record["name"]}!', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        flash(f'Login failed: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """Logout current user"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Main page - redirect to login if not authenticated."""
    if 'user' not in session:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main system dashboard"""
    user = session['user']
    return render_template('dashboard.html', user=user)

@app.route('/user-admin')
@login_required
@role_required('admin')
def user_admin():
    """User administration page (admin only)"""
    from utils.user_registry import get_all_users
    users = get_all_users()
    return render_template('user_admin.html', users=users)

@app.route('/user-directory')
@login_required
@role_required('admin')
def user_directory():
    """User directory dashboard showing all registered users"""
    from utils.user_registry import get_all_users
    users = get_all_users()
    return render_template('user_directory.html', users=users)

@app.route('/bol-extractor')
@login_required
def bol_extractor():
    """BOL Extractor page for PDF upload and processing."""
    return render_template('bol_extractor.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle PDF file upload and processing."""
    logger.info("Upload route called")
    logger.info(f"Request files: {list(request.files.keys())}")
    logger.info(f"Request form: {dict(request.form)}")
    
    if 'file' not in request.files:
        logger.info("No file in request.files")
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename or "unknown.pdf")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Test if we reach this point
            flash(f'File {filename} uploaded successfully! Now starting BOL extraction...', 'info')
            logger.info(f"File saved to: {filepath}")
            
            # Initialize BOL extractor and process the PDF
            try:
                logger.info(f"Starting BOL extraction for {filename}")
                
                from bol_extractor.config import Config
                from bol_extractor.extractor import BOLExtractor
                
                logger.info("Importing BOL extractor modules...")
                config = Config()
                logger.info("Config created successfully")
                
                extractor = BOLExtractor(config)
                logger.info("BOL extractor initialized successfully")
                
                logger.info(f"Processing PDF at {filepath}")
                result = extractor.process_bol_pdf(filepath)
                logger.info(f"Processing result: {result}")
                
                if result.get('success'):
                    # Get the coils data from the extraction result
                    coils_data = result.get('data', {}).get('coils', [])
                    
                    if coils_data:
                        # Process each coil individually through the flattener and writer
                        coils_written = 0
                        from bol_extractor.json_flattener import JSONFlattener
                        from bol_extractor.google_sheets_writer import GoogleSheetsWriter
                        
                        flattener = JSONFlattener()
                        sheets_writer = GoogleSheetsWriter(config)
                        
                        for i, coil in enumerate(coils_data, 1):
                            try:
                                # Flatten individual coil data
                                flattened_coil = flattener.flatten_bol_data(coil)
                                
                                # Write to Google Sheets
                                sheet_result = sheets_writer.append_bol_data(flattened_coil)
                                
                                if sheet_result.get('success'):
                                    coils_written += 1
                                    logger.info(f"Coil {i} written to sheet row {sheet_result.get('row_number')}")
                                else:
                                    logger.error(f"Failed to write coil {i}: {sheet_result.get('error')}")
                                    
                            except Exception as coil_error:
                                logger.error(f"Error processing coil {i}: {str(coil_error)}")
                        
                        flash(f'File {filename} processed successfully! Extracted {len(coils_data)} coils, wrote {coils_written} to sheets.', 'success')
                        logger.info(f"BOL extraction completed: {len(coils_data)} coils extracted, {coils_written} written")
                    else:
                        flash(f'File {filename} processed but no coil data found.', 'warning')
                        logger.warning(f"No coil data found in extraction result for {filename}")
                else:
                    error_msg = result.get('error', 'Unknown processing error')
                    flash(f'File uploaded but processing failed: {error_msg}', 'warning')
                    logger.error(f"BOL extraction failed for {filename}: {error_msg}")
                    
            except Exception as extraction_error:
                flash(f'File uploaded but extraction failed: {str(extraction_error)}', 'warning')
                logger.error(f"BOL extraction error for {filename}: {str(extraction_error)}")
                import traceback
                traceback.print_exc()
            
            return redirect(url_for('dashboard'))
                
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(url_for('bol_extractor'))
    
    flash('Invalid file type. Please upload a PDF file.')
    return redirect(request.url)

# Additional routes that templates are expecting
@app.route('/work-order-form')
@login_required
def work_order_form():
    """Work order form for creating manufacturing orders."""
    return render_template('work_order_form.html')

@app.route('/finished-tag')
@login_required
def finished_tag():
    """Finished tag form"""
    return render_template('finished_tag.html')

@app.route('/create-user')
@login_required
@role_required('admin')
def create_user():
    """Create user placeholder"""
    return "<h1>Create User</h1><p>This feature will be implemented soon.</p>"

@app.route('/control')
@login_required
@role_required('admin')
def control():
    """Control panel placeholder"""
    return "<h1>Control Panel</h1><p>This feature will be implemented soon.</p>"

@app.route('/api/lookup-heat-numbers', methods=['POST'])
@login_required
def lookup_heat_numbers():
    """API endpoint to lookup heat numbers from incoming tag numbers"""
    try:
        data = request.get_json()
        incoming_tags = data.get('incoming_tags', '').strip()
        
        if not incoming_tags:
            return jsonify({'heat_numbers': ''})
        
        # Parse incoming tags
        import re
        tag_list = re.split(r'[,\n\r]+', incoming_tags)
        tag_list = [tag.strip().upper() for tag in tag_list if tag.strip()]
        
        if not tag_list:
            return jsonify({'heat_numbers': ''})
        
        # Initialize Google Sheets connection using existing infrastructure
        import os
        import json
        import gspread
        from google.oauth2.service_account import Credentials
        
        try:
            # Set up credentials
            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            credentials = Credentials.from_service_account_info(
                json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_KEY_NMP']), scopes=SCOPES
            )
            
            client = gspread.authorize(credentials)
            spreadsheet = client.open_by_key(os.environ['SPREADSHEET_ID_NMP'])
            
            # Access IN_PROCESS worksheet
            in_process_sheet = spreadsheet.worksheet("IN_PROCESS")
            
            # Get all data from IN_PROCESS sheet
            in_process_data = in_process_sheet.get_all_records()
            
            # Find matching heat numbers
            found_heat_numbers = []
            
            for row in in_process_data:
                # Look for tag number in various possible column names
                tag_value = None
                for col_name in ['Tag #', 'Tag Number', 'tag_number', 'Customer Tag', 'customer_tag']:
                    if col_name in row and row[col_name]:
                        tag_value = str(row[col_name]).strip().upper()
                        break
                
                if tag_value and tag_value in tag_list:
                    # Look for heat number in various possible column names
                    heat_number = None
                    for heat_col in ['Heat Number', 'Heat', 'heat_number', 'heat']:
                        if heat_col in row and row[heat_col]:
                            heat_number = str(row[heat_col]).strip()
                            break
                    
                    if heat_number and heat_number not in found_heat_numbers:
                        found_heat_numbers.append(heat_number)
            
            return jsonify({'heat_numbers': ', '.join(found_heat_numbers)})
            
        except Exception as e:
            logger.error(f"Error accessing Google Sheets: {str(e)}")
            return jsonify({'heat_numbers': '', 'error': 'Unable to access inventory data'})
        
    except Exception as e:
        logger.error(f"Error in heat number lookup: {str(e)}")
        return jsonify({'heat_numbers': '', 'error': 'Lookup failed'})

@app.route('/invoices')
@login_required
def invoices_dashboard():
    """Invoice dashboard page."""
    return render_template('invoices_dashboard.html')

@app.route('/generate-invoice', methods=['GET', 'POST'])
@login_required
def generate_invoice():
    """Invoice generator page and PDF generation handler."""
    if request.method == 'GET':
        return render_template('generate_invoice.html')
    
    try:
        # Handle invoice generation
        invoice_data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Generate invoice PDF
        from generate_invoice_pdf import generate_invoice_pdf
        pdf_path = generate_invoice_pdf(invoice_data)
        
        if pdf_path and os.path.exists(pdf_path):
            return send_file(pdf_path, as_attachment=True)
        else:
            return jsonify({'error': 'Failed to generate invoice PDF'}), 500
            
    except Exception as e:
        logger.error(f"Error generating invoice: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/suppliers')
@login_required
def get_suppliers():
    """Get all active suppliers."""
    try:
        with open('supplier_prompts.json', 'r') as f:
            suppliers = json.load(f)
        return jsonify(suppliers)
    except FileNotFoundError:
        return jsonify({})
    except Exception as e:
        logger.error(f"Error loading suppliers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/audit-invoice-integrity')
@login_required
@role_required('admin')
def audit_invoice_integrity():
    """Run comprehensive invoice data integrity audit and display results."""
    try:
        from audit_invoice_integrity import InvoiceIntegrityAuditor
        auditor = InvoiceIntegrityAuditor()
        audit_results = auditor.run_full_audit()
        
        return render_template('audit_results.html', results=audit_results)
    except Exception as e:
        logger.error(f"Error running invoice audit: {str(e)}")
        return f"<h1>Audit Error</h1><p>{str(e)}</p>"

@app.route('/work_orders.json')
@login_required
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
        logger.error(f"Error loading work orders: {str(e)}")
        return jsonify([])

@app.route('/api/invoices')
@login_required
def get_invoices():
    """Get all invoice records for the dashboard."""
    try:
        if os.path.exists('invoice_tracking.json'):
            with open('invoice_tracking.json', 'r') as f:
                invoices = json.load(f)
            return jsonify(invoices)
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"Error loading invoices: {str(e)}")
        return jsonify([])

@app.route('/work-order-history')
@login_required
def work_order_history():
    """Display work order history page"""
    return render_template('work_order_history.html')

@app.route('/bol-history')
@login_required
def bol_history():
    """BOL history viewer page."""
    return render_template('bol_viewer.html')

@app.route('/history')
@login_required
def history():
    """Display job history page."""
    return render_template('history.html')

@app.route('/api/bol-history')
@login_required
def get_bol_history():
    """Get all BOL history records."""
    try:
        if os.path.exists('bol_tracking.json'):
            with open('bol_tracking.json', 'r') as f:
                bol_history = json.load(f)
            return jsonify(bol_history)
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"Error loading BOL history: {str(e)}")
        return jsonify([])

@app.route('/bol-generator', methods=['GET', 'POST'])
@login_required
def bol_generator():
    """Bill of Lading generator page."""
    if request.method == 'GET':
        return render_template('bol_generator.html')
    
    # Handle BOL generation
    try:
        data = request.get_json() if request.is_json else request.form
        # BOL generation logic would go here
        return jsonify({'success': True, 'message': 'BOL generated successfully'})
    except Exception as e:
        logger.error(f"Error generating BOL: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/finished-tags-archive')
@login_required
def finished_tags_archive():
    """Display finished tags archive viewer."""
    try:
        # Load finished tags data
        finished_tags = []
        total_weight = 0
        total_tags = 0
        
        if os.path.exists('finished_tags.json'):
            with open('finished_tags.json', 'r') as f:
                finished_tags = json.load(f)
            
            # Calculate totals
            total_tags = len(finished_tags)
            for tag in finished_tags:
                weight = tag.get('total_weight', 0)
                if isinstance(weight, (int, float)):
                    total_weight += weight
        
        return render_template('finished_tags_archive.html', 
                             finished_tags=finished_tags,
                             total_weight=total_weight,
                             total_tags=total_tags)
    except Exception as e:
        logger.error(f"Error loading finished tags archive: {str(e)}")
        return render_template('finished_tags_archive.html', 
                             finished_tags=[],
                             total_weight=0,
                             total_tags=0)

@app.route('/api/work-orders')
@login_required
def get_work_orders():
    """Get available work orders for BOL generation."""
    try:
        if os.path.exists('work_orders.json'):
            with open('work_orders.json', 'r') as f:
                work_orders = json.load(f)
            return jsonify(work_orders)
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"Error loading work orders: {str(e)}")
        return jsonify([])

@app.route('/manual-upload', methods=['GET', 'POST'])
@login_required
def manual_upload():
    """Manual upload page and handler for customer BOLs and original POs."""
    if request.method == 'GET':
        return render_template('manual_upload.html')
    
    try:
        # Handle manual file upload
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join('uploads', filename)
            file.save(upload_path)
            
            # Save upload record
            upload_record = {
                'filename': filename,
                'upload_date': datetime.now().isoformat(),
                'type': 'manual_upload',
                'customer': request.form.get('customer', ''),
                'document_type': request.form.get('document_type', '')
            }
            
            # Save to tracking file
            tracking_file = 'manual_uploads.json'
            if os.path.exists(tracking_file):
                with open(tracking_file, 'r') as f:
                    tracking_data = json.load(f)
            else:
                tracking_data = []
            
            tracking_data.append(upload_record)
            
            with open(tracking_file, 'w') as f:
                json.dump(tracking_data, f, indent=2)
            
            flash('File uploaded successfully')
            return redirect(url_for('manual_upload'))
        else:
            flash('Invalid file type. Please upload a PDF file.')
            return redirect(request.url)
            
    except Exception as e:
        logger.error(f"Error in manual upload: {str(e)}")
        flash('Upload failed')
        return redirect(request.url)

@app.route('/api/bol-uploads')
@login_required
def get_bol_uploads():
    """Get recent BOL upload records."""
    try:
        if os.path.exists('manual_uploads.json'):
            with open('manual_uploads.json', 'r') as f:
                uploads = json.load(f)
            # Filter for BOL uploads only
            bol_uploads = [upload for upload in uploads if upload.get('document_type') == 'bol']
            return jsonify(bol_uploads)
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"Error loading BOL uploads: {str(e)}")
        return jsonify([])

@app.route('/quotes')
@login_required
def quotes():
    """Quotes dashboard page."""
    return render_template('quotes_dashboard.html')

@app.route('/quotes/form')
@login_required
def quotes_form():
    """Quote creation form page with AI generator."""
    return render_template('quote_form.html')

@app.route('/api/get-quotes')
@login_required
def api_get_quotes():
    """API endpoint to get all quotes with lifecycle status"""
    try:
        if os.path.exists('quotes.json'):
            with open('quotes.json', 'r') as f:
                quotes = json.load(f)
            return jsonify(quotes)
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"Error loading quotes: {str(e)}")
        return jsonify([])

@app.route('/purchase-orders')
@login_required
def purchase_orders():
    """Purchase Orders management page."""
    return render_template('purchase_orders.html')

@app.route('/api/po-uploads')
@login_required
def get_po_uploads():
    """Get recent PO upload records only."""
    try:
        if os.path.exists('manual_uploads.json'):
            with open('manual_uploads.json', 'r') as f:
                uploads = json.load(f)
            # Filter for PO uploads only
            po_uploads = [upload for upload in uploads if upload.get('document_type') == 'po']
            return jsonify(po_uploads)
        else:
            return jsonify([])
    except Exception as e:
        logger.error(f"Error loading PO uploads: {str(e)}")
        return jsonify([])

@app.route('/upload-signed-bol', methods=['GET', 'POST'])
@login_required
def upload_signed_bol():
    """Upload signed BOL page and handler."""
    if request.method == 'GET':
        return render_template('upload_signed_bol.html')
    
    try:
        # Handle signed BOL upload
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join('uploads', filename)
            file.save(upload_path)
            
            # Save upload record
            upload_record = {
                'filename': filename,
                'upload_date': datetime.now().isoformat(),
                'type': 'signed_bol'
            }
            
            try:
                if os.path.exists('bol_tracking.json'):
                    with open('bol_tracking.json', 'r') as f:
                        tracking_data = json.load(f)
                else:
                    tracking_data = []
                
                tracking_data.append(upload_record)
                
                with open('bol_tracking.json', 'w') as f:
                    json.dump(tracking_data, f, indent=2)
                
                flash('Signed BOL uploaded successfully')
                return redirect(url_for('upload_signed_bol'))
                
            except Exception as e:
                logger.error(f"Error saving BOL tracking data: {str(e)}")
                flash('File uploaded but tracking failed')
                return redirect(request.url)
        else:
            flash('Invalid file type. Please upload a PDF file.')
            return redirect(request.url)
            
    except Exception as e:
        logger.error(f"Error uploading signed BOL: {str(e)}")
        flash('Upload failed')
        return redirect(request.url)

@app.route('/summary')
@login_required
def summary():
    """Display extraction summary page."""
    return render_template('summary.html')

@app.route('/quotes-pos', methods=['GET', 'POST'])
@login_required
def quotes_pos():
    """Quotes & Purchase Orders page and PO upload handler."""
    return render_template('quotes_pos.html')

@app.route('/generate-bol', methods=['POST'])
@login_required
def generate_bol():
    """Generate Bill of Lading PDF for a work order."""
    return jsonify({'success': True, 'message': 'BOL generation not yet implemented'})

@app.route('/dashboard-upload', methods=['POST'])
@login_required
def dashboard_upload():
    """Handle file uploads from dashboard."""
    return jsonify({'success': True, 'message': 'Dashboard upload handler'})

@app.route('/health')
def health():
    """Health check endpoint - returns JSON for API calls."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/health-status')
def health_status_page():
    """Health status page - returns HTML for browser access."""
    health_data = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': ['Flask App', 'Database', 'File System']
    }
    return render_template('health.html', health=health_data)

@app.route('/stream')
@login_required
def stream_logs():
    """Stream live logs using Server-Sent Events."""
    return "Event stream not yet implemented", 501

@app.route('/regenerate-finished-tag/<tag_id>')
@login_required
def regenerate_finished_tag_pdf(tag_id):
    """Regenerate and download PDF for a finished tag."""
    return "PDF regeneration not yet implemented", 501

@app.route('/finished-tags')
@login_required
def finished_tags():
    """Finished tags management page."""
    return render_template('finished_tags_archive.html')

@app.route('/control-panel')
@login_required
def control_panel():
    """Admin control panel for system settings."""
    return render_template('control.html')

@app.route('/download-backup')
@app.route('/download-backup/<filename>')
@login_required
def download_backup(filename=None):
    """Download JSON backup file."""
    return "Backup download not yet implemented", 501

@app.route('/api/signed-bol-uploads')
@login_required
def get_signed_bol_uploads():
    """Get recent signed BOL upload records."""
    return jsonify([])

@app.route('/api/audit-invoice-integrity')
@login_required
def api_audit_invoice_integrity():
    """API endpoint for invoice integrity audit - returns JSON results."""
    return jsonify({'status': 'not_implemented'})

@app.route('/api/create-quote', methods=['POST'])
@login_required
def api_create_quote():
    """Legacy API endpoint for quote creation."""
    return jsonify({'success': False, 'message': 'Quote creation not yet implemented'})

@app.route('/api/extract-quote-file', methods=['POST'])
@login_required
def extract_quote_from_file():
    """Extract quote information from uploaded file using OpenAI."""
    return jsonify({'success': False, 'message': 'Quote extraction not yet implemented'})

@app.route('/api/extract-quote-text', methods=['POST'])
@login_required
def extract_quote_from_text():
    """Extract quote information from email text using OpenAI."""
    return jsonify({'success': False, 'message': 'Quote extraction not yet implemented'})

@app.route('/create-quote', methods=['POST'])
@login_required
def create_quote():
    """Create a new quote with lifecycle tracking"""
    return jsonify({'success': False, 'message': 'Quote creation not yet implemented'})

@app.route('/extract-quote-from-file', methods=['POST'])
@login_required
def extract_quote_from_file_legacy():
    """Legacy extract quote from file endpoint."""
    return jsonify({'success': False, 'message': 'Quote extraction not yet implemented'})

@app.route('/extract-quote-from-text', methods=['POST'])
@login_required
def extract_quote_from_text_legacy():
    """Legacy extract quote from text endpoint."""
    return jsonify({'success': False, 'message': 'Quote extraction not yet implemented'})

@app.route('/inventory-dashboard')
@login_required
def inventory_dashboard():
    """Inventory Dashboard - main interface for viewing and printing inventory reports."""
    return render_template('inventory_dashboard.html')

def load_inventory_data(sheet_name, customer_name):
    """Load and filter inventory data from Google Sheets by customer name."""
    try:
        from bol_extractor.config import Config
        import gspread
        import json
        from google.oauth2.service_account import Credentials
        
        # Initialize configuration
        config = Config()
        
        # Set up Google Sheets credentials
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(
            json.loads(config.google_service_account_key), scopes=SCOPES
        )
        
        client = gspread.authorize(credentials)
        sheet = client.open_by_key(config.spreadsheet_id)
        
        # Get the specific worksheet
        worksheet = sheet.worksheet(sheet_name)
        
        # Get all records
        all_records = worksheet.get_all_records()
        
        # Filter by customer (case-insensitive)
        filtered_records = []
        for record in all_records:
            customer_field = str(record.get('Customer', '')).strip().lower()
            if customer_name.lower() in customer_field or customer_field in customer_name.lower():
                filtered_records.append(record)
        
        return filtered_records
        
    except Exception as e:
        log_error(f"Error loading inventory data from {sheet_name}: {str(e)}")
        return []

@app.route('/inventory-report/unprocessed/<customer_name>')
@login_required
def inventory_report_unprocessed(customer_name):
    """Generate unprocessed inventory report for specific customer."""
    inventory_data = load_inventory_data("UNPROCESSED_INVENTORY", customer_name)
    return render_template('inventory_report.html',
                         customer_name=customer_name,
                         status="Unprocessed",
                         inventory_data=inventory_data,
                         current_date=datetime.now().strftime('%B %d, %Y'))

@app.route('/inventory-report/in-process/<customer_name>')
@login_required
def inventory_report_in_process(customer_name):
    """Generate in-process inventory report for specific customer."""
    inventory_data = load_inventory_data("IN_PROCESS", customer_name)
    return render_template('inventory_report.html',
                         customer_name=customer_name,
                         status="In-Process",
                         inventory_data=inventory_data,
                         current_date=datetime.now().strftime('%B %d, %Y'))

@app.route('/inventory-report/processed/<customer_name>')
@login_required
def inventory_report_processed(customer_name):
    """Generate processed inventory report for specific customer."""
    inventory_data = load_inventory_data("PROCESSED", customer_name)
    return render_template('inventory_report.html',
                         customer_name=customer_name,
                         status="Processed",
                         inventory_data=inventory_data,
                         current_date=datetime.now().strftime('%B %d, %Y'))

@app.route('/inventory-report/all/<customer_name>')
@login_required
def inventory_report_all(customer_name):
    """Generate unified inventory report (all statuses) for specific customer."""
    unprocessed_data = load_inventory_data("UNPROCESSED_INVENTORY", customer_name)
    in_process_data = load_inventory_data("IN_PROCESS", customer_name)
    processed_data = load_inventory_data("PROCESSED", customer_name)
    
    # Add status field to each record for unified view
    for record in unprocessed_data:
        record['Status'] = 'Unprocessed'
    for record in in_process_data:
        record['Status'] = 'In-Process'
    for record in processed_data:
        record['Status'] = 'Processed'
    
    # Combine all data
    all_inventory_data = unprocessed_data + in_process_data + processed_data
    
    return render_template('inventory_report.html',
                         customer_name=customer_name,
                         status="All Statuses",
                         inventory_data=all_inventory_data,
                         current_date=datetime.now().strftime('%B %d, %Y'))

def log_inventory_report_action(customer_name, report_type, action, pdf_file=None, sent_by=None):
    """Log inventory report actions to history file for audit tracking."""
    try:
        from datetime import datetime
        
        history_file = 'inventory_report_history.json'
        
        # Create new entry
        entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'customer_name': customer_name,
            'report_type': report_type,
            'action': action,
            'pdf_file': pdf_file,
            'sent_by': sent_by or get_current_user().get('email', 'system') if get_current_user() else 'system'
        }
        
        # Load existing history
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history = []
        
        # Add new entry
        history.append(entry)
        
        # Auto-truncate to latest 500 records
        if len(history) > 500:
            history = history[-500:]
        
        # Save updated history
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
        
        log_info(f"Logged inventory report action: {action} for {customer_name} ({report_type})")
        
    except Exception as e:
        log_error(f"Failed to log inventory report action: {str(e)}")

def generate_inventory_pdf(customer_name, status, inventory_data):
    """Generate PDF from inventory report data using ReportLab."""
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from datetime import datetime
        import re
        
        # Sanitize customer name for filename
        safe_customer = re.sub(r'[^a-zA-Z0-9_\-]', '_', customer_name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"NMP_Inventory_{status.replace(' ', '_')}_{safe_customer}_{timestamp}.pdf"
        pdf_path = os.path.join('pdf_outputs', filename)
        
        # Ensure pdf_outputs directory exists
        os.makedirs('pdf_outputs', exist_ok=True)
        
        # Create PDF document
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        
        # Title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.HexColor('#2c5282')
        )
        
        # Add title
        title = Paragraph(f"NICAYNE METAL PROCESSING<br/>{status} Inventory Report", title_style)
        elements.append(title)
        
        # Add customer and date info
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=1
        )
        info = Paragraph(f"Customer: <b>{customer_name}</b><br/>Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", info_style)
        elements.append(info)
        elements.append(Spacer(1, 12))
        
        if inventory_data:
            # Prepare table data
            headers = list(inventory_data[0].keys())
            # Limit columns for better formatting
            main_columns = ['Customer', 'Date', 'Material Type', 'Thickness', 'Width', 'Weight', 'Pieces']
            if 'Status' in headers:
                main_columns.append('Status')
            
            # Filter headers to main columns that exist
            filtered_headers = [h for h in main_columns if h in headers]
            
            table_data = [filtered_headers]
            
            for item in inventory_data:
                row = []
                for header in filtered_headers:
                    value = item.get(header, '')
                    # Convert to string and handle None values
                    if value is None or value == '':
                        row.append('-')
                    else:
                        row.append(str(value))
                table_data.append(row)
            
            # Create table
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5282')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 20))
            
            # Add summary
            total_items = len(inventory_data)
            total_weight = sum(float(item.get('Weight', 0) or 0) for item in inventory_data)
            total_pieces = sum(int(item.get('Pieces', 0) or 0) for item in inventory_data)
            
            summary_style = ParagraphStyle(
                'SummaryStyle',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=10
            )
            
            summary = Paragraph(f"<b>Summary:</b> {total_items} items | {total_weight:.2f} lbs total weight | {total_pieces} total pieces", summary_style)
            elements.append(summary)
        else:
            # No data message
            no_data = Paragraph(f"No {status.lower()} inventory found for customer {customer_name}.", styles['Normal'])
            elements.append(no_data)
        
        # Build PDF
        doc.build(elements)
        log_info(f"PDF generated successfully: {filename}")
        return pdf_path
        
    except Exception as e:
        log_error(f"Error generating PDF: {str(e)}")
        return None

@app.route('/export-pdf/unprocessed/<customer_name>')
@login_required
def export_pdf_unprocessed(customer_name):
    """Export unprocessed inventory report as PDF."""
    inventory_data = load_inventory_data("UNPROCESSED_INVENTORY", customer_name)
    pdf_path = generate_inventory_pdf(customer_name, "Unprocessed", inventory_data)
    
    if pdf_path and os.path.exists(pdf_path):
        # Log the export action
        log_inventory_report_action(customer_name, "unprocessed", "exported", pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
    else:
        return jsonify({'error': 'Failed to generate PDF'}), 500

@app.route('/export-pdf/in-process/<customer_name>')
@login_required
def export_pdf_in_process(customer_name):
    """Export in-process inventory report as PDF."""
    inventory_data = load_inventory_data("IN_PROCESS", customer_name)
    pdf_path = generate_inventory_pdf(customer_name, "In-Process", inventory_data)
    
    if pdf_path and os.path.exists(pdf_path):
        # Log the export action
        log_inventory_report_action(customer_name, "in-process", "exported", pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
    else:
        return jsonify({'error': 'Failed to generate PDF'}), 500

@app.route('/export-pdf/processed/<customer_name>')
@login_required
def export_pdf_processed(customer_name):
    """Export processed inventory report as PDF."""
    inventory_data = load_inventory_data("PROCESSED", customer_name)
    pdf_path = generate_inventory_pdf(customer_name, "Processed", inventory_data)
    
    if pdf_path and os.path.exists(pdf_path):
        # Log the export action
        log_inventory_report_action(customer_name, "processed", "exported", pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
    else:
        return jsonify({'error': 'Failed to generate PDF'}), 500

@app.route('/export-pdf/all/<customer_name>')
@login_required
def export_pdf_all(customer_name):
    """Export unified inventory report as PDF."""
    unprocessed_data = load_inventory_data("UNPROCESSED_INVENTORY", customer_name)
    in_process_data = load_inventory_data("IN_PROCESS", customer_name)
    processed_data = load_inventory_data("PROCESSED", customer_name)
    
    # Add status field to each record
    for record in unprocessed_data:
        record['Status'] = 'Unprocessed'
    for record in in_process_data:
        record['Status'] = 'In-Process'
    for record in processed_data:
        record['Status'] = 'Processed'
    
    all_inventory_data = unprocessed_data + in_process_data + processed_data
    pdf_path = generate_inventory_pdf(customer_name, "All Statuses", all_inventory_data)
    
    if pdf_path and os.path.exists(pdf_path):
        # Log the export action
        log_inventory_report_action(customer_name, "all", "exported", pdf_path)
        return send_file(pdf_path, as_attachment=True, download_name=os.path.basename(pdf_path))
    else:
        return jsonify({'error': 'Failed to generate PDF'}), 500

@app.route('/email-inventory-report/<customer_name>')
@login_required
def email_inventory_report(customer_name):
    """Email inventory report PDF to customer."""
    try:
        from email_utils import send_email_with_attachment
        import re
        
        # Get report type from query parameter
        report_type = request.args.get('report_type', 'all')
        
        # Load appropriate inventory data
        if report_type == 'unprocessed':
            inventory_data = load_inventory_data("UNPROCESSED_INVENTORY", customer_name)
            status = "Unprocessed"
        elif report_type == 'in-process':
            inventory_data = load_inventory_data("IN_PROCESS", customer_name)
            status = "In-Process"
        elif report_type == 'processed':
            inventory_data = load_inventory_data("PROCESSED", customer_name)
            status = "Processed"
        else:  # all
            unprocessed_data = load_inventory_data("UNPROCESSED_INVENTORY", customer_name)
            in_process_data = load_inventory_data("IN_PROCESS", customer_name)
            processed_data = load_inventory_data("PROCESSED", customer_name)
            
            for record in unprocessed_data:
                record['Status'] = 'Unprocessed'
            for record in in_process_data:
                record['Status'] = 'In-Process'
            for record in processed_data:
                record['Status'] = 'Processed'
                
            inventory_data = unprocessed_data + in_process_data + processed_data
            status = "All Statuses"
        
        # Generate PDF
        pdf_path = generate_inventory_pdf(customer_name, status, inventory_data)
        
        if not pdf_path or not os.path.exists(pdf_path):
            return jsonify({'success': False, 'error': 'Failed to generate PDF'}), 500
        
        # Customer email lookup (you can customize this mapping)
        customer_emails = {
            'demo_customer': 'demo@example.com',
            'test_customer': 'test@example.com',
            'timberlea': 'admin@timberlea.com',
            'hammertown': 'orders@hammertown.com',
            # Add more customer email mappings as needed
        }
        
        # Get customer email
        customer_email = customer_emails.get(customer_name.lower())
        if not customer_email:
            # Try to extract email from environment or use default
            customer_email = os.environ.get('DEFAULT_SEND_TO_EMAIL')
            if not customer_email:
                return jsonify({'success': False, 'error': f'Email address not found for customer {customer_name}'}), 400
        
        # Email content
        subject = f"Inventory Report – {customer_name}"
        body = f"""Dear {customer_name},

Attached is your requested {status.lower()} inventory report from Nicayne Metal Processing.

This report includes all current inventory items matching your customer profile as of today's date.

If you have any questions about this report or need additional information, please don't hesitate to contact us.

Best regards,
Nicayne Metal Processing Team

---
This is an automated message from the Nicayne OS platform.
"""
        
        # Send email
        result = send_email_with_attachment(
            to_email=customer_email,
            subject=subject,
            body=body,
            attachment_path=pdf_path,
            filename=os.path.basename(pdf_path)
        )
        
        if result.get('success'):
            # Log the email action
            log_inventory_report_action(customer_name, report_type, "emailed", pdf_path)
            log_info(f"Inventory report emailed to {customer_email} for customer {customer_name}")
            return jsonify({
                'success': True,
                'message': f'Inventory report successfully sent to {customer_email}',
                'customer': customer_name,
                'report_type': report_type,
                'pdf_filename': os.path.basename(pdf_path)
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to send email'),
                'message': 'Email sending failed'
            }), 500
            
    except Exception as e:
        log_error(f"Error emailing inventory report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/report-history')
@login_required
def report_history():
    """Display inventory report history and audit logs."""
    try:
        history_file = 'inventory_report_history.json'
        
        # Load history
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            history = []
        
        # Sort by timestamp descending (newest first)
        history.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Check if PDF files still exist
        for entry in history:
            pdf_file = entry.get('pdf_file')
            if pdf_file:
                entry['pdf_exists'] = os.path.exists(pdf_file)
            else:
                entry['pdf_exists'] = False
        
        return render_template('report_history.html', history=history)
        
    except Exception as e:
        log_error(f"Error loading report history: {str(e)}")
        return render_template('report_history.html', history=[], error=str(e))

@app.route('/upload-to-po', methods=['POST'])
@login_required
def upload_to_po():
    """Handle file uploads to customer PO folders in Google Drive."""
    return jsonify({'success': True, 'message': 'PO upload handler'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)