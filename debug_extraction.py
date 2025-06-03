#!/usr/bin/env python3
"""
Debug script to extract and analyze coil data without writing to sheets.
This will show us exactly what data is being extracted from each page.
"""

from bol_extractor.config import Config
from bol_extractor.extractor import BOLExtractor
import json

def debug_extraction():
    """Extract and display data from the test PDF."""
    try:
        config = Config()
        extractor = BOLExtractor(config)
        
        pdf_path = "attached_assets/MAK TEST BOL 3 PAGE.pdf"
        supplier_name = "maksteel"
        
        print(f"Analyzing: {pdf_path}")
        print(f"Supplier: {supplier_name}")
        print("=" * 60)
        
        # Split PDF into pages
        split_files = extractor.pdf_splitter.split_pdf(pdf_path)
        print(f"PDF split into {len(split_files)} pages")
        
        all_coils = []
        
        for i, page_path in enumerate(split_files):
            print(f"\n--- PAGE {i + 1} ---")
            
            # Extract text
            page_text = extractor.ocr_utils.extract_text_from_pdf(page_path)
            if not page_text:
                print(f"No text extracted from page {i + 1}")
                continue
                
            processed_text = extractor.ocr_utils.preprocess_text(page_text)
            print(f"Text length: {len(processed_text)} characters")
            
            # Check for BOL numbers in text
            bol_numbers = ["1641211", "164121t1", "164121l1", "1641212", "1641213"]
            found_bols = [bol for bol in bol_numbers if bol in processed_text]
            print(f"BOL patterns found: {found_bols}")
            
            # Extract structured data
            structured_data = extractor.llm_refiner.extract_bol_data(processed_text, supplier_name)
            
            if not structured_data:
                print("No structured data extracted")
                continue
                
            # Handle response format
            if isinstance(structured_data, dict) and 'coils' in structured_data:
                page_coils = structured_data['coils']
            elif isinstance(structured_data, list):
                page_coils = structured_data
            else:
                print(f"Unexpected response format: {type(structured_data)}")
                continue
                
            print(f"Extracted {len(page_coils)} coils:")
            
            for j, coil in enumerate(page_coils):
                coil_tag = coil.get('COIL_TAG#', coil.get('COIL_TAG', 'MISSING'))
                width = coil.get('WIDTH', 'MISSING')
                thickness = coil.get('THICKNESS', 'MISSING')
                weight = coil.get('WEIGHT', 'MISSING')
                bol_num = coil.get('BOL_NUMBER', 'MISSING')
                
                print(f"  Coil {j+1}: Tag={coil_tag}, Width={width}, Thickness={thickness}, Weight={weight}, BOL={bol_num}")
                
                # Add to overall list
                all_coils.append({
                    'page': i + 1,
                    'coil_index': j + 1,
                    'tag': coil_tag,
                    'width': width,
                    'thickness': thickness,
                    'weight': weight,
                    'bol_number': bol_num,
                    'full_data': coil
                })
        
        print(f"\n" + "=" * 60)
        print(f"SUMMARY: {len(all_coils)} total coils extracted")
        
        # Group by BOL number
        bol_groups = {}
        for coil in all_coils:
            bol = coil['bol_number']
            if bol not in bol_groups:
                bol_groups[bol] = []
            bol_groups[bol].append(coil)
        
        print(f"BOL groups: {list(bol_groups.keys())}")
        for bol, coils in bol_groups.items():
            print(f"  {bol}: {len(coils)} coils")
        
        # Check for issues
        print("\nISSUE ANALYSIS:")
        
        # Check for coils without tags
        no_tag_coils = [c for c in all_coils if c['tag'] in ['MISSING', '', None]]
        if no_tag_coils:
            print(f"⚠️ {len(no_tag_coils)} coils without tags (will create empty rows)")
        
        # Check for width issues
        width_8_coils = [c for c in all_coils if '8' in str(c['width'])]
        width_5_coils = [c for c in all_coils if '5' in str(c['width'])]
        
        print(f"Coils with width containing '8': {len(width_8_coils)}")
        print(f"Coils with width containing '5': {len(width_5_coils)}")
        
        if width_5_coils:
            print("Coils showing 5\" width:")
            for coil in width_5_coils:
                print(f"  Page {coil['page']}, Tag: {coil['tag']}, Width: {coil['width']}")
        
        # Cleanup
        extractor.pdf_splitter.cleanup_temp_files()
        
        return all_coils
        
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    debug_extraction()