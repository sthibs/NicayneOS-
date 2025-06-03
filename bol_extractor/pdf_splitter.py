"""
PDF splitting utilities for BOL documents.
Splits multi-page PDFs into individual pages for processing.
"""

import os
import logging
import fitz  # PyMuPDF
from typing import List, Optional
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class PDFSplitter:
    """Utilities for splitting multi-page PDFs into individual pages."""
    
    def __init__(self):
        """Initialize PDF splitter."""
        self.temp_dir = None
        logger.info("PDF splitter initialized")
    
    def split_pdf(self, pdf_path: str) -> List[str]:
        """
        Split a multi-page PDF into individual page PDFs.
        
        Args:
            pdf_path: Path to the source PDF file
            
        Returns:
            List of paths to individual page PDF files
        """
        try:
            logger.info(f"Starting PDF split for: {pdf_path}")
            
            # Create temporary directory for split files
            self.temp_dir = tempfile.mkdtemp(prefix="bol_split_")
            logger.info(f"Created temporary directory: {self.temp_dir}")
            
            # Open the source PDF
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            
            if page_count == 0:
                logger.error("PDF contains no pages")
                return []
            
            logger.info(f"PDF contains {page_count} pages")
            
            split_files = []
            source_name = Path(pdf_path).stem
            
            # Split each page into a separate PDF
            for page_num in range(page_count):
                try:
                    # Create new document with single page
                    new_doc = fitz.open()
                    page = doc.load_page(page_num)
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    # Save individual page
                    page_filename = f"{source_name}_page_{page_num + 1}.pdf"
                    page_path = os.path.join(self.temp_dir, page_filename)
                    new_doc.save(page_path)
                    new_doc.close()
                    
                    split_files.append(page_path)
                    logger.info(f"Created page {page_num + 1}: {page_filename}")
                    
                except Exception as e:
                    logger.error(f"Error splitting page {page_num + 1}: {str(e)}")
                    continue
            
            doc.close()
            
            logger.info(f"Successfully split PDF into {len(split_files)} pages")
            return split_files
            
        except Exception as e:
            logger.error(f"Error splitting PDF: {str(e)}")
            return []
    
    def get_pdf_page_count(self, pdf_path: str) -> int:
        """
        Get the number of pages in a PDF without splitting.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Number of pages in the PDF
        """
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            return page_count
        except Exception as e:
            logger.error(f"Error getting page count: {str(e)}")
            return 0
    
    def should_split_pdf(self, pdf_path: str, max_pages: int = 1) -> bool:
        """
        Determine if a PDF should be split based on page count.
        
        Args:
            pdf_path: Path to the PDF file
            max_pages: Maximum pages before splitting (default: 1)
            
        Returns:
            True if PDF should be split, False otherwise
        """
        page_count = self.get_pdf_page_count(pdf_path)
        should_split = page_count > max_pages
        
        if should_split:
            logger.info(f"PDF has {page_count} pages, will split for individual processing")
        else:
            logger.info(f"PDF has {page_count} pages, no splitting needed")
            
        return should_split
    
    def extract_page_metadata(self, pdf_path: str) -> List[dict]:
        """
        Extract metadata for each page in the PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of metadata dictionaries for each page
        """
        try:
            doc = fitz.open(pdf_path)
            page_metadata = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Get page dimensions
                rect = page.rect
                
                # Count text blocks and images
                try:
                    text_dict = page.get_text("dict")
                    text_blocks = len(text_dict.get("blocks", []))
                    page_text = page.get_text()
                    has_text = len(page_text.strip()) > 0
                except:
                    text_blocks = 0
                    has_text = False
                
                image_list = page.get_images()
                
                metadata = {
                    'page_number': page_num + 1,
                    'width': rect.width,
                    'height': rect.height,
                    'text_blocks': text_blocks,
                    'images': len(image_list),
                    'has_text': has_text
                }
                
                page_metadata.append(metadata)
                logger.debug(f"Page {page_num + 1} metadata: {metadata}")
            
            doc.close()
            return page_metadata
            
        except Exception as e:
            logger.error(f"Error extracting page metadata: {str(e)}")
            return []
    
    def cleanup_temp_files(self):
        """
        Clean up temporary split files.
        """
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
                self.temp_dir = None
            except Exception as e:
                logger.warning(f"Error cleaning up temp directory: {str(e)}")
    
    def validate_pdf(self, pdf_path: str) -> dict:
        """
        Validate PDF file and return analysis.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary with validation results
        """
        validation = {
            'is_valid': False,
            'page_count': 0,
            'file_size': 0,
            'is_encrypted': False,
            'has_text': False,
            'error': None
        }
        
        try:
            if not os.path.exists(pdf_path):
                validation['error'] = 'File does not exist'
                return validation
            
            validation['file_size'] = os.path.getsize(pdf_path)
            
            doc = fitz.open(pdf_path)
            validation['page_count'] = len(doc)
            validation['is_encrypted'] = doc.needs_pass
            
            # Check if any page has text
            for page_num in range(min(3, len(doc))):  # Check first 3 pages
                page = doc.load_page(page_num)
                try:
                    page_text = page.get_text()
                    if len(page_text.strip()) > 10:
                        validation['has_text'] = True
                        break
                except:
                    continue
            
            doc.close()
            validation['is_valid'] = True
            
        except Exception as e:
            validation['error'] = str(e)
            logger.error(f"PDF validation error: {str(e)}")
        
        return validation
    
    def __del__(self):
        """Cleanup on object destruction."""
        self.cleanup_temp_files()