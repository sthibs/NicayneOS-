#!/usr/bin/env python3
"""
Test Google Drive file permissions and access
"""

import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def test_file_permissions():
    """Test permissions on a recently created file"""
    
    # Load service account credentials
    service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY_NMP'))
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, 
        scopes=['https://www.googleapis.com/auth/drive']
    )
    
    # Build Drive service
    service = build('drive', 'v3', credentials=credentials)
    
    # Test with the latest invoice file ID
    file_id = "10mSlSrieaxPfi99HB58nh6AIYJVjNHlT"  # Latest invoice
    
    try:
        # Get file metadata
        file_metadata = service.files().get(fileId=file_id, fields='id,name,permissions,webViewLink').execute()
        print(f"File: {file_metadata.get('name')}")
        print(f"File ID: {file_metadata.get('id')}")
        print(f"Web View Link: {file_metadata.get('webViewLink')}")
        
        # Check permissions
        permissions = service.permissions().list(fileId=file_id).execute()
        print(f"\nPermissions:")
        for perm in permissions.get('permissions', []):
            print(f"  Type: {perm.get('type')}, Role: {perm.get('role')}, Email: {perm.get('emailAddress')}")
            
        # Try to make it publicly viewable as a test
        print(f"\nAttempting to make file publicly viewable...")
        public_permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        
        result = service.permissions().create(
            fileId=file_id,
            body=public_permission
        ).execute()
        
        print(f"Public permission created: {result}")
        
        # Get updated file metadata
        file_metadata = service.files().get(fileId=file_id, fields='webViewLink').execute()
        print(f"Updated Web View Link: {file_metadata.get('webViewLink')}")
        
    except Exception as e:
        print(f"Error testing permissions: {e}")

if __name__ == "__main__":
    test_file_permissions()