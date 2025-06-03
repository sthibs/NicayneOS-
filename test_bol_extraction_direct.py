#!/usr/bin/env python3
"""
Direct test of BOL extraction to isolate the issue
"""

import os
import sys

def test_bol_extraction():
    """Test BOL extraction directly on uploaded files"""
    try:
        print("=== DIRECT BOL EXTRACTION TEST ===")
        
        # Check if there are uploaded files to test with
        upload_dir = "uploads"
        if not os.path.exists(upload_dir):
            print("❌ No uploads directory found")
            return
            
        pdf_files = [f for f in os.listdir(upload_dir) if f.endswith('.pdf')]
        if not pdf_files:
            print("❌ No PDF files in uploads directory")
            return
            
        print(f"✅ Found {len(pdf_files)} PDF files")
        latest_file = pdf_files[-1]  # Get most recent
        filepath = os.path.join(upload_dir, latest_file)
        print(f"Testing with: {latest_file}")
        
        # Test BOL extractor import
        try:
            from bol_extractor.config import Config
            from bol_extractor.extractor import BOLExtractor
            print("✅ BOL extractor modules imported successfully")
        except Exception as e:
            print(f"❌ Failed to import BOL extractor: {e}")
            return
            
        # Test config creation
        try:
            config = Config()
            print("✅ Config created successfully")
        except Exception as e:
            print(f"❌ Failed to create config: {e}")
            return
            
        # Test extractor initialization
        try:
            extractor = BOLExtractor(config)
            print("✅ BOL extractor initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize extractor: {e}")
            return
            
        # Test PDF processing
        try:
            print(f"🔄 Processing PDF: {filepath}")
            result = extractor.process_bol_pdf(filepath)
            print(f"✅ Processing completed")
            print(f"📊 Result: {result}")
            
            if result.get('success'):
                extracted_count = result.get('extracted_coils', 0)
                written_count = result.get('coils_written', 0)
                print(f"🎉 SUCCESS: Extracted {extracted_count} coils, wrote {written_count} to sheets")
            else:
                error_msg = result.get('error', 'Unknown error')
                print(f"⚠️ PROCESSING FAILED: {error_msg}")
                
        except Exception as e:
            print(f"❌ Processing error: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bol_extraction()