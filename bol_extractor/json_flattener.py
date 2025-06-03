"""
JSON data flattening and normalization utilities.
Ensures extracted BOL data is properly formatted for Google Sheets.
"""

import logging
from typing import Dict, Any, List
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class JSONFlattener:
    """Utilities for flattening and normalizing BOL data for spreadsheet output."""
    
    def __init__(self):
        """Initialize JSON flattener."""
        self.required_fields = [
            'BOL_NUMBER', 'CUSTOMER_NAME', 'VENDOR_NAME', 'COIL_TAG#',
            'MATERIAL', 'WIDTH', 'THICKNESS', 'WEIGHT', 'NUMBER_OF_COILS', 'DATE_RECEIVED',
            'HEAT_NUMBER', 'CUSTOMER_PO', 'NOTES', 'VALIDATION_STATUS'
        ]
        logger.info("JSON flattener initialized")
    
    def flatten_bol_data(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Flatten and normalize BOL data for Google Sheets output.
        
        Args:
            data: Raw extracted BOL data dictionary
            
        Returns:
            Flattened and normalized data dictionary
        """
        try:
            logger.info("Starting BOL data flattening and normalization")
            
            # Create flattened data structure
            flattened = {}
            
            # Process each required field
            for field in self.required_fields:
                if field == 'VALIDATION_STATUS':
                    # Set default validation status if not present
                    flattened[field] = str(data.get(field, 'PENDING')).strip()
                else:
                    # Get and normalize field value
                    value = data.get(field, '')
                    flattened[field] = self._normalize_field_value(field, value)
            
            # Add processing metadata
            flattened['PROCESSED_DATE'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Validate and clean the flattened data
            flattened = self._validate_and_clean(flattened)
            
            logger.info("BOL data flattening completed successfully")
            return flattened
            
        except Exception as e:
            logger.error(f"Error flattening BOL data: {str(e)}")
            # Return a basic structure with error info
            return self._create_error_record(str(e))
    
    def _normalize_field_value(self, field_name: str, value: Any) -> str:
        """
        Normalize a field value based on its type and expected format.
        
        Args:
            field_name: Name of the field being normalized
            value: Raw field value
            
        Returns:
            Normalized string value
        """
        if value is None:
            return ''
        
        # Convert to string and strip whitespace
        str_value = str(value).strip()
        
        # Field-specific normalization
        if field_name == 'DATE_RECEIVED':
            return self._normalize_date(str_value)
        elif field_name in ['WIDTH', 'THICKNESS', 'WEIGHT']:
            return self._normalize_measurement(str_value)
        elif field_name == 'NUMBER_OF_COILS':
            return self._normalize_coil_count(str_value)
        elif field_name in ['BOL_NUMBER', 'COIL_TAG#', 'HEAT_NUMBER', 'CUSTOMER_PO']:
            return self._normalize_identifier(str_value)
        elif field_name in ['CUSTOMER_NAME', 'VENDOR_NAME']:
            return self._normalize_name(str_value)
        elif field_name == 'MATERIAL':
            return self._normalize_material(str_value)
        elif field_name == 'NOTES':
            return self._normalize_notes(str_value)
        else:
            return str_value
    
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to consistent format."""
        if not date_str:
            return ''
        
        # Common date patterns
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{4})',  # MM-DD-YYYY
            r'(\d{4})/(\d{1,2})/(\d{1,2})',  # YYYY/MM/DD
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    if '/' in date_str and len(match.group(3)) == 4:  # MM/DD/YYYY format
                        month, day, year = match.groups()
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    elif '-' in date_str and len(match.group(3)) == 4:  # MM-DD-YYYY format
                        month, day, year = match.groups()
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    else:  # YYYY-MM-DD or YYYY/MM/DD format
                        year, month, day = match.groups()
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except ValueError:
                    continue
        
        # If no pattern matches, return original string
        return date_str
    
    def _normalize_measurement(self, measurement_str: str) -> str:
        """Normalize measurement strings (width, thickness, weight)."""
        if not measurement_str:
            return ''
        
        # Extract numeric value and units
        number_pattern = r'([\d,]+\.?\d*)\s*([a-zA-Z"\']+)?'
        match = re.search(number_pattern, measurement_str)
        
        if match:
            number = match.group(1).replace(',', '')
            unit = match.group(2) if match.group(2) else ''
            
            # Standardize common units
            unit_mapping = {
                '"': 'inches', "'": 'feet', 'lb': 'lbs', 'pound': 'lbs',
                'kg': 'kg', 'gram': 'g', 'mm': 'mm', 'cm': 'cm', 'm': 'm'
            }
            
            normalized_unit = unit_mapping.get(unit.lower(), unit)
            
            if normalized_unit:
                return f"{number} {normalized_unit}"
            else:
                return number
        
        return measurement_str
    
    def _normalize_coil_count(self, coil_count_str: str) -> str:
        """Normalize number of coils field."""
        if not coil_count_str:
            return '1'  # Default to 1 coil if not specified
        
        # Remove excessive whitespace
        cleaned = ' '.join(coil_count_str.split())
        
        # Extract just the number
        number_match = re.search(r'\d+', cleaned)
        if number_match:
            try:
                count = int(number_match.group())
                return str(count)
            except ValueError:
                pass
        
        # If no valid number found, default to 1
        return '1'
    
    def _normalize_identifier(self, identifier_str: str) -> str:
        """Normalize identifier strings (BOL numbers, tags, etc.)."""
        if not identifier_str:
            return ''
        
        # Remove excessive whitespace and normalize
        normalized = ' '.join(identifier_str.split())
        
        # Convert to uppercase for consistency with BOL standards
        return normalized.upper()
    
    def _normalize_name(self, name_str: str) -> str:
        """Normalize company/customer names."""
        if not name_str:
            return ''
        
        # Title case for proper names
        words = name_str.split()
        normalized_words = []
        
        for word in words:
            # Keep certain words in uppercase (common business abbreviations)
            if word.upper() in ['LLC', 'INC', 'CORP', 'CO', 'LTD', 'LP', 'PC']:
                normalized_words.append(word.upper())
            else:
                normalized_words.append(word.title())
        
        return ' '.join(normalized_words)
    
    def _normalize_material(self, material_str: str) -> str:
        """Normalize material descriptions."""
        if not material_str:
            return ''
        
        # Common material name standardization
        material_mapping = {
            'steel': 'Steel',
            'aluminum': 'Aluminum',
            'copper': 'Copper',
            'brass': 'Brass',
            'stainless': 'Stainless Steel',
            'galvanized': 'Galvanized Steel'
        }
        
        lower_material = material_str.lower()
        for key, value in material_mapping.items():
            if key in lower_material:
                return value
        
        # Return title case if no specific mapping found
        return material_str.title()
    
    def _normalize_notes(self, notes_str: str) -> str:
        """Normalize notes field."""
        if not notes_str:
            return ''
        
        # Clean up excessive whitespace and line breaks
        normalized = ' '.join(notes_str.split())
        
        # Limit length for spreadsheet compatibility
        if len(normalized) > 500:
            normalized = normalized[:497] + '...'
        
        return normalized
    
    def _validate_and_clean(self, data: Dict[str, str]) -> Dict[str, str]:
        """
        Validate and clean the flattened data.
        
        Args:
            data: Flattened data dictionary
            
        Returns:
            Validated and cleaned data dictionary
        """
        cleaned_data = {}
        
        for field in self.required_fields + ['PROCESSED_DATE']:
            value = data.get(field, '')
            
            # Remove any characters that might cause issues in Google Sheets
            cleaned_value = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', str(value))
            
            # Ensure the value doesn't exceed reasonable length limits
            if len(cleaned_value) > 1000:
                cleaned_value = cleaned_value[:997] + '...'
            
            cleaned_data[field] = cleaned_value
        
        return cleaned_data
    
    def _create_error_record(self, error_message: str) -> Dict[str, str]:
        """
        Create an error record when flattening fails.
        
        Args:
            error_message: Error description
            
        Returns:
            Error record dictionary
        """
        error_record = {}
        
        for field in self.required_fields:
            error_record[field] = ''
        
        error_record['NOTES'] = f"Processing Error: {error_message}"
        error_record['VALIDATION_STATUS'] = 'ERROR'
        error_record['PROCESSED_DATE'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return error_record
    
    def get_header_row(self) -> List[str]:
        """
        Get the header row for Google Sheets.
        
        Returns:
            List of column headers
        """
        return self.required_fields + ['PROCESSED_DATE']
