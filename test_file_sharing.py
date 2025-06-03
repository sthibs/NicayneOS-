#!/usr/bin/env python3
"""
Test the file sharing functionality with user email
"""

import os
from drive_utils import DriveUploader

def test_file_sharing():
    """Test if we can share files with the user email"""
    try:
        print("=== Testing File Sharing ===")
        
        # Check if user email is available
        user_email = os.environ.get('USER_EMAIL_ADDRESS')
        print(f"User email: {user_email}")
        
        if not user_email:
            print("✗ No user email configured")
            return False
        
        # Initialize uploader
        uploader = DriveUploader()
        
        # Test sharing the most recent TIMBERLEA invoice
        # File ID from the latest logs: 1KBMgDI6DFK_yZbNwNdCo88IoBwyp5OoI
        test_file_id = "1KBMgDI6DFK_yZbNwNdCo88IoBwyp5OoI"
        
        print(f"Testing file sharing for file ID: {test_file_id}")
        result = uploader.share_file_with_user(test_file_id)
        
        if result:
            print("✓ File sharing test successful")
            return True
        else:
            print("✗ File sharing test failed")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_file_sharing()