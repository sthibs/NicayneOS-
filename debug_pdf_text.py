#!/usr/bin/env python3
"""
Quick diagnostic script to check what text is extracted from the PDF
and which BOL numbers are present.
"""

import fitz  # PyMuPDF
import sys
import os

def extract_text_from_pdf(pdf_path):
    """Extract all text from PDF and show BOL number locations."""
    try:
        doc = fitz.open(pdf_path)
        all_text = ""
        
        print(f"PDF has {len(doc)} pages")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            print(f"\n=== PAGE {page_num + 1} ===")
            print(f"Page text length: {len(page_text)} characters")
            
            # Check for BOL numbers on this page
            bol_numbers = ["1641211", "1641212", "1641213"]
            found_bols = []
            for bol_num in bol_numbers:
                if bol_num in page_text:
                    found_bols.append(bol_num)
            
            print(f"BOL numbers found on page {page_num + 1}: {found_bols}")
            
            # Show first 200 chars of page for context
            print(f"First 200 chars: {page_text[:200]}...")
            
            all_text += page_text + "\n\n"
        
        doc.close()
        
        print(f"\n=== OVERALL SUMMARY ===")
        print(f"Total text length: {len(all_text)} characters")
        
        # Check which BOL numbers are in the complete text
        all_bol_numbers = ["1641211", "1641212", "1641213"]
        found_in_complete = []
        for bol_num in all_bol_numbers:
            if bol_num in all_text:
                found_in_complete.append(bol_num)
        
        print(f"BOL numbers in complete extracted text: {found_in_complete}")
        
        return all_text
        
    except Exception as e:
        print(f"Error extracting text: {e}")
        return None

if __name__ == "__main__":
    # Look for the uploaded PDF
    pdf_path = "attached_assets/MAK TEST BOL 3 PAGE.pdf"
    if os.path.exists(pdf_path):
        print(f"Analyzing: {pdf_path}")
        extract_text_from_pdf(pdf_path)
    else:
        print(f"PDF not found at: {pdf_path}")
        print("Available files in attached_assets:")
        if os.path.exists("attached_assets"):
            for file in os.listdir("attached_assets"):
                print(f"  - {file}")