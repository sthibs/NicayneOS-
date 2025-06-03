"""
Generate professional Bill of Lading (BOL) PDF documents for completed work orders
Consolidates all finished tags into a single shipping document
"""

import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import random
import qrcode
import io

def generate_qr_code_for_bol(url):
    """Generate QR code image from URL for BOL"""
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
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        return Image(img_buffer, width=1*inch, height=1*inch)
    except Exception as e:
        print(f"Error generating QR code for BOL: {e}")
        return None

def generate_bol_number():
    """Generate a unique BOL number in format BL######"""
    # Use timestamp + random for uniqueness
    timestamp = int(datetime.now().timestamp()) % 1000000
    random_part = random.randint(100, 999)
    bol_number = f"BL{timestamp:06d}"
    return bol_number

def get_finished_tags_for_work_order(work_order_number):
    """Retrieve all finished tags associated with a work order"""
    finished_tags = []
    
    # Check if finished tags JSON file exists
    if os.path.exists('finished_tags.json'):
        try:
            with open('finished_tags.json', 'r') as f:
                all_tags = json.load(f)
                
            # Filter tags by work order number
            for tag in all_tags:
                if tag.get('work_order_number') == work_order_number:
                    finished_tags.append(tag)
                    
        except Exception as e:
            print(f"Error reading finished tags: {e}")
    
    return finished_tags

def calculate_totals(finished_tags):
    """Calculate total bundles and total weight"""
    total_bundles = len(finished_tags)
    total_weight = 0
    
    for tag in finished_tags:
        try:
            weight = float(tag.get('finished_weight', 0))
            total_weight += weight
        except (ValueError, TypeError):
            pass
    
    return total_bundles, total_weight

def generate_bol_pdf(work_order_number, customer_name=None, customer_po=None, drive_url=None):
    """Generate a complete Bill of Lading PDF for a work order"""
    
    # Get finished tags for this work order
    finished_tags = get_finished_tags_for_work_order(work_order_number)
    
    if not finished_tags:
        raise ValueError(f"No finished tags found for work order {work_order_number}")
    
    # Extract customer info from first tag if not provided
    if not customer_name and finished_tags:
        customer_name = finished_tags[0].get('customer_name', 'Unknown Customer')
    if not customer_po and finished_tags:
        customer_po = finished_tags[0].get('customer_po', 'Unknown PO')
    
    # Generate BOL number and filename
    bol_number = generate_bol_number()
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"NMP-BOL-{date_str}-{bol_number}.pdf"
    filepath = os.path.join('pdf_outputs', filename)
    
    # Ensure output directory exists
    os.makedirs('pdf_outputs', exist_ok=True)
    
    # Create PDF document
    doc = SimpleDocTemplate(filepath, pagesize=letter,
                          rightMargin=0.75*inch, leftMargin=0.75*inch,
                          topMargin=1*inch, bottomMargin=1*inch)
    
    # Build content
    content = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=12,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica'
    )
    
    # Title
    title = Paragraph("BILL OF LADING", title_style)
    content.append(title)
    
    # Header information table
    header_data = [
        ['BOL Number:', bol_number, 'Date Generated:', datetime.now().strftime('%m/%d/%Y')],
        ['Work Order:', work_order_number, '', ''],
        ['Customer Name:', customer_name, '', ''],
        ['Customer PO#:', customer_po, '', '']
    ]
    
    header_table = Table(header_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 1.5*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # First column bold
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),  # Third column bold
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(header_table)
    content.append(Spacer(1, 0.3*inch))
    
    # Line items table
    table_data = [
        ['Finished Tag #', 'Incoming Tag #', 'Material Grade', 'Material Description', 
         'Heat #', 'Thickness', 'Width', 'Length', 'Pieces/Coils', 'Finished Weight']
    ]
    
    # Add finished tag data
    for tag in finished_tags:
        # Extract material info from description if available
        material_desc = tag.get('material_description', '')
        thickness = tag.get('thickness', '')
        width = tag.get('width', '')
        length = tag.get('length', '')
        
        # For slitting jobs, length should be "coil"
        job_type = tag.get('job_type', '')
        if 'slit' in job_type.lower():
            length = 'coil'
        
        row = [
            tag.get('finished_tag_number', ''),
            tag.get('incoming_tag_number', ''),
            tag.get('material_grade', ''),
            material_desc,
            tag.get('heat_number', ''),
            str(thickness),
            str(width),
            str(length),
            str(tag.get('pieces', '')),
            str(tag.get('finished_weight', ''))
        ]
        table_data.append(row)
    
    # Create the table
    line_items_table = Table(table_data, colWidths=[
        0.8*inch, 0.8*inch, 0.7*inch, 1.5*inch, 0.7*inch,
        0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.8*inch
    ])
    
    line_items_table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.0, 0.357, 0.667)),  # NMP Blue
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Data rows styling
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)])
    ]))
    
    content.append(line_items_table)
    content.append(Spacer(1, 0.3*inch))
    
    # Totals section
    total_bundles, total_weight = calculate_totals(finished_tags)
    totals_data = [
        ['Total # of Bundles:', str(total_bundles)],
        ['Total Weight:', f"{total_weight:.2f} lbs"]
    ]
    
    totals_table = Table(totals_data, colWidths=[2*inch, 1.5*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    content.append(totals_table)
    content.append(Spacer(1, 0.4*inch))
    
    # Signature section
    signature_style = ParagraphStyle(
        'SignatureStyle',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        spaceAfter=30
    )
    
    signature_data = [
        ['Driver Signature:', '_' * 40, 'Date:', '_' * 20],
        ['', '', '', ''],
        ['Shipper/Receiver Signature:', '_' * 40, 'Date:', '_' * 20]
    ]
    
    signature_table = Table(signature_data, colWidths=[2*inch, 2.5*inch, 0.8*inch, 1.5*inch])
    signature_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    content.append(signature_table)
    
    # Add QR code if Drive URL is available
    if drive_url:
        qr_code = generate_qr_code_for_bol(drive_url)
        if qr_code:
            content.append(Spacer(1, 12))
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
            content.append(qr_table)
    
    # Build PDF
    doc.build(content)
    
    # Return BOL metadata
    bol_metadata = {
        'bol_number': bol_number,
        'filename': filename,
        'filepath': filepath,
        'work_order_number': work_order_number,
        'customer_name': customer_name,
        'customer_po': customer_po,
        'total_bundles': total_bundles,
        'total_weight': total_weight,
        'date_generated': datetime.now().isoformat(),
        'finished_tags_count': len(finished_tags)
    }
    
    return bol_metadata

if __name__ == "__main__":
    # Test the BOL generator
    try:
        metadata = generate_bol_pdf("WO-12345", "SAMUEL", "23456")
        print(f"BOL generated successfully: {metadata['filename']}")
        print(f"BOL Number: {metadata['bol_number']}")
        print(f"Total Bundles: {metadata['total_bundles']}")
        print(f"Total Weight: {metadata['total_weight']:.2f} lbs")
    except Exception as e:
        print(f"Error generating BOL: {e}")