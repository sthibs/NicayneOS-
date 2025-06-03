#!/usr/bin/env python3
"""
Analyze the 10-page Maksteel BOL to count expected vs extracted coils
"""

import sys
import os
sys.path.append('.')

from bol_extractor.pdf_splitter import PDFSplitter
from bol_extractor.ocr_utils import OCRUtils
import re

def analyze_10page_bol():
    """Count total coils in the 10-page BOL document"""
    
    pdf_path = "attached_assets/MAK TESY BOL 10 PAGE.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
    
    print(f"Analyzing 10-page BOL: {pdf_path}")
    
    # Split PDF into pages
    splitter = PDFSplitter()
    ocr_utils = OCRUtils()
    
    split_files = splitter.split_pdf(pdf_path)
    print(f"Split into {len(split_files)} pages")
    
    total_coils = 0
    coil_tags = []
    bol_numbers = set()
    
    for i, page_path in enumerate(split_files):
        print(f"\n--- Page {i+1} ---")
        
        # Extract text from page
        page_text = ocr_utils.extract_text_from_pdf(page_path)
        if not page_text:
            print(f"No text extracted from page {i+1}")
            continue
        
        # Find SHIP TAG patterns (these indicate coils)
        ship_tag_pattern = r"SHIP TAG:\s*(\d+)"
        ship_tags = re.findall(ship_tag_pattern, page_text, re.IGNORECASE)
        
        # Find BOL numbers
        bol_pattern = r"BILL OF LADING #:\s*(\d+)"
        bol_matches = re.findall(bol_pattern, page_text, re.IGNORECASE)
        
        # Alternative BOL pattern
        bol_pattern2 = r"(?:BOL|BILL)\s*(?:OF\s*LADING\s*)?#?\s*:?\s*(\d{7})"
        bol_matches2 = re.findall(bol_pattern2, page_text, re.IGNORECASE)
        
        page_coils = len(ship_tags)
        total_coils += page_coils
        coil_tags.extend(ship_tags)
        
        if bol_matches:
            bol_numbers.update(bol_matches)
        if bol_matches2:
            bol_numbers.update(bol_matches2)
        
        print(f"Page {i+1}: {page_coils} coils found")
        if ship_tags:
            print(f"  SHIP TAGs: {ship_tags}")
        if bol_matches or bol_matches2:
            print(f"  BOL numbers: {bol_matches + bol_matches2}")
    
    # Clean up split files
    splitter.cleanup_temp_files()
    
    print(f"\n=== SUMMARY ===")
    print(f"Total pages analyzed: {len(split_files)}")
    print(f"Total coils expected: {total_coils}")
    print(f"Total coils extracted by system: 33")
    print(f"Missing coils: {total_coils - 33}")
    print(f"BOL numbers found: {sorted(bol_numbers)}")
    print(f"All SHIP TAGs: {coil_tags}")
    
    if total_coils != 33:
        print(f"\n⚠️  DISCREPANCY DETECTED!")
        print(f"Expected: {total_coils} coils")
        print(f"Extracted: 33 coils") 
        print(f"Missing: {total_coils - 33} coils")
    else:
        print(f"\n✅ All coils accounted for!")

if __name__ == "__main__":
    analyze_10page_bol()