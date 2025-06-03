"""
BOL Extractor Package

A modular system for extracting structured data from Bill of Lading (BOL) PDFs
using OCR and AI-powered data extraction with Google Sheets integration.

Components:
- extractor: Main extraction pipeline
- pdf_splitter: PDF page splitting utilities
- ocr_utils: OCR text extraction utilities
- llm_refiner: AI-powered data structuring
- json_flattener: Data normalization
- google_sheets_writer: Google Sheets integration
- config: Configuration management
"""

__version__ = "1.0.0"
__author__ = "BOL Extractor Team"

from .extractor import BOLExtractor
from .config import Config
from .pdf_splitter import PDFSplitter

__all__ = ['BOLExtractor', 'Config', 'PDFSplitter']
