#!/usr/bin/env python3
"""
Test access to the NMP folder and ability to create customer structure
"""

import os
from drive_utils import DriveUploader, get_folder_id

def test_nmp_folder_access():
    """Test if we can access and write to the NMP folder"""
    try:
        print("=== Testing NMP Folder Access ===")
        
        # Initialize uploader
        uploader = DriveUploader()
        print("✓ DriveUploader initialized")
        
        # Get the NMP folder ID from your secret
        nmp_folder_id = get_folder_id("NMP_FOLDER_URL")
        print(f"✓ NMP Folder ID: {nmp_folder_id}")
        
        # Test if we can list contents of NMP folder
        print("\n=== Listing NMP Folder Contents ===")
        try:
            results = uploader.service.files().list(
                q=f"'{nmp_folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType)"
            ).execute()
            
            files = results.get('files', [])
            print(f"✓ NMP folder contains {len(files)} items:")
            for file in files:
                print(f"    - {file['name']} ({file['mimeType']})")
                
        except Exception as e:
            print(f"✗ Error listing NMP folder contents: {e}")
            return False
        
        # Test if we can create a Customers folder
        print("\n=== Testing Customers Folder Creation ===")
        try:
            customers_folder_id = uploader.create_or_get_folder("Customers", nmp_folder_id)
            if customers_folder_id:
                print(f"✓ Customers folder ID: {customers_folder_id}")
                
                # Test creating a test customer folder
                test_customer_id = uploader.create_or_get_folder("TEST_CUSTOMER", customers_folder_id)
                if test_customer_id:
                    print(f"✓ Test customer folder ID: {test_customer_id}")
                    
                    # Test creating a PO folder
                    test_po_id = uploader.create_or_get_folder("PO#TEST123", test_customer_id)
                    if test_po_id:
                        print(f"✓ Test PO folder ID: {test_po_id}")
                        print("✓ Full folder structure creation successful!")
                        return True
                    else:
                        print("✗ Failed to create test PO folder")
                else:
                    print("✗ Failed to create test customer folder")
            else:
                print("✗ Failed to create Customers folder")
                
        except Exception as e:
            print(f"✗ Error creating folder structure: {e}")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_nmp_folder_access()