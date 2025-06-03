#!/usr/bin/env python3
"""
Test script to verify work order Google Sheets integration
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from bol_extractor.config import Config

def test_work_order_sheet():
    """Test creating work orders sheet and writing data"""
    try:
        # Load configuration
        config = Config()
        print(f"✓ Configuration loaded")
        print(f"  Spreadsheet ID: {config.spreadsheet_id}")
        
        # Set up credentials
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_info(
            json.loads(config.google_service_account_key), scopes=SCOPES
        )
        
        client = gspread.authorize(credentials)
        print(f"✓ Google Sheets client authorized")
        
        # Open spreadsheet
        sheet = client.open_by_key(config.spreadsheet_id)
        print(f"✓ Opened spreadsheet: {sheet.title}")
        
        # List existing worksheets
        worksheets = sheet.worksheets()
        print(f"✓ Found {len(worksheets)} existing worksheets:")
        for ws in worksheets:
            print(f"  - {ws.title}")
        
        # Try to get or create work_orders worksheet
        try:
            ws = sheet.worksheet("work_orders")
            print(f"✓ Found existing 'work_orders' worksheet")
        except gspread.exceptions.WorksheetNotFound:
            print(f"! 'work_orders' worksheet not found, creating it...")
            ws = sheet.add_worksheet(title="work_orders", rows=1000, cols=20)
            print(f"✓ Created 'work_orders' worksheet")
        
        # Test data
        test_data = {
            'work_order_number': 'WO-TEST-001',
            'customer_name': 'Test Customer',
            'quote_number': 'Q-12345',
            'customer_po': 'PO-67890',
            'date_created': '2025-05-31',
            'date_required': '2025-06-15',
            'process_type': 'slitting',
            'tolerance': '±.005"',
            'max_skid_weight': '5000 lbs',
            'pieces_per_skid': '10',
            'max_od': '72 inches',
            'wood_spacers': 'Yes',
            'paper_wrapped': 'No',
            'coil_direction': 'CW',
            'split_coil': 'No',
            'ctl_jobs_count': '0',
            'slitting_jobs_count': '1',
            'notes': 'Test work order for system verification'
        }
        
        # Write headers if sheet is empty
        existing_data = ws.get_all_values()
        if not existing_data:
            print(f"! Sheet is empty, writing headers...")
            ws.append_row(list(test_data.keys()))
            print(f"✓ Headers written")
        else:
            print(f"✓ Sheet has {len(existing_data)} rows (including headers)")
        
        # Write test data
        ws.append_row(list(test_data.values()))
        print(f"✓ Test work order data written to sheet")
        
        # Verify the write
        all_data = ws.get_all_values()
        print(f"✓ Sheet now has {len(all_data)} total rows")
        
        print(f"\n🎉 Work order sheet integration is working!")
        print(f"   You should now see a 'work_orders' tab in your Google Sheet.")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_work_order_sheet()