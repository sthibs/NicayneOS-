"""
Create the PROCESSED inventory sheet in the Nicayne System Sheets
"""
import os
import json
from bol_extractor.config import Config
from bol_extractor.google_sheets_writer import GoogleSheetsWriter

def create_processed_sheet():
    """Create the PROCESSED inventory sheet with proper headers"""
    try:
        print("Creating PROCESSED inventory sheet...")
        
        # Initialize configuration and sheets writer
        config = Config()
        sheets_writer = GoogleSheetsWriter(config)
        
        if not sheets_writer.client:
            print("Error: Google Sheets connection not available")
            return
            
        # Get the spreadsheet
        spreadsheet = sheets_writer.client.open_by_key(config.spreadsheet_id)
        print(f"Connected to spreadsheet: {spreadsheet.title}")
        
        # Check if PROCESSED sheet already exists
        try:
            existing_sheet = spreadsheet.worksheet("PROCESSED")
            print("PROCESSED sheet already exists")
            return
        except:
            print("PROCESSED sheet doesn't exist, creating it...")
        
        # Get headers from IN_PROCESS sheet to match structure
        try:
            in_process_sheet = spreadsheet.worksheet("IN_PROCESS")
            headers = in_process_sheet.row_values(1)
            print(f"Using headers from IN_PROCESS sheet: {headers}")
        except:
            # Fallback headers if IN_PROCESS doesn't exist
            headers = [
                "BOL Number", "Date", "Customer", "Customer Tag", "Tag #", 
                "Width", "Thickness", "Grade", "Weight", "Heat Number",
                "PO Number", "Supplier", "Coil Count"
            ]
            print(f"Using fallback headers: {headers}")
        
        # Add tracking columns for processed inventory
        tracking_headers = ["Processed_Date", "Finished_Tag_ID", "Status"]
        all_headers = headers + tracking_headers
        
        # Create the PROCESSED sheet
        processed_sheet = spreadsheet.add_worksheet(
            title="PROCESSED", 
            rows=1000, 
            cols=len(all_headers)
        )
        
        # Add headers to the new sheet
        processed_sheet.insert_row(all_headers, 1)
        
        # Format the header row
        processed_sheet.format("1:1", {
            "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.8},
            "textFormat": {"bold": True}
        })
        
        print(f"✓ PROCESSED sheet created successfully with {len(all_headers)} columns")
        print(f"Headers: {', '.join(all_headers)}")
        
        return True
        
    except Exception as e:
        print(f"Error creating PROCESSED sheet: {str(e)}")
        return False

if __name__ == "__main__":
    create_processed_sheet()