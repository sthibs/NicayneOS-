#!/usr/bin/env python3
"""
Test script to write a test line to the UNPROCESSED_INVENTORY sheet
"""

import os
import sys
import json
from datetime import datetime

# Add the bol_extractor module to path
sys.path.insert(0, '.')

from bol_extractor.config import Config
from bol_extractor.google_sheets_writer import GoogleSheetsWriter

def test_write_to_sheet():
    """Write a test line to verify Google Sheets connection"""
    try:
        print("Initializing configuration...")
        config = Config()
        
        print("Initializing Google Sheets writer...")
        sheets_writer = GoogleSheetsWriter(config)
        
        print("Verifying connection...")
        if not sheets_writer.verify_connection():
            print("❌ Connection verification failed")
            return False
        
        # Create test data
        test_data = {
            'BOL_NUMBER': 'TEST-001',
            'CUSTOMER_NAME': 'Test Customer',
            'VENDOR_NAME': 'Test Vendor',
            'COIL_TAG#': 'TEST-TAG-001',
            'MATERIAL': 'Steel',
            'WIDTH': '48 inches',
            'THICKNESS': '0.125 inches',
            'WEIGHT': '2500 lbs',
            'DATE_RECEIVED': datetime.now().strftime('%Y-%m-%d'),
            'HEAT_NUMBER': 'H-TEST-001',
            'CUSTOMER_PO': 'PO-TEST-001',
            'NOTES': 'Test entry from BOL Extractor',
            'VALIDATION_STATUS': 'TEST',
            'PROCESSED_DATE': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print("Writing test data to sheet...")
        result = sheets_writer.append_bol_data(test_data)
        
        if result['success']:
            print(f"✅ Test data written successfully to row {result['row_number']}")
            print(f"Spreadsheet: {result['spreadsheet_title']}")
            print(f"Worksheet: {result['worksheet_title']}")
            return True
        else:
            print(f"❌ Failed to write test data: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {str(e)}")
        return False

if __name__ == '__main__':
    success = test_write_to_sheet()
    sys.exit(0 if success else 1)