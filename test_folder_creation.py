#!/usr/bin/env python3
"""
Test script to verify the Google Drive folder structure creation functionality.
"""

from drive_utils import DriveUploader
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

def test_po_folder_creation():
    """Test creating a complete PO folder structure."""
    print("Testing Google Drive PO folder structure creation...")
    
    # Initialize the Drive uploader
    drive_uploader = DriveUploader()
    
    if not drive_uploader.service:
        print("Google Drive service not available - check credentials")
        return
    
    # Test data
    test_customer = "Test Manufacturing Corp"
    test_po = "PO-TEST-2025-001"
    
    print(f"Creating folder structure for: {test_customer}, PO: {test_po}")
    
    try:
        result = drive_uploader.create_po_folder_structure(test_customer, test_po)
        
        if result:
            print("\n✅ Folder structure created successfully!")
            print(f"Full path: {result['full_path']}")
            print(f"PO folder ID: {result['po_folder_id']}")
            print(f"Customer folder ID: {result['customer_folder_id']}")
            print("Subfolders created:")
            for name, folder_id in result['subfolders'].items():
                print(f"  - {name}: {folder_id}")
        else:
            print("❌ Failed to create folder structure")
            
    except Exception as e:
        print(f"❌ Error during folder creation: {str(e)}")

if __name__ == "__main__":
    test_po_folder_creation()