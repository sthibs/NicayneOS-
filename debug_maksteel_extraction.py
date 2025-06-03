#!/usr/bin/env python3
"""
Debug script to analyze Maksteel extraction without Google Sheets writes.
This will show us exactly what data is being extracted and why we're getting extra rows.
"""

import sys
import os
sys.path.append('.')

from bol_extractor import BOLExtractor, Config
import json

def debug_maksteel_extraction():
    """Extract and display data from the Maksteel PDF without writing to sheets."""
    
    # Use the test PDF
    pdf_path = "attached_assets/MAK TEST BOL 3 PAGE.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found at: {pdf_path}")
        return
        
    print(f"🔍 Analyzing: {pdf_path}")
    print("=" * 60)
    
    # Initialize config and extractor
    config = Config()
    extractor = BOLExtractor(config)
    
    # Extract data using supplier-specific processing
    result = extractor.process_bol_pdf_with_supplier(pdf_path, "maksteel")
    
    if not result.get('success'):
        print(f"❌ Extraction failed: {result.get('error', 'Unknown error')}")
        return
    
    coils = result.get('data', {}).get('coils', [])
    print(f"📊 Total coils extracted: {len(coils)}")
    print("=" * 60)
    
    # Analyze each coil
    for i, coil in enumerate(coils, 1):
        print(f"\n🔧 COIL {i}:")
        print(f"   BOL Number: {coil.get('BOL_NUMBER', 'MISSING')}")
        print(f"   Customer Tag: {coil.get('COIL_TAG#', 'MISSING')}")
        print(f"   Width: {coil.get('WIDTH', 'MISSING')}")
        print(f"   Thickness: {coil.get('THICKNESS', 'MISSING')}")
        print(f"   Weight: {coil.get('WEIGHT', 'MISSING')}")
        print(f"   Heat Number: {coil.get('HEAT_NUMBER', 'MISSING')}")
        print(f"   Material: {coil.get('MATERIAL', 'MISSING')}")
        
        # Check for incomplete entries
        required_fields = ['COIL_TAG#', 'WIDTH', 'THICKNESS', 'WEIGHT']
        missing_fields = []
        
        for field in required_fields:
            value = str(coil.get(field, '')).strip()
            if not value or value in ['', 'Unknown', 'MISSING', None, 'null', 'undefined']:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"   ⚠️  INCOMPLETE - Missing: {', '.join(missing_fields)}")
        
        # Check customer tag validity
        coil_tag = str(coil.get('COIL_TAG#', '')).strip()
        if not any(char.isdigit() for char in coil_tag):
            print(f"   ⚠️  INVALID TAG - No numeric digits: '{coil_tag}'")
            
        # Check width accuracy
        width = coil.get('WIDTH', '')
        if '5' in str(width) and '8' not in str(width):
            print(f"   ⚠️  SUSPICIOUS WIDTH - Shows 5 instead of expected 8: '{width}'")
        
        print(f"   Status: {'✅ VALID' if not missing_fields and any(char.isdigit() for char in coil_tag) else '❌ INVALID'}")
    
    print("\n" + "=" * 60)
    print("🎯 SUMMARY:")
    
    valid_coils = []
    invalid_coils = []
    
    for coil in coils:
        coil_tag = str(coil.get('COIL_TAG#', '')).strip()
        width = str(coil.get('WIDTH', '')).strip()
        thickness = str(coil.get('THICKNESS', '')).strip()
        weight = str(coil.get('WEIGHT', '')).strip()
        
        # Apply the same validation logic as the extractor
        invalid_values = ['', 'Unknown', 'MISSING', None, 'null', 'undefined', '0', '0.0', '0.00']
        
        if (not any(char.isdigit() for char in coil_tag) or 
            coil_tag in invalid_values or
            width in invalid_values or
            thickness in invalid_values or
            weight in invalid_values):
            invalid_coils.append(coil)
        else:
            valid_coils.append(coil)
    
    print(f"   Valid coils that should be processed: {len(valid_coils)}")
    print(f"   Invalid coils that should be skipped: {len(invalid_coils)}")
    
    if invalid_coils:
        print(f"\n❌ Invalid coils causing extra rows:")
        for i, coil in enumerate(invalid_coils, 1):
            print(f"   {i}. Tag='{coil.get('COIL_TAG#', 'MISSING')}', Width='{coil.get('WIDTH', 'MISSING')}'")
    
    # Check for width accuracy issues
    width_issues = []
    for coil in valid_coils:
        width = str(coil.get('WIDTH', ''))
        if '5' in width and '8' not in width:
            width_issues.append(f"Tag {coil.get('COIL_TAG#')}: {width}")
    
    if width_issues:
        print(f"\n⚠️  Width accuracy issues found:")
        for issue in width_issues:
            print(f"   {issue}")

if __name__ == "__main__":
    debug_maksteel_extraction()