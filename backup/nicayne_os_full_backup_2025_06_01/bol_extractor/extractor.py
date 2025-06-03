"""
Main BOL extraction pipeline.
Coordinates PDF splitting, OCR, LLM processing, and Google Sheets output.
"""

import logging
import traceback
import json
import os
from datetime import datetime
from typing import Dict, Any, List
from .pdf_splitter import PDFSplitter
from .ocr_utils import OCRUtils
from .llm_refiner import LLMRefiner
from .json_flattener import JSONFlattener
from .google_sheets_writer import GoogleSheetsWriter
from .config import Config

# Safety configuration constants
MAX_PAGES = 100  # Maximum pages to process per document

logger = logging.getLogger(__name__)

class BOLExtractor:
    """Main BOL extraction pipeline that coordinates all components."""
    
    def __init__(self, config: Config):
        """Initialize the BOL extractor with configuration."""
        self.config = config
        self.pdf_splitter = PDFSplitter()
        self.ocr_utils = OCRUtils()
        self.llm_refiner = LLMRefiner(config)
        self.json_flattener = JSONFlattener()
        self.google_sheets_writer = GoogleSheetsWriter(config)
        
        logger.info("BOL Extractor initialized successfully")
    
    def _create_json_backup(self, coil_data: List[Dict[str, str]], document_name: str = "unknown") -> bool:
        """
        Create a JSON backup of extracted coil data.
        
        Args:
            coil_data: List of flattened coil data
            document_name: Name of the processed document for backup naming
            
        Returns:
            True if backup created successfully, False otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"coil_data_backup_{document_name}_{timestamp}.json"
            
            # Ensure backups directory exists
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            backup_path = os.path.join(backup_dir, backup_filename)
            
            backup_data = {
                "timestamp": timestamp,
                "document_name": document_name,
                "coil_count": len(coil_data),
                "coils": coil_data
            }
            
            with open(backup_path, "w") as f:
                json.dump(backup_data, f, indent=2)
            
            logger.info(f"📂 JSON backup created: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create JSON backup: {str(e)}")
            return False
    
    def _validate_coil_count(self, expected: int, actual: int) -> bool:
        """
        Validate that the expected number of coils matches what was written.
        
        Args:
            expected: Number of coils extracted
            actual: Number of coils written to sheets
            
        Returns:
            True if counts match, False otherwise
        """
        try:
            if expected != actual:
                logger.warning(f"⚠️ Coil count mismatch: extracted {expected}, wrote {actual}")
                return False
            else:
                logger.info(f"✅ Coil count validation passed: {expected} coils")
                return True
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            return False
    
    def process_bol_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a BOL PDF through the complete extraction pipeline.
        
        Args:
            pdf_path: Path to the PDF file to process
            
        Returns:
            Dict containing success status, extracted data, or error information
        """
        try:
            logger.info(f"Starting BOL extraction for: {pdf_path}")
            
            # Step 0: Validate and potentially split PDF
            logger.info("Step 0: Validating and analyzing PDF")
            validation = self.pdf_splitter.validate_pdf(pdf_path)
            
            if not validation['is_valid']:
                return {
                    'success': False,
                    'error': f"Invalid PDF file: {validation['error']}"
                }
            
            logger.info(f"PDF validation passed: {validation['page_count']} pages, {validation['file_size']} bytes")
            
            # Check if PDF should be split
            if self.pdf_splitter.should_split_pdf(pdf_path):
                return self._process_multi_page_pdf(pdf_path)
            else:
                return self._process_single_page_pdf(pdf_path)
            
        except Exception as e:
            error_msg = f"Error in BOL extraction pipeline: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg
            }
    
    def _process_single_page_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a single-page PDF through the extraction pipeline.
        
        Args:
            pdf_path: Path to the PDF file to process
            
        Returns:
            Dict containing success status, extracted data, or error information
        """
        try:
            # Step 1: Extract raw text from PDF
            logger.info("Step 1: Extracting text from PDF")
            raw_text = self.ocr_utils.extract_text_from_pdf(pdf_path)
            
            if not raw_text or len(raw_text.strip()) < 50:
                return {
                    'success': False,
                    'error': 'Failed to extract sufficient text from PDF. File may be corrupted or contain only images.'
                }
            
            logger.info(f"Extracted {len(raw_text)} characters of text")
            
            # Step 2: Use LLM to structure the data
            logger.info("Step 2: Processing text with LLM")
            structured_data = self.llm_refiner.extract_bol_data(raw_text)
            
            if not structured_data:
                return {
                    'success': False,
                    'error': 'Failed to extract structured data from text using LLM'
                }
            
            # Step 3: Flatten and normalize the JSON data
            logger.info("Step 3: Flattening and normalizing data")
            flattened_data = self.json_flattener.flatten_bol_data(structured_data)
            
            # Step 4: Write to Google Sheets
            logger.info("Step 4: Writing to Google Sheets")
            sheet_result = self.google_sheets_writer.append_bol_data(flattened_data)
            
            if not sheet_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to write to Google Sheets: {sheet_result['error']}"
                }
            
            logger.info("BOL extraction completed successfully")
            return {
                'success': True,
                'data': flattened_data,
                'sheet_row': sheet_result.get('row_number'),
                'raw_text_length': len(raw_text),
                'pages_processed': 1
            }
            
        except Exception as e:
            error_msg = f"Error processing single page PDF: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg
            }
    
    def _process_multi_page_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a multi-page PDF by splitting it and processing each page.
        
        Args:
            pdf_path: Path to the PDF file to process
            
        Returns:
            Dict containing success status, aggregated data, or error information
        """
        try:
            logger.info("Processing multi-page PDF")
            
            # Split PDF into individual pages
            split_files = self.pdf_splitter.split_pdf(pdf_path)
            
            if not split_files:
                return {
                    'success': False,
                    'error': 'Failed to split PDF into individual pages'
                }
            
            logger.info(f"Split PDF into {len(split_files)} pages")
            
            # Extract text from all pages and combine
            all_page_text = []
            total_chars = 0
            
            for i, page_path in enumerate(split_files):
                try:
                    logger.info(f"Extracting text from page {i + 1}/{len(split_files)}")
                    page_text = self.ocr_utils.extract_text_from_pdf(page_path)
                    
                    if page_text:
                        processed_text = self.ocr_utils.preprocess_text(page_text)
                        all_page_text.append(f"--- PAGE {i + 1} ---\n{processed_text}")
                        total_chars += len(processed_text)
                        logger.info(f"Extracted {len(processed_text)} characters from page {i + 1}")
                    else:
                        logger.warning(f"No text extracted from page {i + 1}")
                        
                except Exception as e:
                    logger.error(f"Error extracting text from page {i + 1}: {str(e)}")
                    continue
            
            # Clean up temporary split files
            self.pdf_splitter.cleanup_temp_files()
            
            if not all_page_text:
                return {
                    'success': False,
                    'error': 'Failed to extract text from any pages'
                }
            
            # Combine all page text
            combined_text = "\n\n".join(all_page_text)
            logger.info(f"Combined text from {len(all_page_text)} pages: {total_chars} total characters")
            
            # Process combined text with LLM using default supplier
            logger.info("Processing combined text with LLM using default supplier")
            structured_data = self.llm_refiner.extract_bol_data(combined_text, "default")
            
            if not structured_data:
                return {
                    'success': False,
                    'error': 'Failed to extract structured data from combined text'
                }
            
            # Handle multiple coils (array response) or single BOL
            if isinstance(structured_data, list):
                # Multiple coils - write each one to sheets
                all_rows = []
                logger.info(f"Processing {len(coils_data)} coils from BOL")
                
                for idx, coil_data in enumerate(coils_data):
                    logger.info(f"Processing coil {idx + 1}/{len(coils_data)}")
                    flattened_data = self.json_flattener.flatten_bol_data(coil_data)
                    
                    # Write to Google Sheets
                    sheet_result = self.google_sheets_writer.append_bol_data(flattened_data)
                    if sheet_result['success']:
                        all_rows.append(sheet_result.get('row_number'))
                        logger.info(f"Coil {idx + 1} written to sheet row {sheet_result.get('row_number')}")
                    else:
                        logger.error(f"Failed to write coil {idx + 1} to sheets: {sheet_result.get('error')}")
                
                logger.info(f"Multi-page processing completed: {len(coils_data)} coils processed")
                return {
                    'success': True,
                    'data': structured_data,
                    'coils_processed': len(coils_data),
                    'sheet_rows': all_rows,
                    'raw_text_length': total_chars,
                    'pages_processed': len(all_page_text)
                }
            else:
                # Single BOL record - process normally
                logger.info("Processing single BOL record")
                flattened_data = self.json_flattener.flatten_bol_data(structured_data)
                
                # Write to Google Sheets
                sheet_result = self.google_sheets_writer.append_bol_data(flattened_data)
                
                if sheet_result['success']:
                    logger.info(f"BOL written to sheet row {sheet_result.get('row_number')}")
                    return {
                        'success': True,
                        'data': structured_data,
                        'flattened_data': flattened_data,
                        'sheet_result': sheet_result,
                        'sheet_row': sheet_result.get('row_number'),
                        'raw_text_length': total_chars,
                        'pages_processed': len(all_page_text)
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Failed to write to Google Sheets: {sheet_result.get('error')}"
                    }
            
        except Exception as e:
            # Ensure cleanup even on error
            self.pdf_splitter.cleanup_temp_files()
            error_msg = f"Error processing multi-page PDF: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg
            }
    
    def process_bol_pdf_with_supplier(self, pdf_path: str, supplier_name: str = "default") -> Dict[str, Any]:
        """
        Process a BOL PDF with supplier-specific prompt customization.
        
        Args:
            pdf_path: Path to the PDF file to process
            supplier_name: Supplier identifier for custom prompt
            
        Returns:
            Dict containing success status, extracted data, or error information
        """
        try:
            logger.info(f"Starting BOL extraction for: {pdf_path} with supplier: {supplier_name}")
            
            # Step 0: Validate and potentially split PDF
            logger.info("Step 0: Validating and analyzing PDF")
            validation = self.pdf_splitter.validate_pdf(pdf_path)
            
            if not validation['is_valid']:
                return {
                    'success': False,
                    'error': f"Invalid PDF file: {validation['error']}"
                }
            
            logger.info(f"PDF validation passed: {validation['page_count']} pages, {validation['file_size']} bytes")
            
            # Check if PDF should be split
            if self.pdf_splitter.should_split_pdf(pdf_path):
                return self._process_multi_page_pdf_with_supplier(pdf_path, supplier_name)
            else:
                return self._process_single_page_pdf_with_supplier(pdf_path, supplier_name)
            
        except Exception as e:
            error_msg = f"Error in BOL extraction pipeline: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg
            }
    
    def _process_single_page_pdf_with_supplier(self, pdf_path: str, supplier_name: str) -> Dict[str, Any]:
        """
        Process a single-page PDF with supplier-specific prompts.
        
        Args:
            pdf_path: Path to the PDF file to process
            supplier_name: Supplier identifier for custom prompt
            
        Returns:
            Dict containing success status, extracted data, or error information
        """
        try:
            # Step 1: Extract raw text from PDF
            logger.info("Step 1: Extracting text from PDF")
            raw_text = self.ocr_utils.extract_text_from_pdf(pdf_path)
            
            if not raw_text or len(raw_text.strip()) < 50:
                return {
                    'success': False,
                    'error': 'Failed to extract sufficient text from PDF. File may be corrupted or contain only images.'
                }
            
            logger.info(f"Extracted {len(raw_text)} characters of text")
            
            # Step 2: Use LLM to structure the data with supplier-specific prompt
            logger.info(f"Step 2: Processing text with LLM for supplier: {supplier_name}")
            structured_data = self.llm_refiner.extract_bol_data(raw_text, supplier_name)
            
            if not structured_data:
                return {
                    'success': False,
                    'error': 'Failed to extract structured data from text using LLM'
                }
            
            # Step 3: Flatten and normalize the JSON data
            logger.info("Step 3: Flattening and normalizing data")
            flattened_data = self.json_flattener.flatten_bol_data(structured_data)
            
            # Step 4: Write to Google Sheets
            logger.info("Step 4: Writing to Google Sheets")
            sheet_result = self.google_sheets_writer.append_bol_data(flattened_data)
            
            if not sheet_result['success']:
                return {
                    'success': False,
                    'error': f"Failed to write to Google Sheets: {sheet_result['error']}"
                }
            
            logger.info("BOL extraction completed successfully")
            return {
                'success': True,
                'data': flattened_data,
                'sheet_row': sheet_result.get('row_number'),
                'raw_text_length': len(raw_text),
                'pages_processed': 1,
                'supplier': supplier_name
            }
            
        except Exception as e:
            error_msg = f"Error processing single page PDF with supplier {supplier_name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg
            }
    
    def _process_multi_page_pdf_with_supplier(self, pdf_path: str, supplier_name: str) -> Dict[str, Any]:
        """
        Process a multi-page PDF with supplier-specific prompts.
        
        Args:
            pdf_path: Path to the PDF file to process
            supplier_name: Supplier identifier for custom prompt
            
        Returns:
            Dict containing success status, aggregated data, or error information
        """
        try:
            logger.info(f"Processing multi-page PDF for supplier: {supplier_name}")
            
            # Split PDF into individual pages
            split_files = self.pdf_splitter.split_pdf(pdf_path)
            
            if not split_files:
                return {
                    'success': False,
                    'error': 'Failed to split PDF into individual pages'
                }
            
            logger.info(f"Split PDF into {len(split_files)} pages")
            
            # Max page protection
            if len(split_files) > MAX_PAGES:
                logger.warning(f"🚫 PDF has {len(split_files)} pages, which exceeds max allowed ({MAX_PAGES}). Truncating.")
                split_files = split_files[:MAX_PAGES]
                logger.info(f"Processing first {MAX_PAGES} pages only")
            
            # Process each page individually and collect all coils for batch writing
            all_processed_coils = []
            all_flattened_coils = []
            total_coils_count = 0
            page_coil_counts = []  # Track coils per page for debugging
            failed_pages = []  # Track pages that failed processing
            
            for i, page_path in enumerate(split_files):
                try:
                    logger.info(f"Processing page {i + 1}/{len(split_files)} individually")
                    page_text = self.ocr_utils.extract_text_from_pdf(page_path)
                    
                    if not page_text:
                        logger.warning(f"No text extracted from page {i + 1}, skipping")
                        continue
                        
                    processed_text = self.ocr_utils.preprocess_text(page_text)
                    logger.info(f"Extracted {len(processed_text)} characters from page {i + 1}")
                    
                    # Process this page individually with LLM
                    logger.info(f"Processing page {i + 1} with LLM for supplier: {supplier_name}")
                    page_structured_data = self.llm_refiner.extract_bol_data(processed_text, supplier_name)
                    
                    if not page_structured_data:
                        logger.warning(f"No structured data extracted from page {i + 1}")
                        continue
                        
                    # Handle the response format for this page
                    if isinstance(page_structured_data, dict) and 'coils' in page_structured_data:
                        page_coils = page_structured_data['coils']
                    elif isinstance(page_structured_data, list):
                        page_coils = page_structured_data
                    else:
                        logger.warning(f"Unexpected response format from page {i + 1}")
                        continue
                    
                    logger.info(f"Found {len(page_coils)} coils on page {i + 1}")
                    
                    # Debug: Show raw AI response for troubleshooting
                    logger.info(f"DEBUG - Raw AI response for page {i + 1}:")
                    import json
                    try:
                        logger.info(json.dumps(page_coils, indent=2))
                    except:
                        logger.info(str(page_coils))
                    
                    # Process each coil from this page
                    for coil_data in page_coils:
                        # Extract and validate essential fields
                        coil_tag = coil_data.get('COIL_TAG#') or coil_data.get('COIL_TAG')
                        width = coil_data.get('WIDTH')
                        thickness = coil_data.get('THICKNESS')
                        weight = coil_data.get('WEIGHT')
                        heat_number = coil_data.get('HEAT_NUMBER')
                        
                        # Convert to strings and strip whitespace and units
                        coil_tag_str = str(coil_tag).strip() if coil_tag else ''
                        width_str = str(width).strip() if width else ''
                        thickness_str = str(thickness).strip() if thickness else ''
                        weight_str = str(weight).strip() if weight else ''
                        
                        # Clean up unit suffixes from measurements
                        width_str = width_str.replace(' inches', '').replace('inches', '').replace('"', '').strip()
                        thickness_str = thickness_str.replace(' inches', '').replace('inches', '').replace('"', '').strip()
                        weight_str = weight_str.replace(' lbs', '').replace('lbs', '').replace(' pounds', '').replace('pounds', '').replace(',', '').strip()
                        
                        # Helper function to clean numeric values
                        def clean_numeric(value):
                            if not value:
                                return ""
                            try:
                                # Remove common invalid placeholders
                                if str(value).strip() in ['Unknown', 'MISSING', 'null', 'undefined', 'None']:
                                    return ""
                                return str(value).strip()
                            except:
                                return ""
                        
                        # Prepare cleaned row data - capture all available data
                        bol_num = coil_data.get('BOL_NUMBER', '')
                        cleaned_row = {
                            "Coil Tag": clean_numeric(coil_tag),
                            "Heat Number": clean_numeric(heat_number),
                            "Width": clean_numeric(width_str),
                            "Thickness": clean_numeric(thickness_str),
                            "Weight": clean_numeric(weight_str),
                            "BOL Number": clean_numeric(bol_num),
                            "Material": clean_numeric(coil_data.get('MATERIAL', '')),
                            "Customer Name": clean_numeric(coil_data.get('CUSTOMER_NAME', '')),
                            "Vendor Name": clean_numeric(coil_data.get('VENDOR_NAME', ''))
                        }
                        
                        # Only include the row if at least one key identifier is present
                        has_identifier = cleaned_row["Coil Tag"] or cleaned_row["Heat Number"] or cleaned_row["BOL Number"]
                        
                        if has_identifier:
                            # Log which fields are missing for QA purposes
                            missing_fields = [k for k, v in cleaned_row.items() if not v]
                            if missing_fields:
                                logger.warning(f"Partial data row: missing fields {missing_fields} — Row: {cleaned_row}")
                            
                            # Additional validation for suspicious width values
                            if cleaned_row["Width"]:
                                try:
                                    width_val = float(cleaned_row["Width"])
                                    if width_val < 3.0 or width_val > 100.0:
                                        logger.warning(f"Suspicious width detected ({width_val}) for coil {cleaned_row['Coil Tag']}")
                                except ValueError:
                                    logger.warning(f"Non-numeric width value for coil {cleaned_row['Coil Tag']}: {cleaned_row['Width']}")
                        else:
                            logger.warning(f"⛔️ SKIPPED ROW from page {i + 1}: No valid identifiers found")
                            logger.warning(f"Raw skipped data:\n{json.dumps(coil_data, indent=2)}")
                            continue
                            
                        total_coils_count += 1
                        bol_num = coil_data.get('BOL_NUMBER', 'Unknown')
                        
                        # Special logging for width verification
                        if '5' in width_str and '8' not in width_str:
                            logger.warning(f"⚠️ POTENTIAL WIDTH ERROR: Got {width_str}\" for coil {coil_tag_str} - verify this is correct (common confusion with 8\")")
                        
                        logger.info(f"✅ Processing valid coil {total_coils_count} from page {i + 1}: Tag={coil_tag_str}, Width={width_str}, BOL={bol_num}")
                        
                        # DEBUG MODE: Skip Google Sheets to avoid rate limits and show data
                        DEBUG_ONLY = False  # Set to False when live
                        
                        # Special debug for missing coil issue
                        bol_num = coil_data.get('BOL_NUMBER', 'Unknown')
                        if '7' in str(bol_num) or 'coils' in str(total_coils_count).lower():
                            logger.info(f"🔍 DEBUG - Coil {total_coils_count} details: BOL={bol_num}, Tag={coil_tag_str}")
                            logger.info(f"🔍 Full coil data: {json.dumps(coil_data, indent=2)}")
                        
                        # Collect all valid coils for batch processing
                        all_processed_coils.append(coil_data)
                        all_flattened_coils.append(self.json_flattener.flatten_bol_data(coil_data))
                            
                except Exception as e:
                    logger.error(f"⚠️ Error processing page {i + 1}: {str(e)}")
                    failed_pages.append(i + 1)
                    continue
            
            # Clean up temporary split files
            self.pdf_splitter.cleanup_temp_files()
            
            if total_coils_count == 0:
                return {
                    'success': False,
                    'error': 'No coils could be extracted from any pages'
                }
            
            # Create JSON backup before writing to sheets
            document_name = os.path.basename(pdf_path).replace('.pdf', '')
            backup_created = self._create_json_backup(all_flattened_coils, document_name)
            
            # Report on failed pages if any
            if failed_pages:
                logger.warning(f"⚠️ Failed to process {len(failed_pages)} pages: {failed_pages}")
            
            # Batch write all flattened coils to avoid API rate limits
            logger.info(f"Writing {len(all_flattened_coils)} coils to Google Sheets in batch")
            batch_result = self.google_sheets_writer.append_bol_data_batch(all_flattened_coils)
            
            # Validate coil count after batch write
            expected_count = len(all_flattened_coils)
            actual_count = batch_result.get('rows_added', 0) if batch_result.get('success') else 0
            count_validation = self._validate_coil_count(expected_count, actual_count)
            
            if batch_result['success']:
                logger.info(f"Successfully wrote {len(all_flattened_coils)} coils to Google Sheets")
            else:
                logger.error(f"Batch write failed: {batch_result.get('error', 'Unknown error')}")
            
            # Create structured_data for response
            structured_data = {"coils": all_processed_coils}
            
            if not structured_data:
                return {
                    'success': False,
                    'error': 'Failed to extract structured data from combined text'
                }
            
            # Debug: Log what we got from the AI
            logger.info(f"AI returned data type: {type(structured_data)}")
            if isinstance(structured_data, list):
                logger.info(f"Array with {len(structured_data)} items")
            else:
                logger.info(f"Single object with keys: {list(structured_data.keys()) if isinstance(structured_data, dict) else 'Not a dict'}")
            
            # Handle multiple coils - check for both array format and object with coils array
            if isinstance(structured_data, list):
                # Direct array format
                coils_data = structured_data
            elif isinstance(structured_data, dict) and 'coils' in structured_data:
                # Object format with coils array
                coils_data = structured_data['coils']
            else:
                # Single coil object
                coils_data = [structured_data]
            
            # Return successful result - batch writing already completed above
            logger.info(f"Multi-page processing completed: {total_coils_count} coils processed")
            return {
                'success': True,
                'data': structured_data,
                'coils_processed': total_coils_count,
                'batch_write_result': batch_result,
                'pages_processed': len(split_files),
                'failed_pages': failed_pages,
                'backup_created': backup_created,
                'count_validation': count_validation,
                'supplier': supplier_name
            }
            
        except Exception as e:
            # Ensure cleanup even on error
            self.pdf_splitter.cleanup_temp_files()
            error_msg = f"Error processing multi-page PDF for supplier {supplier_name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': error_msg
            }
    
    def validate_extraction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extracted BOL data for completeness and accuracy.
        
        Args:
            data: Extracted BOL data dictionary
            
        Returns:
            Validation results with status and issues
        """
        validation_results = {
            'is_valid': True,
            'issues': [],
            'completeness_score': 0.0
        }
        
        # Required fields for BOL validation
        required_fields = [
            'BOL_NUMBER', 'CUSTOMER_NAME', 'VENDOR_NAME', 
            'MATERIAL', 'WEIGHT', 'DATE_RECEIVED'
        ]
        
        # Check for required fields
        missing_fields = []
        for field in required_fields:
            if not data.get(field) or str(data[field]).strip() == '':
                missing_fields.append(field)
        
        if missing_fields:
            validation_results['is_valid'] = False
            validation_results['issues'].append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Calculate completeness score
        all_fields = [
            'BOL_NUMBER', 'CUSTOMER_NAME', 'VENDOR_NAME', 'COIL_TAG#',
            'MATERIAL', 'WIDTH', 'THICKNESS', 'WEIGHT', 'DATE_RECEIVED',
            'HEAT_NUMBER', 'CUSTOMER_PO', 'NOTES'
        ]
        
        filled_fields = sum(1 for field in all_fields if data.get(field) and str(data[field]).strip())
        validation_results['completeness_score'] = filled_fields / len(all_fields)
        
        # Set validation status in the data
        data['VALIDATION_STATUS'] = 'VALID' if validation_results['is_valid'] else 'NEEDS_REVIEW'
        
        return validation_results
