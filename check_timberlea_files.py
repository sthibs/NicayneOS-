#!/usr/bin/env python3
"""
Check if TIMBERLEA files are actually in Google Drive
"""

import os
from drive_utils import DriveUploader, get_folder_id

def check_timberlea_files():
    """Check for TIMBERLEA files in Google Drive"""
    try:
        print("=== Checking TIMBERLEA Files in Google Drive ===")
        
        uploader = DriveUploader()
        nmp_folder_id = get_folder_id("NMP_FOLDER_URL")
        
        # Get Customers folder ID
        customers_folder_id = uploader.create_or_get_folder("Customers", nmp_folder_id)
        print(f"✓ Customers folder ID: {customers_folder_id}")
        
        # Check if TIMBERLEA folder exists
        timberlea_folder_id = uploader.create_or_get_folder("TIMBERLEA", customers_folder_id)
        if timberlea_folder_id:
            print(f"✓ TIMBERLEA folder ID: {timberlea_folder_id}")
            
            # List contents of TIMBERLEA folder
            results = uploader.service.files().list(
                q=f"'{timberlea_folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType, modifiedTime)"
            ).execute()
            
            files = results.get('files', [])
            print(f"\n=== TIMBERLEA Folder Contents ({len(files)} items) ===")
            for file in files:
                print(f"  - {file['name']} ({file['mimeType']}) - {file['modifiedTime']}")
                
                # If it's a PO folder, check its contents
                if file['mimeType'] == 'application/vnd.google-apps.folder' and 'PO#' in file['name']:
                    po_results = uploader.service.files().list(
                        q=f"'{file['id']}' in parents and trashed=false",
                        fields="files(id, name, mimeType, modifiedTime, webViewLink)"
                    ).execute()
                    
                    po_files = po_results.get('files', [])
                    print(f"    PO Folder '{file['name']}' contains {len(po_files)} files:")
                    for po_file in po_files:
                        print(f"      - {po_file['name']} ({po_file['mimeType']}) - {po_file['modifiedTime']}")
                        print(f"        Link: {po_file.get('webViewLink', 'No link')}")
        else:
            print("✗ TIMBERLEA folder not found")
            
    except Exception as e:
        print(f"✗ Error checking TIMBERLEA files: {e}")

if __name__ == "__main__":
    check_timberlea_files()