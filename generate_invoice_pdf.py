"""
Standardized Invoice PDF Generator - Nicayne OS Platform
Consistent formatting across all document types with unified design system
"""

import os
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
import qrcode
import io

# Standardized Design System Colors
NICAYNE_BLUE = colors.HexColor('#0056A4')
SECTION_BACKGROUND = colors.HexColor('#f0f4f8')
BORDER_GRAY = colors.HexColor('#c8c8c8')
TEXT_DARK = colors.black
HEADER_TEXT = colors.white

def generate_invoice_number():
    """Generate a unique invoice number in format INV######"""
    timestamp = datetime.now()
    invoice_number = f"INV{timestamp.strftime('%m%d%y')}{timestamp.strftime('%H%M')}"
    return invoice_number

def group_materials_by_size(finished_tags):
    """Group finished tags by material size and calculate totals"""
    size_groups = {}
    
    for tag in finished_tags:
        thickness = tag.get('thickness', 'N/A')
        width = tag.get('width', 'N/A')
        length = tag.get('length', 'N/A')
        size_key = f"{thickness} x {width} x {length}"
        
        if size_key not in size_groups:
            size_groups[size_key] = {
                'description': size_key,
                'pieces': 0,
                'weight': 0.0
            }
        
        size_groups[size_key]['pieces'] += int(tag.get('pieces', 1))
        size_groups[size_key]['weight'] += float(tag.get('weight', 0))
    
    return list(size_groups.values())

def calculate_pricing(material_groups, pricing_method, rate_or_amount):
    """Calculate pricing based on method (CWT or LOT)"""
    line_items = []
    subtotal = 0
    
    if pricing_method == 'cwt':
        rate = float(rate_or_amount)
        for group in material_groups:
            cwt_weight = group['weight'] / 100
            line_subtotal = cwt_weight * rate
            subtotal += line_subtotal
            
            line_items.append({
                'description': group['description'],
                'pieces': group['pieces'],
                'weight': group['weight'],
                'rate_type': 'CWT',
                'rate': f"${rate:.2f}",
                'subtotal': line_subtotal
            })
    
    elif pricing_method == 'lot':
        lot_amount = float(rate_or_amount)
        subtotal = lot_amount
        
        # For lot pricing, create one line item for the entire job
        total_pieces = sum(group['pieces'] for group in material_groups)
        total_weight = sum(group['weight'] for group in material_groups)
        
        line_items.append({
            'description': 'Complete Job - All Materials',
            'pieces': total_pieces,
            'weight': total_weight,
            'rate_type': 'LOT',
            'rate': 'Flat Rate',
            'subtotal': lot_amount
        })
    
    return line_items, subtotal

def generate_invoice_pdf(invoice_data, drive_url=None):
    """Generate a professional invoice PDF"""
    
    # Create filename
    invoice_number = generate_invoice_number()
    work_order = invoice_data['work_order_number']
    customer_po = invoice_data['customer_po']
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    filename = f"NMP-INVOICE-{date_str}-WO{work_order}-PO{customer_po}.pdf"
    filepath = os.path.join('pdf_outputs', filename)
    
    # Ensure output directory exists
    os.makedirs('pdf_outputs', exist_ok=True)
    
    # Create document
    doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.Color(0, 0.36, 0.66),  # NMP Blue
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    company_style = ParagraphStyle(
        'CompanyStyle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.Color(0, 0.36, 0.66),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.Color(0, 0.36, 0.66),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    # Header
    story.append(Paragraph("NICAYNE METAL PROCESSING LTD.", header_style))
    story.append(Paragraph("Professional Metal Processing Services", company_style))
    story.append(Spacer(1, 20))
    
    # Invoice title and details
    story.append(Paragraph("INVOICE", title_style))
    
    # Invoice info table
    invoice_info = [
        ['Invoice Number:', invoice_number, 'Date:', datetime.now().strftime('%B %d, %Y')],
        ['Work Order #:', work_order, 'Customer PO:', customer_po],
        ['BOL Number:', invoice_data.get('bol_number', 'N/A'), '', '']
    ]
    
    info_table = Table(invoice_info, colWidths=[1.5*inch, 1.5*inch, 1*inch, 1.5*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Bill to section
    bill_to_data = [
        ['Bill To:', ''],
        [invoice_data['customer_name'].upper(), '']
    ]
    
    bill_to_table = Table(bill_to_data, colWidths=[1*inch, 5*inch])
    bill_to_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(bill_to_table)
    story.append(Spacer(1, 20))
    
    # Materials and pricing table
    material_groups = group_materials_by_size(invoice_data['finished_tags'])
    line_items, subtotal = calculate_pricing(
        material_groups,
        invoice_data['pricing_method'],
        invoice_data['rate_or_amount']
    )
    
    # Table headers
    table_data = [['Material Description', 'Pieces', 'Weight (lbs)', 'Rate Type', 'Rate', 'Subtotal']]
    
    # Add line items
    for item in line_items:
        table_data.append([
            item['description'],
            str(item['pieces']),
            f"{item['weight']:.2f}",
            item['rate_type'],
            item['rate'],
            f"${item['subtotal']:.2f}"
        ])
    
    # Create pricing table
    pricing_table = Table(table_data, colWidths=[2.5*inch, 0.8*inch, 1*inch, 0.8*inch, 1*inch, 1*inch])
    pricing_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0, 0.36, 0.66)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
    ]))
    
    story.append(pricing_table)
    story.append(Spacer(1, 20))
    
    # Totals section
    totals_data = [
        ['', '', '', '', 'Subtotal:', f"${subtotal:.2f}"],
        ['', '', '', '', 'Tax:', 'N/A'],
        ['', '', '', '', 'TOTAL:', f"${subtotal:.2f}"]
    ]
    
    totals_table = Table(totals_data, colWidths=[2.5*inch, 0.8*inch, 1*inch, 0.8*inch, 1*inch, 1*inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (4, 0), (4, 1), 'Helvetica-Bold'),
        ('FONTNAME', (4, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (4, 0), (-1, -1), 11),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (4, 2), (-1, 2), 1, colors.black),
        ('BACKGROUND', (4, 2), (-1, 2), colors.Color(0.9, 0.9, 0.9)),
    ]))
    
    story.append(totals_table)
    story.append(Spacer(1, 30))
    
    # Notes section
    if invoice_data.get('notes'):
        story.append(Paragraph("<b>Notes:</b>", styles['Normal']))
        story.append(Paragraph(invoice_data['notes'], styles['Normal']))
        story.append(Spacer(1, 20))
    
    # Footer
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.Color(0.3, 0.3, 0.3),
        alignment=TA_CENTER
    )
    
    story.append(Spacer(1, 30))
    story.append(Paragraph("Thank you for your business!", footer_style))
    story.append(Paragraph("Payment Terms: Net 30 Days", footer_style))
    story.append(Paragraph("For questions regarding this invoice, please contact our accounting department.", footer_style))
    
    # Build PDF
    doc.build(story)
    
    # Save invoice record
    invoice_record = {
        'invoice_number': invoice_number,
        'work_order_number': work_order,
        'customer_name': invoice_data['customer_name'],
        'customer_po': customer_po,
        'bol_number': invoice_data.get('bol_number'),
        'date_generated': datetime.now().isoformat(),
        'pricing_method': invoice_data['pricing_method'],
        'rate_or_amount': invoice_data['rate_or_amount'],
        'subtotal': subtotal,
        'total': subtotal,
        'filename': filename,
        'filepath': filepath,
        'notes': invoice_data.get('notes', ''),
        'line_items_count': len(line_items)
    }
    
    # Save to tracking file
    save_invoice_record(invoice_record)
    
    return {
        'invoice_number': invoice_number,
        'filename': filename,
        'filepath': filepath,
        'subtotal': subtotal,
        'total': subtotal,
        'record': invoice_record
    }

def save_invoice_record(invoice_record):
    """Save invoice record to tracking file"""
    try:
        invoice_log_file = 'invoice_tracking.json'
        
        if os.path.exists(invoice_log_file):
            with open(invoice_log_file, 'r') as f:
                invoices = json.load(f)
        else:
            invoices = []
        
        invoices.append(invoice_record)
        
        # Keep only the most recent 200 invoices
        invoices = invoices[-200:]
        
        with open(invoice_log_file, 'w') as f:
            json.dump(invoices, f, indent=2)
            
    except Exception as e:
        print(f"Error saving invoice record: {str(e)}")

if __name__ == "__main__":
    # Test data
    test_invoice_data = {
        'work_order_number': 'WO-20250531-200247',
        'customer_name': 'samuel',
        'customer_po': '23456',
        'bol_number': 'BL734193',
        'pricing_method': 'cwt',
        'rate_or_amount': '12.50',
        'notes': 'Rush order - expedited processing',
        'finished_tags': [
            {
                'thickness': '0.250',
                'width': '6',
                'length': '240',
                'pieces': '25',
                'weight': '2337.75'
            },
            {
                'thickness': '0.375',
                'width': '8',
                'length': '120',
                'pieces': '15',
                'weight': '2338.00'
            }
        ]
    }
    
    result = generate_invoice_pdf(test_invoice_data)
    print(f"Generated invoice: {result['filename']}")
    print(f"Total amount: ${result['total']:.2f}")