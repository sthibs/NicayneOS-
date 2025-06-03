"""
Create the FINISHED_TAGS sheet in the Nicayne System Sheets
"""
import os
import json
from bol_extractor.config import Config
from bol_extractor.google_sheets_writer import GoogleSheetsWriter

def create_finished_tags_sheet():
    """Create the FINISHED_TAGS sheet with proper headers"""
    try:
        print("Creating FINISHED_TAGS sheet...")
        
        # Initialize configuration and sheets writer
        config = Config()
        sheets_writer = GoogleSheetsWriter(config)
        
        if not sheets_writer.client:
            print("Error: Google Sheets connection not available")
            return
            
        # Get the spreadsheet
        spreadsheet = sheets_writer.client.open_by_key(config.spreadsheet_id)
        print(f"Connected to spreadsheet: {spreadsheet.title}")
        
        # Check if FINISHED_TAGS sheet already exists
        try:
            existing_sheet = spreadsheet.worksheet("FINISHED_TAGS")
            print("FINISHED_TAGS sheet already exists")
            return
        except:
            print("FINISHED_TAGS sheet doesn't exist, creating it...")
        
        # Define headers for finished tags tracking
        headers = [
            "Tag_ID",
            "Date", 
            "Work_Order_Number",
            "Customer_Name",
            "Customer_PO",
            "Material_Grade",
            "Material_Description",
            "Pieces_or_Coils",
            "Finished_Weight",
            "Heat_Numbers",
            "Operator_Initials",
            "Incoming_Tags",
            "Created_At",
            "PDF_Generated",
            "Drive_Upload_Status"
        ]
        
        # Create the FINISHED_TAGS sheet
        finished_tags_sheet = spreadsheet.add_worksheet(
            title="FINISHED_TAGS", 
            rows=1000, 
            cols=len(headers)
        )
        
        # Add headers to the new sheet
        finished_tags_sheet.insert_row(headers, 1)
        
        # Format the header row
        finished_tags_sheet.format("1:1", {
            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.2},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
        })
        
        print(f"✓ FINISHED_TAGS sheet created successfully with {len(headers)} columns")
        print(f"Headers: {', '.join(headers)}")
        
        return True
        
    except Exception as e:
        print(f"Error creating FINISHED_TAGS sheet: {str(e)}")
        return False

if __name__ == "__main__":
    create_finished_tags_sheet()