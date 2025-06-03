#!/usr/bin/env python3
"""
Comprehensive system diagnostic for BOL Extractor
"""

import os
import sys
import json
from pathlib import Path

def check_environment_variables():
    """Check all required environment variables"""
    print("🔍 1. CONFIGURATION VALIDATION")
    print("=" * 50)
    
    required_vars = [
        "OPEN_AI_API_KEY_CAIOS",
        "DEEP_SEEK_API", 
        "GOOGLE_SERVICE_ACCOUNT_KEY_CAIOS_NMP",
        "SPREADSHEET_ID_NMP"
    ]
    
    status = {}
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: Found (length: {len(value)})")
            status[var] = "OK"
        else:
            print(f"❌ {var}: Missing")
            status[var] = "MISSING"
    
    return status

def check_python_modules():
    """Check critical Python modules"""
    print("\n🐍 2. PYTHON MODULES CHECK")
    print("=" * 50)
    
    modules_to_check = [
        ("fitz", "PyMuPDF for PDF processing"),
        ("openai", "OpenAI API client"),
        ("requests", "HTTP requests for DeepSeek"),
        ("gspread", "Google Sheets API"),
        ("google.oauth2", "Google authentication"),
        ("PIL", "Image processing"),
        ("pytesseract", "OCR capabilities")
    ]
    
    status = {}
    for module, description in modules_to_check:
        try:
            __import__(module)
            print(f"✅ {module}: Available - {description}")
            status[module] = "OK"
        except ImportError:
            print(f"❌ {module}: Missing - {description}")
            status[module] = "MISSING"
    
    return status

def check_file_structure():
    """Check required files exist"""
    print("\n🗂 3. FILE STRUCTURE CHECK")
    print("=" * 50)
    
    required_files = [
        "bol_extractor/__init__.py",
        "bol_extractor/config.py",
        "bol_extractor/pdf_splitter.py", 
        "bol_extractor/ocr_utils.py",
        "bol_extractor/llm_refiner.py",
        "bol_extractor/extractor.py",
        "bol_extractor/google_sheets_writer.py",
        "bol_extractor/json_flattener.py",
        "app.py"
    ]
    
    status = {}
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}: Found")
            status[file_path] = "OK"
        else:
            print(f"❌ {file_path}: Missing")
            status[file_path] = "MISSING"
    
    return status

def test_pdf_processing():
    """Test PDF processing capabilities"""
    print("\n📄 4. PDF PROCESSING TEST")
    print("=" * 50)
    
    try:
        import fitz
        print(f"✅ PyMuPDF imported successfully")
        
        # Test basic fitz functionality
        if hasattr(fitz, 'open'):
            print(f"✅ fitz.open method available")
            # Test creating an empty document
            try:
                doc = fitz.open()
                print(f"✅ Can create empty PDF document")
                doc.close()
                return "OK"
            except Exception as e:
                print(f"❌ Cannot create PDF document: {str(e)}")
                return "FAILED"
        else:
            print(f"❌ fitz.open method not available")
            print(f"   This indicates corrupted PyMuPDF installation")
            return "FAILED"
            
    except Exception as e:
        print(f"❌ PDF processing test failed: {str(e)}")
        return "FAILED"

def test_basic_imports():
    """Test basic system imports"""
    print("\n⚙️ 5. BASIC SYSTEM IMPORTS")
    print("=" * 50)
    
    try:
        from bol_extractor.config import Config
        print("✅ Config import successful")
        
        config = Config()
        print("✅ Config initialization successful")
        
        return "OK"
    except Exception as e:
        print(f"❌ Basic imports failed: {str(e)}")
        return "FAILED"

def main():
    """Run comprehensive diagnostic"""
    print("📦 BOL EXTRACTOR SYSTEM DIAGNOSTIC")
    print("=" * 60)
    
    # Run all checks
    env_status = check_environment_variables()
    module_status = check_python_modules()
    file_status = check_file_structure()
    pdf_status = test_pdf_processing()
    import_status = test_basic_imports()
    
    # Summary
    print("\n✅ FINAL DIAGNOSTIC REPORT")
    print("=" * 60)
    
    issues = []
    
    # Check for critical issues
    if module_status.get("fitz") != "OK":
        issues.append("PyMuPDF (fitz) module not properly installed")
    
    if pdf_status != "OK":
        issues.append("PDF processing functionality broken")
        
    if import_status != "OK":
        issues.append("Basic system imports failing")
    
    missing_env = [k for k, v in env_status.items() if v == "MISSING"]
    if missing_env:
        issues.append(f"Missing environment variables: {', '.join(missing_env)}")
    
    if issues:
        print("❌ CRITICAL ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n🛠 RECOMMENDED ACTIONS:")
        if "fitz" in str(issues):
            print("  1. Reinstall PyMuPDF: uv add pymupdf")
        print("  2. Restart the application")
        print("  3. Re-run this diagnostic")
    else:
        print("✅ All systems operational!")

if __name__ == "__main__":
    main()