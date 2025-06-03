#!/usr/bin/env python3
"""
Test script to write 10 test lines to the UNPROCESSED_INVENTORY sheet
"""

import os
import json
from datetime import datetime
from bol_extractor.config import Config
from bol_extractor.google_sheets_writer import GoogleSheetsWriter

def create_test_data():
    """Create 10 test BOL records"""
    test_records = []
    
    for i in range(1, 11):
        record = {
            'bol_number': f'BOL-TEST-{i:03d}',
            'customer_name': f'Test Customer {i}',
            'vendor_name': f'Test Vendor {i}',
            'coil_tag': f'CT-{i:04d}',
            'material': f'Steel Grade {i}',
            'width': f'{20 + i}.5',
            'thickness': f'0.{i:02d}5',
            'weight': f'{1000 + i * 100}',
            'date_received': datetime.now().strftime('%Y-%m-%d'),
            'heat_number': f'HN-{i:05d}',
            'customer_po': f'PO-{i:06d}',
            'notes': f'Test record {i} - automated test data'
        }
        test_records.append(record)
    
    return test_records

def main():
    try:
        # Initialize configuration and Google Sheets writer
        config = Config()
        sheets_writer = GoogleSheetsWriter(config)
        
        # Verify connection
        if not sheets_writer.verify_connection():
            print("❌ Failed to connect to Google Sheets")
            return
        
        print("✅ Connected to Google Sheets successfully")
        
        # Create test data
        test_records = create_test_data()
        print(f"📝 Created {len(test_records)} test records")
        
        # Write each record to the sheet
        successful_writes = 0
        for i, record in enumerate(test_records, 1):
            result = sheets_writer.append_bol_data(record)
            
            if result['success']:
                successful_writes += 1
                print(f"✅ Test record {i} written to row {result['row_number']}")
            else:
                print(f"❌ Failed to write test record {i}: {result['error']}")
        
        print(f"\n📊 Summary: {successful_writes}/{len(test_records)} records written successfully")
        
        if successful_writes == len(test_records):
            print("🎉 All test records written successfully to UNPROCESSED_INVENTORY!")
        else:
            print("⚠️ Some test records failed to write")
            
    except Exception as e:
        print(f"❌ Error running test: {str(e)}")

if __name__ == "__main__":
    main()