"""
Main BOL extraction pipeline.
Coordinates PDF splitting, OCR, LLM processing, and Google Sheets output.
"""

import os
import json
import logging
import traceback
from typing import Dict, Any, List
from .config import Config
from .pdf_splitter import PDFSplitter
from .ocr_utils import OCRUtils
from .llm_refiner import LLMRefiner
from .json_flattener import JSONFlattener
from .google_sheets_writer import GoogleSheetsWriter

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
        
        # Only initialize Google Sheets writer if not in test mode
        if not config.is_test_mode():
            self.google_sheets_writer = GoogleSheetsWriter(config)
        else:
            self.google_sheets_writer = None
            logger.info("Running in test mode - Google Sheets writer disabled")
    
    def process_bol_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process a BOL PDF through the complete extraction pipeline.
        
        Args:
            pdf_path: Path to the PDF file to process
            
        Returns:
            Dict containing success status, extracted data, or error information
        """
        try:
            # Check if PDF is multi-page
            page_count = self.pdf_splitter.get_page_count(pdf_path)
            logger.info(f"PDF has {page_count} pages")
            
            if page_count > 1:
                return self._process_multi_page_pdf(pdf_path)
            else:
                return self._process_single_page_pdf(pdf_path)
                
        except Exception as e:
            error_msg = f"Error processing BOL PDF: {str(e)}"
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
            logger.info("Processing single-page PDF")
            
            # Extract text from PDF
            pdf_text = self.ocr_utils.extract_text_from_pdf(pdf_path)
            if not pdf_text:
                return {
                    'success': False,
                    'error': 'No text could be extracted from the PDF'
                }
            
            # Preprocess extracted text
            processed_text = self.ocr_utils.preprocess_text(pdf_text)
            logger.info(f"Extracted {len(processed_text)} characters from PDF")
            
            # Process with LLM
            structured_data = self.llm_refiner.refine_extracted_data(processed_text)
            if not structured_data:
                return {
                    'success': False,
                    'error': 'Failed to structure extracted data'
                }
            
            # Flatten data for Google Sheets
            flattened_data = self.json_flattener.flatten_bol_data(structured_data)
            
            # Write to Google Sheets (if not in test mode)
            if self.google_sheets_writer:
                sheet_result = self.google_sheets_writer.append_bol_data(flattened_data)
                
                if sheet_result['success']:
                    logger.info(f"BOL written to sheet row {sheet_result.get('row_number')}")
                    return {
                        'success': True,
                        'data': structured_data,
                        'flattened_data': flattened_data,
                        'sheet_result': sheet_result,
                        'sheet_row': sheet_result.get('row_number')
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Failed to write to Google Sheets: {sheet_result.get('error')}"
                    }
            else:
                # Test mode - return data without writing to sheets
                logger.info("Test mode - returning extracted data without writing to sheets")
                return {
                    'success': True,
                    'data': structured_data,
                    'flattened_data': flattened_data,
                    'test_mode': True
                }
                
        except Exception as e:
            error_msg = f"Error processing single-page PDF: {str(e)}"
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
            
            # Process each page individually and collect all coils for batch writing
            all_processed_coils = []
            all_flattened_coils = []
            total_coils_count = 0
            
            for i, page_path in enumerate(split_files):
                try:
                    logger.info(f"Processing page {i + 1}/{len(split_files)}")
                    page_text = self.ocr_utils.extract_text_from_pdf(page_path)
                    
                    if not page_text:
                        logger.warning(f"No text extracted from page {i + 1}, skipping")
                        continue
                        
                    processed_text = self.ocr_utils.preprocess_text(page_text)
                    logger.info(f"Extracted {len(processed_text)} characters from page {i + 1}")
                    
                    # Process this page with LLM
                    structured_data = self.llm_refiner.refine_extracted_data(processed_text)
                    
                    if not structured_data:
                        logger.warning(f"No structured data extracted from page {i + 1}")
                        continue
                    
                    # Handle multiple coils per page
                    if isinstance(structured_data, list):
                        coils_data = structured_data
                    elif isinstance(structured_data, dict) and 'coils' in structured_data:
                        coils_data = structured_data['coils']
                    else:
                        coils_data = [structured_data]
                    
                    page_coil_count = len(coils_data)
                    total_coils_count += page_coil_count
                    logger.info(f"Page {i + 1} extracted {page_coil_count} coils")
                    
                    # Collect all coils for batch processing
                    for coil_data in coils_data:
                        all_processed_coils.append(coil_data)
                        # Flatten each coil for Google Sheets
                        flattened_coil = self.json_flattener.flatten_bol_data(coil_data)
                        all_flattened_coils.append(flattened_coil)
                        
                except Exception as e:
                    logger.error(f"Error processing page {i + 1}: {str(e)}")
                    continue
            
            # Clean up temporary split files
            self.pdf_splitter.cleanup_temp_files()
            
            if total_coils_count == 0:
                return {
                    'success': False,
                    'error': 'No coils could be extracted from any pages'
                }
            
            # Write all coils to Google Sheets in a single batch operation
            if self.google_sheets_writer and all_flattened_coils:
                logger.info(f"Writing {len(all_flattened_coils)} coils to Google Sheets in batch")
                batch_result = self.google_sheets_writer.append_bol_data_batch(all_flattened_coils)
                
                if batch_result['success']:
                    logger.info(f"Successfully wrote {len(all_flattened_coils)} coils to Google Sheets")
                else:
                    logger.error(f"Batch write failed: {batch_result.get('error', 'Unknown error')}")
                
                return {
                    'success': True,
                    'data': {"coils": all_processed_coils},
                    'coils_processed': total_coils_count,
                    'batch_write_result': batch_result,
                    'pages_processed': len(split_files)
                }
            else:
                # Test mode or no sheets writer
                logger.info("Test mode - returning extracted data without writing to sheets")
                return {
                    'success': True,
                    'data': {"coils": all_processed_coils},
                    'coils_processed': total_coils_count,
                    'pages_processed': len(split_files),
                    'test_mode': True
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
            # Check if PDF is multi-page
            page_count = self.pdf_splitter.get_page_count(pdf_path)
            logger.info(f"PDF has {page_count} pages")
            
            if page_count > 1:
                return self._process_multi_page_pdf_with_supplier(pdf_path, supplier_name)
            else:
                return self._process_single_page_pdf_with_supplier(pdf_path, supplier_name)
                
        except Exception as e:
            error_msg = f"Error processing BOL PDF with supplier {supplier_name}: {str(e)}"
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
            logger.info(f"Processing single-page PDF with supplier: {supplier_name}")
            
            # Extract text from PDF
            pdf_text = self.ocr_utils.extract_text_from_pdf(pdf_path)
            if not pdf_text:
                return {
                    'success': False,
                    'error': 'No text could be extracted from the PDF'
                }
            
            # Preprocess extracted text
            processed_text = self.ocr_utils.preprocess_text(pdf_text)
            logger.info(f"Extracted {len(processed_text)} characters from PDF")
            
            # Process with LLM using supplier-specific prompt
            structured_data = self.llm_refiner.refine_extracted_data_with_supplier(processed_text, supplier_name)
            if not structured_data:
                return {
                    'success': False,
                    'error': 'Failed to structure extracted data'
                }
            
            # Flatten data for Google Sheets
            flattened_data = self.json_flattener.flatten_bol_data(structured_data)
            
            # Write to Google Sheets (if not in test mode)
            if self.google_sheets_writer:
                sheet_result = self.google_sheets_writer.append_bol_data(flattened_data)
                
                if sheet_result['success']:
                    logger.info(f"BOL written to sheet row {sheet_result.get('row_number')}")
                    return {
                        'success': True,
                        'data': structured_data,
                        'flattened_data': flattened_data,
                        'sheet_result': sheet_result,
                        'sheet_row': sheet_result.get('row_number'),
                        'supplier': supplier_name
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Failed to write to Google Sheets: {sheet_result.get('error')}"
                    }
            else:
                # Test mode - return data without writing to sheets
                logger.info("Test mode - returning extracted data without writing to sheets")
                return {
                    'success': True,
                    'data': structured_data,
                    'flattened_data': flattened_data,
                    'test_mode': True,
                    'supplier': supplier_name
                }
                
        except Exception as e:
            error_msg = f"Error processing single-page PDF with supplier {supplier_name}: {str(e)}"
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
            
            # Process each page individually and collect all coils for batch writing
            all_processed_coils = []
            all_flattened_coils = []
            total_coils_count = 0
            
            for i, page_path in enumerate(split_files):
                try:
                    logger.info(f"Processing page {i + 1}/{len(split_files)} for supplier: {supplier_name}")
                    page_text = self.ocr_utils.extract_text_from_pdf(page_path)
                    
                    if not page_text:
                        logger.warning(f"No text extracted from page {i + 1}, skipping")
                        continue
                        
                    processed_text = self.ocr_utils.preprocess_text(page_text)
                    logger.info(f"Extracted {len(processed_text)} characters from page {i + 1}")
                    
                    # Process this page with LLM using supplier-specific prompt
                    structured_data = self.llm_refiner.refine_extracted_data_with_supplier(processed_text, supplier_name)
                    
                    if not structured_data:
                        logger.warning(f"No structured data extracted from page {i + 1}")
                        continue
                    
                    # Handle multiple coils per page
                    if isinstance(structured_data, list):
                        coils_data = structured_data
                    elif isinstance(structured_data, dict) and 'coils' in structured_data:
                        coils_data = structured_data['coils']
                    else:
                        coils_data = [structured_data]
                    
                    page_coil_count = len(coils_data)
                    total_coils_count += page_coil_count
                    logger.info(f"Page {i + 1} extracted {page_coil_count} coils")
                    
                    # Collect all coils for batch processing
                    for coil_data in coils_data:
                        all_processed_coils.append(coil_data)
                        # Flatten each coil for Google Sheets
                        flattened_coil = self.json_flattener.flatten_bol_data(coil_data)
                        all_flattened_coils.append(flattened_coil)
                        
                except Exception as e:
                    logger.error(f"Error processing page {i + 1}: {str(e)}")
                    continue
            
            # Clean up temporary split files
            self.pdf_splitter.cleanup_temp_files()
            
            if total_coils_count == 0:
                return {
                    'success': False,
                    'error': 'No coils could be extracted from any pages'
                }
            
            # Write all coils to Google Sheets in a single batch operation
            if self.google_sheets_writer and all_flattened_coils:
                logger.info(f"Writing {len(all_flattened_coils)} coils to Google Sheets in batch")
                batch_result = self.google_sheets_writer.append_bol_data_batch(all_flattened_coils)
                
                if batch_result['success']:
                    logger.info(f"Successfully wrote {len(all_flattened_coils)} coils to Google Sheets")
                else:
                    logger.error(f"Batch write failed: {batch_result.get('error', 'Unknown error')}")
                
                return {
                    'success': True,
                    'data': {"coils": all_processed_coils},
                    'coils_processed': total_coils_count,
                    'batch_write_result': batch_result,
                    'pages_processed': len(split_files),
                    'supplier': supplier_name
                }
            else:
                # Test mode or no sheets writer
                logger.info("Test mode - returning extracted data without writing to sheets")
                return {
                    'success': True,
                    'data': {"coils": all_processed_coils},
                    'coils_processed': total_coils_count,
                    'pages_processed': len(split_files),
                    'test_mode': True,
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
        issues = []
        
        # Required fields
        required_fields = ['bol_number', 'customer_name', 'material']
        for field in required_fields:
            if not data.get(field):
                issues.append(f"Missing required field: {field}")
        
        # Validate numeric fields if present
        numeric_fields = ['width', 'thickness', 'weight', 'number_of_coils']
        for field in numeric_fields:
            value = data.get(field)
            if value and not str(value).replace('.', '').replace(',', '').isdigit():
                issues.append(f"Invalid numeric value for {field}: {value}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'data': data
        }