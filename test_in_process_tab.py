#!/usr/bin/env python3
"""
Test script to create the IN_PROCESS tab and test inventory matching
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from bol_extractor.config import Config

def create_in_process_tab():
    """Create the IN_PROCESS tab and test the inventory matching system"""
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
        
        # Get unprocessed inventory worksheet
        unprocessed = sheet.worksheet("UNPROCESSED_INVENTORY")
        print(f"✓ Found UNPROCESSED_INVENTORY worksheet")
        
        # Get headers from unprocessed
        headers = unprocessed.row_values(1)
        print(f"✓ Headers from UNPROCESSED_INVENTORY: {headers}")
        
        # Try to get or create IN_PROCESS worksheet
        try:
            in_process = sheet.worksheet("IN_PROCESS")
            print(f"✓ Found existing 'IN_PROCESS' worksheet")
        except gspread.exceptions.WorksheetNotFound:
            print(f"! 'IN_PROCESS' worksheet not found, creating it...")
            in_process = sheet.add_worksheet(title="IN_PROCESS", rows=1000, cols=20)
            print(f"✓ Created 'IN_PROCESS' worksheet")
            
            # Copy headers from unprocessed to in-process
            if headers:
                in_process.append_row(headers)
                print(f"✓ Copied headers to IN_PROCESS")
        
        # Check current data in unprocessed
        all_data = unprocessed.get_all_records()
        print(f"✓ Found {len(all_data)} rows in UNPROCESSED_INVENTORY")
        
        if all_data:
            print(f"Sample row: {all_data[0]}")
            
            # Look for coil tag columns
            tag_col_names = ["Coil Tag", "CoilTag", "Coil_Tag", "Tag", "Heat Number"]
            found_tag_col = None
            for col_name in tag_col_names:
                if col_name in headers:
                    found_tag_col = col_name
                    break
            
            if found_tag_col:
                print(f"✓ Found coil tag column: {found_tag_col}")
                # Show some sample tags
                sample_tags = []
                for row in all_data[:5]:  # Show first 5 tags
                    tag = row.get(found_tag_col, "")
                    if tag:
                        sample_tags.append(tag)
                print(f"  Sample tags: {sample_tags}")
            else:
                print(f"! No coil tag column found. Available columns: {headers}")
        
        print(f"\n🎉 IN_PROCESS tab setup complete!")
        print(f"   You should now see an 'IN_PROCESS' tab in your Google Sheet.")
        print(f"   This tab will be used to track coils that are matched with work orders.")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_in_process_tab()