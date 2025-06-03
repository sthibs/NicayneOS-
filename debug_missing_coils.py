#!/usr/bin/env python3
"""
Debug script to identify which coils are missing from the 5-page extraction
"""

import sys
import os
import json
import fitz  # PyMuPDF

def analyze_pdf_content():
    """Analyze the PDF to find all BOL numbers and coil references."""
    
    pdf_path = "attached_assets/MAK TEST BOL 5 PAGE.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
    
    try:
        # Open PDF and extract all text
        doc = fitz.open(pdf_path)
        all_text = ""
        page_texts = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            page_texts.append(page_text)
            all_text += f"\n--- PAGE {page_num + 1} ---\n" + page_text
        
        doc.close()
        
        # Find all BOL numbers
        import re
        bol_pattern = r'(?:BOL|B/L)[#\s]*:?\s*([A-Z0-9-]+)'
        bol_matches = re.findall(bol_pattern, all_text, re.IGNORECASE)
        
        # Find coil/tag references
        coil_pattern = r'(?:coil|tag)[#\s]*:?\s*([A-Z0-9-]+)'
        coil_matches = re.findall(coil_pattern, all_text, re.IGNORECASE)
        
        # Find table-like data with dimensions
        width_pattern = r'(\d+(?:\.\d+)?)\s*["\']?\s*(?:x|X|\*)\s*(\d+(?:\.\d+)?)'
        dimension_matches = re.findall(width_pattern, all_text)
        
        print("=== PDF CONTENT ANALYSIS ===")
        print(f"Total pages: {len(page_texts)}")
        print(f"Total characters: {len(all_text)}")
        print()
        
        print("BOL Numbers found:")
        unique_bols = list(set(bol_matches))
        for bol in unique_bols:
            print(f"  - {bol}")
        print(f"Total unique BOLs: {len(unique_bols)}")
        print()
        
        print("Coil/Tag references found:")
        unique_coils = list(set(coil_matches))
        for coil in unique_coils:
            print(f"  - {coil}")
        print(f"Total unique coil references: {len(unique_coils)}")
        print()
        
        print("Dimension patterns found:")
        for dim in dimension_matches[:10]:  # Show first 10
            print(f"  - {dim[0]} x {dim[1]}")
        print(f"Total dimension patterns: {len(dimension_matches)}")
        print()
        
        # Analyze each page
        for i, page_text in enumerate(page_texts):
            print(f"--- PAGE {i + 1} ANALYSIS ---")
            page_bols = re.findall(bol_pattern, page_text, re.IGNORECASE)
            page_coils = re.findall(coil_pattern, page_text, re.IGNORECASE)
            page_dims = re.findall(width_pattern, page_text)
            
            print(f"BOLs on page: {list(set(page_bols))}")
            print(f"Coils on page: {list(set(page_coils))}")
            print(f"Dimensions on page: {len(page_dims)}")
            
            # Look for tabular data
            lines = page_text.split('\n')
            potential_coil_lines = []
            for line in lines:
                if any(keyword in line.lower() for keyword in ['heat', 'width', 'thickness', 'weight', 'coil']):
                    if len(line.strip()) > 10:  # Filter out headers
                        potential_coil_lines.append(line.strip())
            
            print(f"Potential coil data lines: {len(potential_coil_lines)}")
            for line in potential_coil_lines[:3]:  # Show first 3
                print(f"  - {line[:100]}...")
            print()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_pdf_content()