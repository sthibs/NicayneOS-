"""
Google Sheets integration for writing BOL data.
Handles authentication and data writing to specified spreadsheet.
"""

import json
import logging
from typing import Dict, Any, List
import gspread
from google.oauth2.service_account import Credentials
from .config import Config

logger = logging.getLogger(__name__)

class GoogleSheetsWriter:
    """Google Sheets integration for BOL data output."""
    
    def __init__(self, config: Config):
        """Initialize Google Sheets writer with configuration."""
        self.config = config
        self.client = None
        self.worksheet = None
        
        # Initialize Google Sheets client
        self._initialize_client()
        logger.info("Google Sheets writer initialized")
    
    def _initialize_client(self):
        """Initialize the Google Sheets client with service account credentials."""
        try:
            # Parse service account credentials from config
            if not self.config.google_service_account_key:
                raise ValueError("Google service account key not provided")
            
            # Load credentials from JSON string
            service_account_info = json.loads(self.config.google_service_account_key)
            
            # Define required scopes
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Create credentials object
            credentials = Credentials.from_service_account_info(
                service_account_info, 
                scopes=scopes
            )
            
            # Initialize gspread client
            self.client = gspread.authorize(credentials)
            logger.info("Google Sheets client initialized successfully")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in Google service account key: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {str(e)}")
            raise
    
    def verify_connection(self) -> bool:
        """
        Verify connection to Google Sheets and access to the target spreadsheet.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Google Sheets client not initialized")
                return False
            
            # Try to open the target spreadsheet
            spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)
            logger.info(f"Successfully connected to spreadsheet: {spreadsheet.title}")
            
            # Try to access the first worksheet
            worksheet = spreadsheet.sheet1
            logger.info(f"Successfully accessed worksheet: {worksheet.title}")
            
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets connection verification failed: {str(e)}")
            return False
    
    def append_bol_data_batch(self, bol_data_list: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Append multiple BOL data entries to the Google Sheets spreadsheet in batch.
        
        Args:
            bol_data_list: List of flattened BOL data dictionaries
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            if not self.client:
                return {"success": False, "error": "Google Sheets client not initialized"}
            
            spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)
            
            # Try to access the target worksheet first, fallback to first sheet
            try:
                worksheet = spreadsheet.worksheet(self.config.worksheet_name)
                logger.info(f"Successfully accessed worksheet: {self.config.worksheet_name}")
            except Exception as e:
                worksheet = spreadsheet.sheet1
                logger.warning(f"UNPROCESSED_INVENTORY worksheet not found, using first worksheet: {str(e)}")
            
            if not bol_data_list:
                return {"success": False, "error": "No data to write"}
            
            # Ensure headers exist
            self._ensure_headers(worksheet, bol_data_list[0])
            
            # Prepare rows for batch insert
            rows_to_add = []
            for bol_data in bol_data_list:
                row_data = [bol_data.get(header, '') for header in self.get_header_row()]
                rows_to_add.append(row_data)
            
            # Batch append all rows at once
            worksheet.append_rows(rows_to_add)
            
            logger.info(f"Successfully batch-appended {len(rows_to_add)} BOL records")
            return {
                "success": True, 
                "rows_added": len(rows_to_add),
                "message": f"Batch wrote {len(rows_to_add)} coils"
            }
            
        except Exception as e:
            error_msg = f"Failed to batch append BOL data to Google Sheets: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def append_bol_data(self, bol_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Append BOL data to the Google Sheets spreadsheet.
        
        Args:
            bol_data: Flattened BOL data dictionary
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            # Open the target spreadsheet and get UNPROCESSED_INVENTORY worksheet
            spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)
            
            try:
                worksheet = spreadsheet.worksheet("UNPROCESSED_INVENTORY")
            except Exception as e:
                logger.warning(f"UNPROCESSED_INVENTORY worksheet not found, using first worksheet: {str(e)}")
                worksheet = spreadsheet.sheet1
            
            # Check if headers exist, if not create them
            self._ensure_headers(worksheet, bol_data)
            
            # Get headers to ensure correct column order
            headers = worksheet.row_values(1)
            
            # Create row data in correct order
            row_data = []
            for header in headers:
                value = bol_data.get(header, '')
                row_data.append(str(value))
            
            # Append the row
            worksheet.append_row(row_data)
            
            # Get the row number of the added data
            row_number = len(worksheet.get_all_values())
            
            logger.info(f"Successfully appended BOL data to row {row_number}")
            
            return {
                'success': True,
                'row_number': row_number,
                'spreadsheet_title': spreadsheet.title,
                'worksheet_title': worksheet.title
            }
            
        except Exception as e:
            error_msg = f"Failed to append BOL data to Google Sheets: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _ensure_headers(self, worksheet, bol_data: Dict[str, str]):
        """
        Ensure the worksheet has proper headers.
        
        Args:
            worksheet: Google Sheets worksheet object
            bol_data: BOL data dictionary to get headers from
        """
        try:
            # Get current headers
            existing_headers = worksheet.row_values(1) if worksheet.row_count > 0 else []
            
            # Define expected headers based on BOL data keys
            expected_headers = list(bol_data.keys())
            
            # If no headers exist or headers don't match, set them
            if not existing_headers or set(existing_headers) != set(expected_headers):
                logger.info("Setting up headers in Google Sheets")
                
                # Clear first row and set headers
                if worksheet.row_count > 0:
                    worksheet.delete_rows(1)
                
                worksheet.insert_row(expected_headers, 1)
                logger.info(f"Headers set: {expected_headers}")
            
        except Exception as e:
            logger.warning(f"Could not ensure headers: {str(e)}")
            # Continue anyway, let append_row handle it
    
    def get_all_bol_data(self) -> List[Dict[str, str]]:
        """
        Retrieve all BOL data from the spreadsheet.
        
        Returns:
            List of BOL data dictionaries
        """
        try:
            spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)
            worksheet = spreadsheet.sheet1
            
            # Get all records
            records = worksheet.get_all_records()
            
            logger.info(f"Retrieved {len(records)} BOL records from spreadsheet")
            return records
            
        except Exception as e:
            logger.error(f"Failed to retrieve BOL data: {str(e)}")
            return []
    
    def update_validation_status(self, row_number: int, status: str) -> bool:
        """
        Update the validation status for a specific row.
        
        Args:
            row_number: Row number to update (1-indexed)
            status: New validation status
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)
            worksheet = spreadsheet.sheet1
            
            # Find the VALIDATION_STATUS column
            headers = worksheet.row_values(1)
            if 'VALIDATION_STATUS' not in headers:
                logger.error("VALIDATION_STATUS column not found")
                return False
            
            status_col = headers.index('VALIDATION_STATUS') + 1
            
            # Update the cell
            worksheet.update_cell(row_number, status_col, status)
            
            logger.info(f"Updated validation status for row {row_number} to: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update validation status: {str(e)}")
            return False
    
    def create_backup_sheet(self) -> bool:
        """
        Create a backup worksheet with current timestamp.
        
        Returns:
            True if backup created successfully, False otherwise
        """
        try:
            from datetime import datetime
            
            spreadsheet = self.client.open_by_key(self.config.spreadsheet_id)
            
            # Create backup sheet name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"Backup_{timestamp}"
            
            # Duplicate the main sheet
            source_sheet = spreadsheet.sheet1
            backup_sheet = spreadsheet.duplicate_sheet(
                source_sheet.id, 
                new_sheet_name=backup_name
            )
            
            logger.info(f"Created backup sheet: {backup_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create backup sheet: {str(e)}")
            return False
    
    def get_header_row(self) -> List[str]:
        """
        Get the standard header row for BOL data.
        
        Returns:
            List of column headers
        """
        return [
            'BOL_NUMBER',
            'CUSTOMER_NAME', 
            'VENDOR_NAME',
            'COIL_TAG#',
            'MATERIAL',
            'WIDTH',
            'THICKNESS', 
            'WEIGHT',
            'NUMBER_OF_COILS',
            'DATE_RECEIVED',
            'HEAT_NUMBER',
            'CUSTOMER_PO',
            'NOTES',
            'VALIDATION_STATUS'
        ]
