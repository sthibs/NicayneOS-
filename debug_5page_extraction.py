#!/usr/bin/env python3
"""
Debug script to analyze 5-page extraction and identify missing coils
"""

import sys
import os
import json
from bol_extractor.config import Config
from bol_extractor.pdf_splitter import PDFSplitter
from bol_extractor.ocr_utils import OCRUtils
from bol_extractor.llm_refiner import LLMRefiner

def debug_5page_extraction():
    """Analyze which coils are being extracted from the 5-page document."""
    
    pdf_path = "attached_assets/MAK TEST BOL 5 PAGE.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
    
    try:
        config = Config()
        pdf_splitter = PDFSplitter()
        ocr_utils = OCRUtils()
        llm_refiner = LLMRefiner(config)
        
        # Split PDF
        split_files = pdf_splitter.split_pdf(pdf_path)
        print(f"Split PDF into {len(split_files)} pages")
        
        total_coils = 0
        all_bol_numbers = set()
        
        for i, page_path in enumerate(split_files):
            print(f"\n--- PAGE {i + 1} ---")
            
            # Extract text
            page_text = ocr_utils.extract_text_from_pdf(page_path)
            processed_text = ocr_utils.preprocess_text(page_text)
            
            # Extract with AI
            page_data = llm_refiner.extract_bol_data(processed_text, "maksteel")
            
            if page_data and 'coils' in page_data:
                coils = page_data['coils']
                print(f"Found {len(coils)} coils on page {i + 1}")
                
                for j, coil in enumerate(coils):
                    total_coils += 1
                    bol_num = coil.get('BOL_NUMBER', 'Unknown')
                    customer_tag = coil.get('CUSTOMER_TAG', 'Unknown')
                    all_bol_numbers.add(bol_num)
                    
                    print(f"  Coil {total_coils}: BOL={bol_num}, Tag={customer_tag}")
            else:
                print(f"No coils found on page {i + 1}")
        
        print(f"\n=== SUMMARY ===")
        print(f"Total coils extracted: {total_coils}")
        print(f"Expected: 15")
        print(f"Missing: {15 - total_coils}")
        print(f"Unique BOL numbers: {sorted(list(all_bol_numbers))}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_5page_extraction()