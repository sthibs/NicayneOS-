#!/usr/bin/env python3
"""
Debug script to analyze coil extraction per page and track BOL numbers.
This will help identify which of the 15 total coils are missing.
"""

import sys
import os
import json
from bol_extractor.config import Config
from bol_extractor.pdf_splitter import PDFSplitter
from bol_extractor.ocr_utils import OCRUtils
from bol_extractor.llm_refiner import LLMRefiner

def debug_coil_extraction():
    """Extract and analyze coils per page to find the missing 3 out of 15 total."""
    
    # Use the new 5-page test PDF
    pdf_path = "attached_assets/MAK TEST BOL 5 PAGE.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    try:
        # Initialize components
        config = Config()
        pdf_splitter = PDFSplitter()
        ocr_utils = OCRUtils(config)
        llm_refiner = LLMRefiner(config)
        
        # Split PDF into pages
        split_files = pdf_splitter.split_pdf(pdf_path)
        if not split_files:
            print(f"❌ Failed to split PDF or no pages found")
            return
        print(f"📄 Split PDF into {len(split_files)} pages")
        print("=" * 60)
        
        total_coils_found = 0
        bol_numbers_found = set()
        
        for i, page_path in enumerate(split_files):
            print(f"\n🔍 ANALYZING PAGE {i + 1}")
            print("-" * 40)
            
            # Extract text
            page_text = ocr_utils.extract_text_from_pdf(page_path)
            if not page_text:
                print(f"⚠️ No text extracted from page {i + 1}")
                continue
            
            processed_text = ocr_utils.preprocess_text(page_text)
            print(f"📝 Extracted {len(processed_text)} characters")
            
            # Extract BOL data
            page_data = llm_refiner.extract_bol_data(processed_text, "maksteel")
            
            if not page_data or 'coils' not in page_data:
                print(f"❌ No coil data found on page {i + 1}")
                continue
            
            coils = page_data['coils']
            page_coil_count = len(coils)
            total_coils_found += page_coil_count
            
            print(f"✅ Found {page_coil_count} coils on page {i + 1}")
            
            # Analyze each coil
            for j, coil in enumerate(coils, 1):
                bol_num = coil.get('BOL_NUMBER', 'Unknown')
                customer_tag = coil.get('CUSTOMER_TAG', 'Unknown')
                width = coil.get('WIDTH', 'Unknown')
                
                bol_numbers_found.add(bol_num)
                
                print(f"  Coil {j}: BOL={bol_num}, Tag={customer_tag}, Width={width}")
        
        print("\n" + "=" * 60)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 60)
        print(f"Total coils found: {total_coils_found} out of expected 15")
        print(f"Missing coils: {15 - total_coils_found}")
        print(f"Unique BOL numbers found: {len(bol_numbers_found)}")
        print("BOL numbers:", sorted(list(bol_numbers_found)))
        
        if total_coils_found < 15:
            print(f"\n❌ MISSING {15 - total_coils_found} COILS")
            print("Possible causes:")
            print("- OCR missed some text")
            print("- AI didn't detect all coils in tables")
            print("- Validation rules too strict")
            print("- Different BOL format on some pages")
        else:
            print("\n✅ All 15 coils found successfully!")
            
    except Exception as e:
        print(f"❌ Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_coil_extraction()