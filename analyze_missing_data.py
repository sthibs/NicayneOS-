#!/usr/bin/env python3
"""
Analyze the 5-page PDF to identify what coil data was missed during extraction
"""

import fitz  # PyMuPDF
import re
import json

def analyze_missing_coils():
    """Compare PDF content with extraction results to find missed data."""
    
    pdf_path = "attached_assets/MAK TEST BOL 5 PAGE.pdf"
    
    try:
        # Open PDF and extract text from each page
        doc = fitz.open(pdf_path)
        
        print("=== DETAILED PAGE ANALYSIS ===\n")
        
        total_potential_coils = 0
        all_found_patterns = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            
            print(f"--- PAGE {page_num + 1} ANALYSIS ---")
            
            # Find BOL number
            bol_pattern = r'BILL OF LADING #:?\s*(\d+)'
            bol_matches = re.findall(bol_pattern, page_text, re.IGNORECASE)
            if bol_matches:
                print(f"BOL Number: {bol_matches[0]}")
            
            # Look for coil data patterns - thickness, width, weight combinations
            # Pattern 1: Standard format with decimals
            coil_pattern1 = r'(\d+\.\d+)\s+(\d+\.\d+)\s+(?:Coil|Trail)\s+(\d+,?\d+)'
            matches1 = re.findall(coil_pattern1, page_text)
            
            # Pattern 2: Look for lines with customer tags and measurements
            tag_pattern = r'(\d{7})\s.*?(\d+\.\d+)\s+(\d+\.\d+)\s.*?(\d+,?\d+)'
            tag_matches = re.findall(tag_pattern, page_text)
            
            # Pattern 3: Look for any numeric patterns that might be coil data
            numeric_pattern = r'(\d+\.\d{4})\s+(\d+\.\d{4})\s+\w+\s+(\d+,?\d+)'
            numeric_matches = re.findall(numeric_pattern, page_text)
            
            print(f"Standard coil patterns found: {len(matches1)}")
            for i, match in enumerate(matches1):
                thickness, width, weight = match
                print(f"  Coil {i+1}: Thickness={thickness}, Width={width}, Weight={weight}")
                all_found_patterns.append({
                    'page': page_num + 1,
                    'thickness': thickness,
                    'width': width, 
                    'weight': weight,
                    'type': 'standard'
                })
            
            print(f"Tag-based patterns found: {len(tag_matches)}")
            for i, match in enumerate(tag_matches):
                tag, thickness, width, weight = match
                print(f"  Tag {tag}: Thickness={thickness}, Width={width}, Weight={weight}")
                all_found_patterns.append({
                    'page': page_num + 1,
                    'tag': tag,
                    'thickness': thickness,
                    'width': width,
                    'weight': weight,
                    'type': 'tagged'
                })
            
            print(f"Numeric patterns found: {len(numeric_matches)}")
            for i, match in enumerate(numeric_matches):
                thickness, width, weight = match
                print(f"  Pattern {i+1}: Thickness={thickness}, Width={width}, Weight={weight}")
                all_found_patterns.append({
                    'page': page_num + 1,
                    'thickness': thickness,
                    'width': width,
                    'weight': weight,
                    'type': 'numeric'
                })
            
            page_total = len(matches1) + len(tag_matches) + len(numeric_matches)
            total_potential_coils += page_total
            print(f"Total potential coils on page {page_num + 1}: {page_total}")
            
            # Look for any customer tag numbers
            customer_tags = re.findall(r'[Y]?(\d{7})', page_text)
            if customer_tags:
                print(f"Customer tags found: {customer_tags}")
            
            print()
        
        doc.close()
        
        print(f"=== SUMMARY ===")
        print(f"Total potential coil entries found across all pages: {total_potential_coils}")
        print(f"System extracted: 13 coils")
        print(f"Potential missing: {total_potential_coils - 13}")
        
        print(f"\n=== ALL DETECTED PATTERNS ===")
        for i, pattern in enumerate(all_found_patterns):
            print(f"{i+1}. Page {pattern['page']}: {pattern}")
        
        # Deduplicate patterns that might be the same coil
        unique_patterns = []
        for pattern in all_found_patterns:
            is_duplicate = False
            for existing in unique_patterns:
                if (pattern.get('width') == existing.get('width') and 
                    pattern.get('thickness') == existing.get('thickness') and
                    pattern.get('weight') == existing.get('weight')):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_patterns.append(pattern)
        
        print(f"\n=== UNIQUE COIL PATTERNS (after deduplication) ===")
        print(f"Unique patterns found: {len(unique_patterns)}")
        for i, pattern in enumerate(unique_patterns):
            print(f"{i+1}. {pattern}")
        
        print(f"\nFINAL ANALYSIS:")
        print(f"- Unique coil patterns detected: {len(unique_patterns)}")
        print(f"- System extracted: 13")
        print(f"- Potential discrepancy: {len(unique_patterns) - 13}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_missing_coils()