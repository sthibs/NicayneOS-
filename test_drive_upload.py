#!/usr/bin/env python3
"""
Test Google Drive upload functionality to diagnose why files aren't appearing
"""

import os
import json
from drive_utils import DriveUploader

def test_drive_connection():
    """Test if we can actually connect to and write to Google Drive"""
    try:
        print("=== Google Drive Connection Test ===")
        
        # Initialize the drive uploader
        uploader = DriveUploader()
        print("✓ DriveUploader initialized successfully")
        
        # Test creating a simple folder
        print("\n=== Testing Folder Creation ===")
        test_folder_name = "TEST_FOLDER_DELETE_ME"
        
        # Try to create folder in root
        folder_id = uploader.create_or_get_folder(test_folder_name)
        if folder_id:
            print(f"✓ Test folder created/found: {test_folder_name}")
            print(f"  Folder ID: {folder_id}")
            
            # Try to list folders to verify it exists
            try:
                results = uploader.service.files().list(
                    q=f"name='{test_folder_name}' and mimeType='application/vnd.google-apps.folder'",
                    fields="files(id, name, parents)"
                ).execute()
                
                folders = results.get('files', [])
                print(f"  Found {len(folders)} folder(s) with this name")
                for folder in folders:
                    print(f"    - {folder['name']} (ID: {folder['id']})")
                    
            except Exception as e:
                print(f"✗ Error listing folders: {e}")
        else:
            print("✗ Failed to create test folder")
            
        # Test the folder structure secrets
        print("\n=== Testing Folder Structure Secrets ===")
        caios_root = os.environ.get('CAIOS_ROOT_FOLDER_URL', 'Not set')
        clients_folder = os.environ.get('CLIENTS_FOLDER_URL', 'Not set')
        customers_folder = os.environ.get('CUSTOMERS_FOLDER_URL', 'Not set')
        
        print(f"CAIOS_ROOT_FOLDER_URL: {caios_root}")
        print(f"CLIENTS_FOLDER_URL: {clients_folder}")
        print(f"CUSTOMERS_FOLDER_URL: {customers_folder}")
        
        # Test accessing the customer folder
        if customers_folder != 'Not set':
            try:
                customer_folder_id = uploader.get_folder_id('CUSTOMERS_FOLDER_URL')
                print(f"✓ Customer folder ID extracted: {customer_folder_id}")
                
                # Try to list contents of customer folder
                results = uploader.service.files().list(
                    q=f"'{customer_folder_id}' in parents",
                    fields="files(id, name, mimeType)"
                ).execute()
                
                files = results.get('files', [])
                print(f"✓ Customer folder contains {len(files)} items:")
                for file in files[:5]:  # Show first 5 items
                    print(f"    - {file['name']} ({file['mimeType']})")
                    
            except Exception as e:
                print(f"✗ Error accessing customer folder: {e}")
        
        return True
        
    except Exception as e:
        print(f"✗ Drive connection test failed: {e}")
        return False

if __name__ == "__main__":
    test_drive_connection()