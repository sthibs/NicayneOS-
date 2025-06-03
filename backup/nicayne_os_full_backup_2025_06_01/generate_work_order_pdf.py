"""
Generate professional Work Order PDF documents matching the finalized design
Includes all fields from the work order form with proper layout and styling
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os
from datetime import datetime
import json
import qrcode
import io
from PIL import Image as PILImage

def generate_qr_code(url):
    """Generate QR code image from URL and return as ReportLab Image object"""
    if not url:
        return None
    
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to ReportLab Image
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return Image(img_buffer, width=1*inch, height=1*inch)
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

def generate_work_order_pdf(work_order_data, drive_url=None):
    """Generate a professional work order PDF matching the design specifications"""
    
    # Create filename
    work_order_number = work_order_data.get('work_order_number', 'UNKNOWN')
    customer_name = work_order_data.get('customer_name', 'UNKNOWN').replace(' ', '_')
    filename = f"WO-{work_order_number}-{customer_name}.pdf"
    
    # Create work_orders directory if it doesn't exist
    os.makedirs('work_orders', exist_ok=True)
    filepath = os.path.join('work_orders', filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(filepath, pagesize=letter,
                          rightMargin=0.5*inch, leftMargin=0.5*inch,
                          topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Build the story (content)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#005baa')
    )
    
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=16,
        spaceAfter=6,
        alignment=TA_LEFT,
        textColor=colors.black
    )
    
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=8,
        spaceBefore=12,
        textColor=colors.HexColor('#005baa'),
        borderWidth=1,
        borderColor=colors.HexColor('#005baa'),
        borderPadding=4
    )
    
    # Header Section
    header_table_data = [
        [
            Paragraph("Nicayne Metal Processing", company_style),
            "",
            Paragraph(f"<b>NMP</b>", ParagraphStyle('NMP', fontSize=24, alignment=TA_RIGHT, textColor=colors.HexColor('#005baa')))
        ]
    ]
    
    header_table = Table(header_table_data, colWidths=[3*inch, 2*inch, 2*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#005baa'))
    ]))
    story.append(header_table)
    story.append(Spacer(1, 12))
    
    # Work Order Title and Number
    work_order_title_data = [
        [
            Paragraph(f"<b>Work Order #{work_order_number}</b>", header_style),
            "",
            Paragraph(f"Date Created<br/>{datetime.now().strftime('%Y-%m-%d')}", 
                     ParagraphStyle('DateStyle', fontSize=10, alignment=TA_RIGHT))
        ]
    ]
    
    work_order_title_table = Table(work_order_title_data, colWidths=[4*inch, 1*inch, 2*inch])
    work_order_title_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#005baa'))
    ]))
    story.append(work_order_title_table)
    story.append(Spacer(1, 12))
    
    # General Information Section
    story.append(Paragraph("<b>General Information</b>", section_header_style))
    
    general_info_data = [
        ["Quote Number", "Customer", "Date Created"],
        [work_order_data.get('quote_number', ''), 
         work_order_data.get('customer_name', ''), 
         datetime.now().strftime('%Y-%m-%d')],
        ["Date Required", "Customer PO #", ""],
        [work_order_data.get('date_required', ''), 
         work_order_data.get('customer_po', ''), 
         ""]
    ]
    
    general_info_table = Table(general_info_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
    general_info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f0f0f0')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold')
    ]))
    story.append(general_info_table)
    story.append(Spacer(1, 12))
    
    # Packaging Instructions Section
    story.append(Paragraph("<b>Packaging Instructions</b>", section_header_style))
    
    packaging_data = [
        ["Max Bundle/Skid Weight", f"{work_order_data.get('max_bundle_weight', '')} lbs", 
         "Requested Pieces per Bundle", work_order_data.get('pieces_per_bundle', '')],
        ["Max OD", f"{work_order_data.get('max_od', '')} in", 
         "Wood Spacers", work_order_data.get('wood_spacers', '')],
        ["Paper Wrap", work_order_data.get('paper_wrap', ''), 
         "Coil Direction on Skid", work_order_data.get('coil_direction', '')],
        ["Edge Protectors", work_order_data.get('edge_protectors', ''), 
         "Split Coil", work_order_data.get('split_coil', '')]
    ]
    
    packaging_table = Table(packaging_data, colWidths=[1.7*inch, 1.7*inch, 1.7*inch, 1.7*inch])
    packaging_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold')
    ]))
    story.append(packaging_table)
    story.append(Spacer(1, 12))
    
    # Tolerances Section
    story.append(Paragraph("<b>Tolerances</b>", section_header_style))
    
    # Process tolerances - handle multiple tolerance groups
    tolerance_thickness = work_order_data.get('tolerance_thickness', [])
    tolerance_width = work_order_data.get('tolerance_width', [])
    tolerance_length = work_order_data.get('tolerance_length', [])
    
    # Ensure all lists are the same length
    max_tolerance_groups = max(len(tolerance_thickness), len(tolerance_width), len(tolerance_length))
    
    tolerance_data = [["Thickness", "Width", "Length"]]
    
    for i in range(max_tolerance_groups):
        thickness = tolerance_thickness[i] if i < len(tolerance_thickness) else "–"
        width = tolerance_width[i] if i < len(tolerance_width) else "–"
        length = tolerance_length[i] if i < len(tolerance_length) else "–"
        tolerance_data.append([thickness, width, length])
    
    # If no tolerances, add empty row
    if max_tolerance_groups == 0:
        tolerance_data.append(["–", "–", "–"])
    
    tolerance_table = Table(tolerance_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
    tolerance_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ]))
    story.append(tolerance_table)
    story.append(Spacer(1, 12))
    
    # Customer Notes
    if work_order_data.get('packaging_instructions'):
        story.append(Paragraph(f"<b>Customer Notes:</b> {work_order_data.get('packaging_instructions', '')}", 
                              ParagraphStyle('Notes', fontSize=10, spaceAfter=12)))
    
    # Job Process Section
    jobs = work_order_data.get('jobs', [])
    
    if jobs:
        for job_index, job in enumerate(jobs):
            job_type = job.get('job_type', '').lower()
            
            if job_type == 'slitting':
                story.append(Paragraph(f"<b>Process Type: Slitting &nbsp;&nbsp;&nbsp;&nbsp; Slitting Jobs</b>", section_header_style))
                
                slitting_headers = ["Material Grade", "Coil Description", "Incoming Weight", "OD Size", "Finished Weight"]
                slitting_data = [slitting_headers]
                
                # Process slitting job data
                material_grade = job.get('material_grade', '–')
                thickness = job.get('thickness', '')
                width = job.get('width', '')
                coil_desc = f"{thickness} x {width}\" Coil ID: {job.get('coil_id', '')}" if thickness and width else "–"
                incoming_weight = f"{job.get('incoming_weight', '')} lbs" if job.get('incoming_weight') else "–"
                od_size = f"{job.get('od_size', '')} in" if job.get('od_size') else "–"
                finished_weight = f"{job.get('finished_weight', '')} lbs/" if job.get('finished_weight') else "–"
                
                slitting_data.append([material_grade, coil_desc, incoming_weight, od_size, finished_weight])
                
            elif job_type == 'cut_to_length':
                story.append(Paragraph(f"<b>Process Type: Cut-to-Length &nbsp;&nbsp;&nbsp;&nbsp; Cut-to-Length Jobs</b>", section_header_style))
                
                ctl_headers = ["Material Grade", "Material Description", "Incoming Weight", "Finished Pieces", "Finished Weight"]
                slitting_data = [ctl_headers]
                
                # Process CTL job data
                material_grade = job.get('material_grade', '–')
                thickness = job.get('thickness', '')
                width = job.get('width', '')
                length = job.get('length', '')
                material_desc = f"{thickness} x {width}\" x {length}\"" if all([thickness, width, length]) else "–"
                incoming_weight = f"{job.get('incoming_weight', '')} lbs" if job.get('incoming_weight') else "–"
                finished_pieces = job.get('finished_pieces', '–')
                finished_weight = f"{job.get('finished_weight', '')} lbs" if job.get('finished_weight') else "–"
                
                slitting_data.append([material_grade, material_desc, incoming_weight, finished_pieces, finished_weight])
            
            # Create job table
            job_table = Table(slitting_data, colWidths=[1.4*inch, 1.4*inch, 1.4*inch, 1.4*inch, 1.4*inch])
            job_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f0f0')),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')
            ]))
            story.append(job_table)
            story.append(Spacer(1, 12))
    
    # Bottom section - Operator Notes
    story.append(Spacer(1, 24))
    story.append(Paragraph("<b>Operator Notes:</b>", ParagraphStyle('OperatorNotes', fontSize=12, spaceAfter=24)))
    story.append(Spacer(1, 48))
    
    # Signature lines
    signature_data = [
        ["Operator Signature: _________________________", "Date: _______________"],
        ["", ""],
        ["Supervisor Signature: _________________________", "Date: _______________"]
    ]
    
    signature_table = Table(signature_data, colWidths=[4*inch, 2.5*inch])
    signature_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(signature_table)
    
    # Add QR code if Drive URL is available
    if drive_url:
        qr_code = generate_qr_code(drive_url)
        if qr_code:
            story.append(Spacer(1, 12))
            # Create QR code table positioned at bottom right
            qr_table = Table([
                ['', '', qr_code],
                ['', '', Paragraph('<font size="8">Scan for digital copy</font>', 
                                 ParagraphStyle('QRText', fontSize=8, alignment=TA_CENTER))]
            ], colWidths=[5*inch, 1*inch, 1*inch])
            qr_table.setStyle(TableStyle([
                ('ALIGN', (2, 0), (2, 1), 'CENTER'),
                ('VALIGN', (2, 0), (2, 1), 'MIDDLE'),
            ]))
            story.append(qr_table)
    
    # Build PDF
    doc.build(story)
    
    return filepath

def generate_work_order_pdf_from_form_data(form_data, drive_url=None):
    """Generate work order PDF from form submission data"""
    
    # Extract job data
    jobs = []
    if form_data.get('jobs'):
        for job in form_data['jobs']:
            jobs.append({
                'job_type': job.get('job_type', ''),
                'material_grade': job.get('material_grade', ''),
                'thickness': job.get('thickness', ''),
                'width': job.get('width', ''),
                'length': job.get('length', ''),
                'incoming_weight': job.get('incoming_weight', ''),
                'finished_pieces': job.get('finished_pieces', ''),
                'finished_weight': job.get('finished_weight', ''),
                'coil_id': job.get('coil_id', ''),
                'od_size': job.get('od_size', '')
            })
    
    # Extract tolerance data
    tolerance_thickness = form_data.get('tolerance_thickness', [])
    tolerance_width = form_data.get('tolerance_width', [])
    tolerance_length = form_data.get('tolerance_length', [])
    
    # Convert single strings to lists if needed
    if isinstance(tolerance_thickness, str):
        tolerance_thickness = [tolerance_thickness] if tolerance_thickness else []
    if isinstance(tolerance_width, str):
        tolerance_width = [tolerance_width] if tolerance_width else []
    if isinstance(tolerance_length, str):
        tolerance_length = [tolerance_length] if tolerance_length else []
    
    work_order_data = {
        'work_order_number': form_data.get('work_order_number', ''),
        'quote_number': form_data.get('quote_number', ''),
        'customer_name': form_data.get('customer_name', ''),
        'customer_po': form_data.get('customer_po', ''),
        'date_required': form_data.get('date_required', ''),
        'max_bundle_weight': form_data.get('max_bundle_weight', ''),
        'pieces_per_bundle': form_data.get('pieces_per_bundle', ''),
        'max_od': form_data.get('max_od', ''),
        'wood_spacers': form_data.get('wood_spacers', ''),
        'paper_wrap': form_data.get('paper_wrap', ''),
        'coil_direction': form_data.get('coil_direction', ''),
        'edge_protectors': form_data.get('edge_protectors', ''),
        'split_coil': form_data.get('split_coil', ''),
        'packaging_instructions': form_data.get('packaging_instructions', ''),
        'tolerance_thickness': tolerance_thickness,
        'tolerance_width': tolerance_width,
        'tolerance_length': tolerance_length,
        'jobs': jobs
    }
    
    return generate_work_order_pdf(work_order_data, drive_url)