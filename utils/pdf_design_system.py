"""
Standardized PDF Design System for Nicayne OS Platform
Provides consistent formatting, colors, and layout components across all document types
"""

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Standardized Design System Colors
NICAYNE_BLUE = colors.HexColor('#0056A4')
SECTION_BACKGROUND = colors.HexColor('#f0f4f8')
BORDER_GRAY = colors.HexColor('#c8c8c8')
TEXT_DARK = colors.black
HEADER_TEXT = colors.white

def create_standardized_header():
    """Create standardized header for all Nicayne OS documents"""
    header_data = [
        ["NICAYNE METAL PROCESSING", "Powered by Chaos Operating System"],
    ]
    
    header_table = Table(header_data, colWidths=[4.5*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NICAYNE_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, -1), HEADER_TEXT),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, 0), 'Helvetica'),
        ('FONTSIZE', (0, 0), (0, 0), 18),
        ('FONTSIZE', (1, 0), (1, 0), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    
    return header_table

def create_standardized_footer(doc_type, timestamp, qr_code=None):
    """Create standardized footer for all documents"""
    if qr_code:
        footer_data = [
            [f"Generated: {timestamp}", "", qr_code],
            ["Nicayne Metal Processing OS", "", "Scan for Digital Access"]
        ]
        footer_table = Table(footer_data, colWidths=[3*inch, 2*inch, 2.5*inch])
        footer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (1, 1), 9),
            ('FONTSIZE', (2, 1), (2, 1), 8),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.gray),
        ]))
    else:
        footer_data = [
            [f"Generated: {timestamp}"],
            ["Nicayne Metal Processing OS"]
        ]
        footer_table = Table(footer_data, colWidths=[7.5*inch])
        footer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.gray),
        ]))
    
    return footer_table

def get_standardized_styles():
    """Get standardized paragraph styles for all documents"""
    styles = getSampleStyleSheet()
    
    # Document title style
    title_style = ParagraphStyle(
        'DocumentTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=16,
        spaceBefore=8,
        alignment=TA_CENTER,
        textColor=NICAYNE_BLUE,
        fontName='Helvetica-Bold'
    )
    
    # Section header style
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=8,
        spaceBefore=12,
        textColor=NICAYNE_BLUE,
        fontName='Helvetica-Bold'
    )
    
    # Field label style
    field_label_style = ParagraphStyle(
        'FieldLabel',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        textColor=TEXT_DARK
    )
    
    # Field value style
    field_value_style = ParagraphStyle(
        'FieldValue',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        textColor=TEXT_DARK
    )
    
    # Small text style
    small_text_style = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica',
        textColor=colors.gray
    )
    
    return {
        'title': title_style,
        'section_header': section_header_style,
        'field_label': field_label_style,
        'field_value': field_value_style,
        'small_text': small_text_style
    }

def create_section_table(data, col_widths, header_background=True):
    """Create a standardized table with consistent styling"""
    table = Table(data, colWidths=col_widths)
    
    style_commands = [
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, BORDER_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]
    
    if header_background and len(data) > 1:
        style_commands.extend([
            ('BACKGROUND', (0, 0), (-1, 0), SECTION_BACKGROUND),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (-1, 0), NICAYNE_BLUE),
        ])
    
    table.setStyle(TableStyle(style_commands))
    return table

def create_document_title(title_text, doc_number=None):
    """Create a standardized document title section"""
    styles = get_standardized_styles()
    
    if doc_number:
        title_data = [
            [title_text, f"#{doc_number}"]
        ]
        title_table = Table(title_data, colWidths=[5*inch, 2.5*inch])
        title_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 20),
            ('FONTSIZE', (1, 0), (1, 0), 16),
            ('TEXTCOLOR', (0, 0), (-1, -1), NICAYNE_BLUE),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return title_table
    else:
        return Paragraph(title_text, styles['title'])