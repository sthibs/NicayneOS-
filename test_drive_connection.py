#!/usr/bin/env python3
"""
Test Google Drive connection using CAIOS credentials
"""

import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def test_drive_connection():
    """Test Google Drive API connection"""
    try:
        # Load CAIOS credentials
        google_creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_CAIOS_NMP")
        if not google_creds_json:
            print("❌ GOOGLE_SERVICE_ACCOUNT_KEY_CAIOS_NMP not found")
            return False
        
        # Parse credentials
        creds_info = json.loads(google_creds_json)
        
        # Set up Google credentials with Drive scope
        scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/spreadsheets'
        ]
        
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=scopes
        )
        
        # Build Drive service
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Test connection by listing files (limited to 5 items)
        results = drive_service.files().list(pageSize=5, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        print("✅ Google Drive connection successful!")
        print(f"Found {len(files)} accessible files")
        
        if files:
            print("Sample files:")
            for file in files[:3]:
                print(f"  - {file['name']} (ID: {file['id']})")
        
        return True
        
    except Exception as e:
        print(f"❌ Google Drive connection failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_drive_connection()