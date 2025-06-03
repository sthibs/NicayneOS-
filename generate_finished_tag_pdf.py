"""
Standardized Finished Tag PDF Generator - Nicayne OS Platform
Consistent formatting across all document types with unified design system
"""
from reportlab.lib.pagesizes import landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import os
import qrcode
import io
import sys
sys.path.append('.')
from utils.pdf_design_system import (
    create_standardized_header, 
    create_standardized_footer, 
    get_standardized_styles,
    create_document_title,
    create_section_table,
    NICAYNE_BLUE,
    SECTION_BACKGROUND,
    BORDER_GRAY
)

def generate_qr_code_for_tag(url):
    """Generate QR code image from URL for finished tag"""
    if not url:
        return None
    
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return Image(img_buffer, width=0.8*inch, height=0.8*inch)
    except Exception as e:
        print(f"Error generating QR code for tag: {e}")
        return None

def generate_finished_tag_pdf(data, drive_url=None):
    """Generate a professional 4x6" finished tag PDF optimized for label printing."""
    
    # Create PDF filename with proper naming convention
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    work_order = data.get("work_order_number", "UNKNOWN")
    pieces = data.get("pieces_or_coils", "0")
    
    filename = f"NMP-FINISHED-TAG-{date_str}-{work_order}-{pieces}pcs.pdf"
    pdf_path = f"pdf_outputs/{filename}"

    # Create output directory
    os.makedirs("pdf_outputs", exist_ok=True)
    
    # Create 4x6 inch label size (landscape orientation)
    page_width = 6 * inch
    page_height = 4 * inch
    
    # Create the PDF document with custom page size
    doc = SimpleDocTemplate(
        pdf_path, 
        pagesize=(page_width, page_height),
        leftMargin=0.15*inch,
        rightMargin=0.15*inch,
        topMargin=0.15*inch,
        bottomMargin=0.15*inch
    )
    
    story = []
    
    # Custom styles for clean label layout
    header_style = ParagraphStyle(
        'HeaderStyle',
        fontSize=12,
        fontName='Helvetica-Bold',
        alignment=1,  # Center
        spaceAfter=4
    )
    
    tag_id_style = ParagraphStyle(
        'TagIDStyle',
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=2,  # Right align
    )
    
    date_style = ParagraphStyle(
        'DateStyle',
        fontSize=9,
        fontName='Helvetica',
        alignment=0,  # Left align
    )
    
    # HEADER SECTION - Company name, date, and tag ID
    header_table_data = [
        [
            Paragraph(f"Date: {data.get('date', '')}", date_style),
            Paragraph("NICAYNE METAL PROCESSING", header_style),
            Paragraph(f"TAG: {data.get('tag_id', '')}", tag_id_style)
        ]
    ]
    
    header_table = Table(header_table_data, colWidths=[1.3*inch, 2.4*inch, 1.3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 1.5, colors.black),
        ('BACKGROUND', (1, 0), (1, 0), colors.lightgrey),
    ]))
    
    story.append(header_table)
    
    # JOB INFO SECTION
    job_data = [
        ['Work Order:', data.get('work_order_number', ''), 'Customer:', data.get('customer_name', '')],
        ['Customer PO:', data.get('customer_po', ''), '', '']
    ]
    
    job_table = Table(job_data, colWidths=[1.0*inch, 1.5*inch, 0.8*inch, 1.7*inch])
    job_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(job_table)
    
    # MATERIAL INFO SECTION
    material_data = [
        ['Material Grade:', data.get('material_grade', ''), 'Pieces:', data.get('pieces_or_coils', '')],
        ['Description:', data.get('material_description', ''), 'Weight:', data.get('finished_weight', '') + ' lbs'],
    ]
    
    material_table = Table(material_data, colWidths=[1.0*inch, 2.0*inch, 0.7*inch, 1.3*inch])
    material_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(material_table)
    
    # HEAT NUMBERS SECTION (full width)
    heat_data = [
        ['Heat Number(s):', data.get('heat_numbers', '')]
    ]
    
    heat_table = Table(heat_data, colWidths=[1.2*inch, 3.8*inch])
    heat_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(heat_table)
    
    # PROCESSING INFO & OPERATOR SECTION
    processing_data = [
        ['Incoming Tags:', data.get('incoming_tags', ''), 'Operator:', data.get('operator_initials', '')]
    ]
    
    processing_table = Table(processing_data, colWidths=[1.0*inch, 2.5*inch, 0.7*inch, 0.8*inch])
    processing_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (3, 0), (3, 0), colors.lightgrey),  # Highlight operator box
        ('FONTNAME', (3, 0), (3, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (3, 0), (3, 0), 10),
        ('ALIGN', (3, 0), (3, 0), 'CENTER'),
    ]))
    
    story.append(processing_table)
    
    # Add QR code if Drive URL is available (positioned in bottom right corner)
    if drive_url:
        qr_code = generate_qr_code_for_tag(drive_url)
        if qr_code:
            # Create QR code table positioned at bottom right of 4x6 label
            qr_table = Table([
                ['', '', qr_code],
                ['', '', Paragraph('<font size="6">Digital Copy</font>', 
                                 ParagraphStyle('QRText', fontSize=6, alignment=1))]
            ], colWidths=[4*inch, 1.2*inch, 0.8*inch])
            qr_table.setStyle(TableStyle([
                ('ALIGN', (2, 0), (2, 1), 'CENTER'),
                ('VALIGN', (2, 0), (2, 1), 'MIDDLE'),
            ]))
            story.append(qr_table)
    
    # Build the PDF
    doc.build(story)
    
    return pdf_path