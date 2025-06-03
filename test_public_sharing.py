#!/usr/bin/env python3
"""
Test the new public sharing approach
"""

import os
from drive_utils import DriveUploader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_test_pdf():
    """Create a simple test PDF"""
    filename = "test_public_access.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, "Test PDF for Public Access")
    c.drawString(100, 730, "This file should be accessible via Google Drive link")
    c.save()
    return filename

def test_public_sharing():
    """Test public sharing workflow"""
    print("Creating test PDF...")
    pdf_path = create_test_pdf()
    
    print("Initializing Drive uploader...")
    uploader = DriveUploader()
    
    if not uploader.service:
        print("❌ Drive service not initialized")
        return
    
    print("Uploading test PDF...")
    try:
        # Upload to a test customer folder
        result = uploader.upload_finished_tag_pdf(
            pdf_path, 
            "TEST_PUBLIC_ACCESS", 
            "TEST123"
        )
        
        if result:
            print(f"✅ Test file uploaded successfully!")
            print(f"Drive URL: {result}")
            print("\nPlease test this link in an incognito browser window:")
            print(f"🔗 {result}")
        else:
            print("❌ Upload failed")
            
    except Exception as e:
        print(f"❌ Error during upload: {e}")
    
    finally:
        # Clean up local file
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

if __name__ == "__main__":
    test_public_sharing()