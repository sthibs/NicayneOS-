#!/usr/bin/env python3
"""
Debug-only extraction to see what data is being extracted without Google Sheets writes.
"""

import sys
import os
sys.path.append('.')

from bol_extractor.extractor import BOLExtractor
from bol_extractor.config import Config
from bol_extractor.pdf_splitter import PDFSplitter
from bol_extractor.ocr_utils import OCRUtils
from bol_extractor.llm_refiner import LLMRefiner
import json

def debug_extraction_only():
    """Show exactly what the AI extracts without writing to sheets."""
    
    pdf_path = "attached_assets/MAK TEST BOL 3 PAGE.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found at: {pdf_path}")
        return
        
    print(f"🔍 Debug Analysis: {pdf_path}")
    print("=" * 60)
    
    # Initialize components
    config = Config()
    pdf_splitter = PDFSplitter()
    ocr_utils = OCRUtils()
    llm_refiner = LLMRefiner(config)
    
    # Split PDF into pages
    page_paths = pdf_splitter.split_pdf(pdf_path)
    print(f"📄 Split into {len(page_paths)} pages")
    
    total_coils = 0
    valid_coils = 0
    
    for i, page_path in enumerate(page_paths):
        print(f"\n📖 PAGE {i + 1}:")
        print("-" * 40)
        
        # Extract text from page
        text = ocr_utils.extract_text_from_pdf(page_path)
        if not text:
            print("❌ No text extracted")
            continue
            
        # Use AI to extract structured data
        coils_data = llm_refiner.extract_bol_data(text, "maksteel")
        if not coils_data:
            print("❌ No structured data extracted")
            continue
            
        page_coils = coils_data.get('coils', [])
        print(f"🤖 AI extracted {len(page_coils)} coils")
        
        # Show raw AI response
        print("📊 RAW AI RESPONSE:")
        print(json.dumps(page_coils, indent=2))
        print()
        
        # Validate each coil
        for j, coil_data in enumerate(page_coils):
            total_coils += 1
            print(f"🔧 COIL {j + 1} from page {i + 1}:")
            
            # Extract fields
            coil_tag = coil_data.get('COIL_TAG#') or coil_data.get('COIL_TAG')
            width = coil_data.get('WIDTH')
            thickness = coil_data.get('THICKNESS')
            weight = coil_data.get('WEIGHT')
            
            # Convert to strings
            coil_tag_str = str(coil_tag).strip() if coil_tag else ''
            width_str = str(width).strip() if width else ''
            thickness_str = str(thickness).strip() if thickness else ''
            weight_str = str(weight).strip() if weight else ''
            
            print(f"   Tag: '{coil_tag_str}'")
            print(f"   Width: '{width_str}'")
            print(f"   Thickness: '{thickness_str}'")
            print(f"   Weight: '{weight_str}'")
            
            # Validate
            invalid_values = ['', 'Unknown', 'MISSING', 'null', 'undefined', '0', '0.0', '0.00', 'None']
            validation_failures = []
            
            if not coil_tag_str or coil_tag_str in invalid_values or not any(char.isdigit() for char in coil_tag_str):
                validation_failures.append(f"Invalid customer tag")
            
            if not width_str or width_str in invalid_values:
                validation_failures.append(f"Invalid width")
                
            if not thickness_str or thickness_str in invalid_values:
                validation_failures.append(f"Invalid thickness")
                
            if not weight_str or weight_str in invalid_values:
                validation_failures.append(f"Invalid weight")
            
            if validation_failures:
                print(f"   ❌ INVALID: {'; '.join(validation_failures)}")
            else:
                valid_coils += 1
                print(f"   ✅ VALID")
                
                # Check width accuracy
                if '5' in width_str and '8' not in width_str:
                    print(f"   ⚠️ WIDTH ISSUE: Shows {width_str} instead of expected 8")
            
            print()
    
    print("=" * 60)
    print(f"📊 SUMMARY:")
    print(f"   Total coils extracted by AI: {total_coils}")
    print(f"   Valid coils that should be processed: {valid_coils}")
    print(f"   Invalid coils filtered out: {total_coils - valid_coils}")
    
    if valid_coils == 12:
        print("✅ Expected 12 coils - validation is working correctly!")
    else:
        print(f"⚠️ Expected 12 coils but got {valid_coils}")

if __name__ == "__main__":
    debug_extraction_only()