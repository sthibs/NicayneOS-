"""
Test suite for BOL extractor components.
Includes unit tests and integration tests for the complete pipeline.
"""

import os
import sys
import logging
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
import tempfile
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from extractor import BOLExtractor
from ocr_utils import OCRUtils
from llm_refiner import LLMRefiner
from json_flattener import JSONFlattener
from google_sheets_writer import GoogleSheetsWriter

logger = logging.getLogger(__name__)

class TestConfig(unittest.TestCase):
    """Test configuration management."""
    
    def test_config_initialization(self):
        """Test config initialization with environment variables."""
        with patch.dict(os.environ, {
            'GOOGLE_SERVICE_ACCOUNT_KEY_NMP': '{"test": "key"}',
            'SPREADSHEET_ID_NMP': 'test_sheet_id',
            'OPENAI_API_KEY': 'test_openai_key'
        }):
            config = Config()
            self.assertEqual(config.google_service_account_key, '{"test": "key"}')
            self.assertEqual(config.spreadsheet_id, 'test_sheet_id')
            self.assertEqual(config.openai_api_key, 'test_openai_key')
    
    def test_config_validation_missing_required(self):
        """Test config validation with missing required fields."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                Config()

class TestOCRUtils(unittest.TestCase):
    """Test OCR utilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.ocr_utils = OCRUtils()
    
    def test_text_preprocessing(self):
        """Test text preprocessing function."""
        raw_text = "  Line 1  \n\n\n  Line 2  \n   \n Line 3   "
        processed = self.ocr_utils.preprocess_text(raw_text)
        expected = "Line 1\n\nLine 2\n\nLine 3"
        self.assertEqual(processed, expected)
    
    @patch('fitz.open')
    def test_direct_text_extraction(self, mock_fitz_open):
        """Test direct text extraction from PDF."""
        # Mock PyMuPDF document
        mock_doc = Mock()
        mock_page = Mock()
        mock_page.get_text.return_value = "Test BOL content"
        mock_doc.__len__.return_value = 1
        mock_doc.load_page.return_value = mock_page
        mock_fitz_open.return_value = mock_doc
        
        result = self.ocr_utils._extract_direct_text("test.pdf")
        self.assertEqual(result, "Test BOL content")

class TestJSONFlattener(unittest.TestCase):
    """Test JSON flattening utilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.flattener = JSONFlattener()
    
    def test_date_normalization(self):
        """Test date normalization."""
        test_cases = [
            ("2024-01-15", "2024-01-15"),
            ("01/15/2024", "2024-01-15"),
            ("1/5/2024", "2024-01-05"),
            ("2024/1/15", "2024-01-15"),
        ]
        
        for input_date, expected in test_cases:
            result = self.flattener._normalize_date(input_date)
            self.assertEqual(result, expected, f"Failed for {input_date}")
    
    def test_measurement_normalization(self):
        """Test measurement normalization."""
        test_cases = [
            ("12.5 inches", "12.5 inches"),
            ('24"', '24 inches'),
            ("2,500 lbs", "2500 lbs"),
            ("1.5mm", "1.5 mm"),
        ]
        
        for input_measurement, expected in test_cases:
            result = self.flattener._normalize_measurement(input_measurement)
            self.assertEqual(result, expected, f"Failed for {input_measurement}")
    
    def test_identifier_normalization(self):
        """Test identifier normalization."""
        test_cases = [
            ("bol-12345", "BOL-12345"),
            ("  tag  567  ", "TAG 567"),
            ("heat#890", "HEAT#890"),
        ]
        
        for input_id, expected in test_cases:
            result = self.flattener._normalize_identifier(input_id)
            self.assertEqual(result, expected, f"Failed for {input_id}")
    
    def test_flatten_bol_data(self):
        """Test complete BOL data flattening."""
        test_data = {
            'BOL_NUMBER': 'bol-12345',
            'CUSTOMER_NAME': 'acme corp',
            'DATE_RECEIVED': '01/15/2024',
            'WEIGHT': '2,500 lbs',
            'MATERIAL': 'steel'
        }
        
        result = self.flattener.flatten_bol_data(test_data)
        
        self.assertEqual(result['BOL_NUMBER'], 'BOL-12345')
        self.assertEqual(result['CUSTOMER_NAME'], 'Acme Corp')
        self.assertEqual(result['DATE_RECEIVED'], '2024-01-15')
        self.assertEqual(result['WEIGHT'], '2500 lbs')
        self.assertEqual(result['MATERIAL'], 'Steel')
        self.assertIn('PROCESSED_DATE', result)

class TestLLMRefiner(unittest.TestCase):
    """Test LLM refiner functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock config
        self.mock_config = Mock()
        self.mock_config.openai_api_key = 'test_key'
        self.mock_config.deepseek_api_key = 'test_deepseek_key'
    
    @patch('bol_extractor.llm_refiner.OpenAI')
    def test_openai_extraction(self, mock_openai):
        """Test OpenAI data extraction."""
        # Mock OpenAI response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            'BOL_NUMBER': 'TEST-123',
            'CUSTOMER_NAME': 'Test Customer'
        })
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        refiner = LLMRefiner(self.mock_config)
        result = refiner._extract_with_openai("test text")
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result['BOL_NUMBER'], 'TEST-123')

class TestGoogleSheetsWriter(unittest.TestCase):
    """Test Google Sheets integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock config
        self.mock_config = Mock()
        self.mock_config.google_service_account_key = '{"test": "key"}'
        self.mock_config.spreadsheet_id = 'test_sheet_id'
    
    @patch('gspread.authorize')
    @patch('bol_extractor.google_sheets_writer.Credentials')
    def test_client_initialization(self, mock_credentials, mock_gspread):
        """Test Google Sheets client initialization."""
        mock_creds = Mock()
        mock_credentials.from_service_account_info.return_value = mock_creds
        mock_client = Mock()
        mock_gspread.return_value = mock_client
        
        writer = GoogleSheetsWriter(self.mock_config)
        
        self.assertIsNotNone(writer.client)
        mock_credentials.from_service_account_info.assert_called_once()
        mock_gspread.assert_called_once_with(mock_creds)

class TestBOLExtractor(unittest.TestCase):
    """Test main BOL extractor integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock config
        self.mock_config = Mock()
        self.mock_config.openai_api_key = 'test_key'
        self.mock_config.google_service_account_key = '{"test": "key"}'
        self.mock_config.spreadsheet_id = 'test_sheet_id'
    
    @patch('bol_extractor.extractor.GoogleSheetsWriter')
    @patch('bol_extractor.extractor.LLMRefiner')
    @patch('bol_extractor.extractor.OCRUtils')
    def test_successful_extraction_pipeline(self, mock_ocr, mock_llm, mock_sheets):
        """Test successful end-to-end extraction pipeline."""
        # Mock components
        mock_ocr_instance = Mock()
        mock_ocr_instance.extract_text_from_pdf.return_value = "Sample BOL text content"
        mock_ocr.return_value = mock_ocr_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.extract_bol_data.return_value = {
            'BOL_NUMBER': 'TEST-123',
            'CUSTOMER_NAME': 'Test Customer'
        }
        mock_llm.return_value = mock_llm_instance
        
        mock_sheets_instance = Mock()
        mock_sheets_instance.append_bol_data.return_value = {
            'success': True,
            'row_number': 5
        }
        mock_sheets.return_value = mock_sheets_instance
        
        # Test extraction
        extractor = BOLExtractor(self.mock_config)
        result = extractor.process_bol_pdf("test.pdf")
        
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertEqual(result['sheet_row'], 5)

def create_sample_pdf():
    """Create a sample PDF for testing (requires reportlab)."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        
        # Create PDF content
        c = canvas.Canvas(temp_file.name, pagesize=letter)
        c.drawString(100, 750, "BILL OF LADING")
        c.drawString(100, 700, "BOL Number: TEST-BOL-12345")
        c.drawString(100, 650, "Customer: Acme Corporation")
        c.drawString(100, 600, "Vendor: Steel Supply Co")
        c.drawString(100, 550, "Material: Carbon Steel")
        c.drawString(100, 500, "Weight: 2,500 lbs")
        c.drawString(100, 450, "Date Received: 01/15/2024")
        c.save()
        
        return temp_file.name
    except ImportError:
        logger.warning("reportlab not available - cannot create sample PDF")
        return None

def run_integration_test():
    """Run integration test with sample data."""
    logger.info("Starting BOL extractor integration test")
    
    try:
        # Load configuration
        config = Config()
        
        # Initialize extractor
        extractor = BOLExtractor(config)
        
        # Test with sample text (simulating OCR output)
        sample_text = """
        BILL OF LADING
        
        BOL Number: TEST-BOL-12345
        Customer: Acme Corporation  
        Vendor: Steel Supply Company
        
        Material Details:
        Material: Carbon Steel Coil
        Coil Tag: CSC-001
        Width: 48 inches
        Thickness: 0.125 inches
        Weight: 2,500 pounds
        Heat Number: H-987654
        
        Customer PO: PO-ABC-789
        Date Received: January 15, 2024
        
        Notes: Handle with care, inspect upon delivery
        """
        
        # Test LLM extraction
        logger.info("Testing LLM data extraction")
        structured_data = extractor.llm_refiner.extract_bol_data(sample_text)
        
        if structured_data:
            logger.info("LLM extraction successful")
            logger.info(f"Extracted data: {json.dumps(structured_data, indent=2)}")
            
            # Test JSON flattening
            logger.info("Testing JSON flattening")
            flattened_data = extractor.json_flattener.flatten_bol_data(structured_data)
            logger.info(f"Flattened data: {json.dumps(flattened_data, indent=2)}")
            
            # Test Google Sheets connection (if not in test mode)
            if not config.is_test_mode:
                logger.info("Testing Google Sheets connection")
                connection_result = extractor.google_sheets_writer.verify_connection()
                if connection_result:
                    logger.info("Google Sheets connection successful")
                    
                    # Optionally append test data
                    # sheet_result = extractor.google_sheets_writer.append_bol_data(flattened_data)
                    # logger.info(f"Sheet write result: {sheet_result}")
                else:
                    logger.error("Google Sheets connection failed")
            
            return {
                'success': True,
                'llm_extraction': structured_data,
                'flattened_data': flattened_data
            }
        else:
            logger.error("LLM extraction failed")
            return {'success': False, 'error': 'LLM extraction failed'}
            
    except Exception as e:
        logger.error(f"Integration test failed: {str(e)}")
        return {'success': False, 'error': str(e)}

def run_tests():
    """Run the complete test suite."""
    results = {
        'unit_tests': None,
        'integration_test': None,
        'success': False
    }
    
    try:
        # Configure logging for tests
        logging.basicConfig(level=logging.INFO)
        
        logger.info("Starting BOL extractor test suite")
        
        # Run unit tests
        logger.info("Running unit tests")
        test_loader = unittest.TestLoader()
        test_suite = test_loader.loadTestsFromModule(sys.modules[__name__])
        test_runner = unittest.TextTestRunner(verbosity=2)
        unit_test_result = test_runner.run(test_suite)
        
        results['unit_tests'] = {
            'tests_run': unit_test_result.testsRun,
            'failures': len(unit_test_result.failures),
            'errors': len(unit_test_result.errors),
            'success': unit_test_result.wasSuccessful()
        }
        
        # Run integration test
        logger.info("Running integration test")
        integration_result = run_integration_test()
        results['integration_test'] = integration_result
        
        # Overall success
        results['success'] = (
            results['unit_tests']['success'] and 
            results['integration_test']['success']
        )
        
        logger.info(f"Test suite completed. Overall success: {results['success']}")
        return results
        
    except Exception as e:
        logger.error(f"Test suite execution failed: {str(e)}")
        results['error'] = str(e)
        return results

if __name__ == '__main__':
    # Run tests when executed directly
    results = run_tests()
    print(json.dumps(results, indent=2))
