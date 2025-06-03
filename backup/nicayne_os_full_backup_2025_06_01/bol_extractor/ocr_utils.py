"""
OCR utilities for text extraction from PDFs.
Handles both text-based PDFs and image-based PDFs requiring OCR.
"""

import logging
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os
from typing import Optional

logger = logging.getLogger(__name__)

class OCRUtils:
    """Utilities for extracting text from PDFs using PyMuPDF and OCR fallback."""
    
    def __init__(self):
        """Initialize OCR utilities."""
        # Configure Tesseract path if needed (common on Windows)
        tesseract_cmd = os.environ.get('TESSERACT_CMD')
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        logger.info("OCR utilities initialized")
    
    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Extract text from PDF using PyMuPDF with OCR fallback for image-based content.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text as string, or None if extraction fails
        """
        try:
            # First attempt: Extract text directly from PDF
            direct_text = self._extract_direct_text(pdf_path)
            
            # If we got sufficient text, return it
            if direct_text and len(direct_text.strip()) > 100:
                logger.info("Successfully extracted text directly from PDF")
                return direct_text
            
            # Fallback: Use OCR on PDF pages
            logger.info("Direct text extraction insufficient, falling back to OCR")
            ocr_text = self._extract_text_with_ocr(pdf_path)
            
            if ocr_text and len(ocr_text.strip()) > 50:
                logger.info("Successfully extracted text using OCR")
                return ocr_text
            
            # If OCR also fails, return whatever we got
            logger.warning("OCR extraction also yielded limited text")
            return direct_text or ocr_text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return None
    
    def _extract_direct_text(self, pdf_path: str) -> Optional[str]:
        """
        Extract text directly from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text or None if extraction fails
        """
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                if text.strip():
                    text_content.append(text)
            
            doc.close()
            
            full_text = '\n'.join(text_content)
            logger.info(f"Direct extraction yielded {len(full_text)} characters from {len(doc)} pages")
            return full_text if full_text.strip() else None
            
        except Exception as e:
            logger.error(f"Error in direct text extraction: {str(e)}")
            return None
    
    def _extract_text_with_ocr(self, pdf_path: str) -> Optional[str]:
        """
        Extract text from PDF using OCR on rendered page images.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            OCR-extracted text or None if extraction fails
        """
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Render page as image
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR accuracy
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to PIL Image
                image = Image.open(io.BytesIO(img_data))
                
                # Perform OCR
                try:
                    page_text = pytesseract.image_to_string(
                        image, 
                        config='--psm 6 -l eng'  # Page segmentation mode 6, English language
                    )
                    if page_text.strip():
                        text_content.append(page_text)
                        logger.info(f"OCR extracted {len(page_text)} characters from page {page_num + 1}")
                except Exception as ocr_error:
                    logger.warning(f"OCR failed for page {page_num + 1}: {str(ocr_error)}")
                    continue
            
            doc.close()
            
            full_text = '\n'.join(text_content)
            logger.info(f"OCR extraction complete: {len(full_text)} total characters")
            return full_text if full_text.strip() else None
            
        except Exception as e:
            logger.error(f"Error in OCR text extraction: {str(e)}")
            return None
    
    def preprocess_text(self, text: str) -> str:
        """
        Clean and preprocess extracted text for better LLM processing.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned and preprocessed text
        """
        if not text:
            return ""
        
        # Basic text cleaning
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip empty lines and lines with only special characters
            if line and len(line) > 1 and not line.replace('-', '').replace('_', '').replace('*', '').strip() == '':
                cleaned_lines.append(line)
        
        # Join lines back together
        cleaned_text = '\n'.join(cleaned_lines)
        
        # Remove excessive whitespace
        import re
        cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)  # Normalize line breaks
        cleaned_text = re.sub(r' +', ' ', cleaned_text)  # Normalize spaces
        
        return cleaned_text.strip()
