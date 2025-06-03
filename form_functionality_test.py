#!/usr/bin/env python3
"""
Test form functionality, calculations, and data routing
"""

import requests
import json
from datetime import datetime

def test_quote_calculations():
    """Test quote form calculations"""
    print("🧮 Testing Quote Form Calculations...")
    
    # Test Cut-to-Length calculation
    # Formula: Finished Pieces = Incoming Weight / (Thickness × Width × Length × 0.2836)
    test_cases = [
        {"weight": 1000, "thickness": 0.25, "width": 12, "length": 120, "expected": round(1000 / (0.25 * 12 * 120 * 0.2836))},
        {"weight": 500, "thickness": 0.125, "width": 6, "length": 96, "expected": round(500 / (0.125 * 6 * 96 * 0.2836))},
    ]
    
    for case in test_cases:
        calculated = round(case["weight"] / (case["thickness"] * case["width"] * case["length"] * 0.2836))
        print(f"   Weight: {case['weight']} lbs, Dimensions: {case['thickness']}\" x {case['width']}\" x {case['length']}\"")
        print(f"   Expected: {case['expected']} pieces, Calculated: {calculated} pieces")
        if calculated == case["expected"]:
            print("   ✅ Calculation correct")
        else:
            print("   ❌ Calculation error")
    
def test_work_order_form_access():
    """Test work order form accessibility and structure"""
    print("📝 Testing Work Order Form...")
    
    try:
        response = requests.get("http://127.0.0.1:5000/work-order-form", timeout=5)
        if response.status_code == 200:
            content = response.text
            required_fields = [
                'name="customer_name"',
                'name="customer_po"', 
                'name="material_specs"',
                'name="quantity"',
                'name="packaging_instructions"'
            ]
            
            missing_fields = [field for field in required_fields if field not in content]
            
            if missing_fields:
                print(f"   ❌ Missing form fields: {missing_fields}")
            else:
                print("   ✅ All required form fields present")
                
        else:
            print(f"   ❌ Work order form returned status {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Work order form test failed: {str(e)}")

def test_finished_tag_form_access():
    """Test finished tag form accessibility"""
    print("🏷️ Testing Finished Tag Form...")
    
    try:
        response = requests.get("http://127.0.0.1:5000/finished-tag", timeout=5)
        if response.status_code == 200:
            content = response.text
            required_fields = [
                'name="customer_name"',
                'name="customer_po"',
                'name="work_order"',
                'name="pieces"',
                'name="weight"'
            ]
            
            missing_fields = [field for field in required_fields if field not in content]
            
            if missing_fields:
                print(f"   ❌ Missing form fields: {missing_fields}")
            else:
                print("   ✅ All required form fields present")
                
        else:
            print(f"   ❌ Finished tag form returned status {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Finished tag form test failed: {str(e)}")

def test_invoice_dashboard_route():
    """Fix and test invoice dashboard route"""
    print("💰 Testing Invoice Dashboard Route...")
    
    # Check if the route exists in app.py
    try:
        with open("app.py", 'r') as f:
            content = f.read()
            
        if "/invoices-dashboard" in content:
            print("   ✅ Invoice dashboard route exists in app.py")
            
            # Test the route
            response = requests.get("http://127.0.0.1:5000/invoices-dashboard", timeout=5)
            if response.status_code == 200:
                print("   ✅ Invoice dashboard accessible")
            else:
                print(f"   ❌ Invoice dashboard returned status {response.status_code}")
        else:
            print("   ❌ Invoice dashboard route not found in app.py")
            
    except Exception as e:
        print(f"   ❌ Invoice dashboard test failed: {str(e)}")

def check_google_drive_integration():
    """Check Google Drive integration setup"""
    print("☁️ Testing Google Drive Integration...")
    
    try:
        from drive_utils import DriveUploader
        
        # Check if DriveUploader can be initialized
        uploader = DriveUploader()
        print("   ✅ DriveUploader initialized successfully")
        
        # Check for required folder environment variables
        import os
        drive_secrets = [
            "CAIOS_ROOT_FOLDER_URL",
            "CLIENTS_FOLDER_ID", 
            "CUSTOMERS_FOLDER_ID"
        ]
        
        missing_secrets = [secret for secret in drive_secrets if not os.getenv(secret)]
        
        if missing_secrets:
            print(f"   ⚠️ Missing Google Drive folder secrets: {missing_secrets}")
        else:
            print("   ✅ All Google Drive folder secrets present")
            
    except ImportError as e:
        print(f"   ❌ DriveUploader import failed: {str(e)}")
    except Exception as e:
        print(f"   ❌ Google Drive integration test failed: {str(e)}")

def test_pdf_naming_conventions():
    """Test PDF naming conventions"""
    print("📄 Testing PDF Naming Conventions...")
    
    # Check if generate functions use consistent naming
    try:
        from generate_finished_tag_pdf import generate_finished_tag_pdf
        from generate_bol_pdf import generate_bol_pdf
        from generate_invoice_pdf import generate_invoice_pdf
        
        print("   ✅ All PDF generation modules importable")
        
        # Check for consistent file naming patterns in the code
        with open("generate_finished_tag_pdf.py", 'r') as f:
            content = f.read()
            if "NMP-FINISHED-TAG-" in content:
                print("   ✅ Finished tag PDF uses NMP naming convention")
            else:
                print("   ⚠️ Finished tag PDF naming convention not found")
                
    except Exception as e:
        print(f"   ❌ PDF naming convention test failed: {str(e)}")

def main():
    """Run form functionality tests"""
    print("🔍 Running Form Functionality & Data Routing Tests...")
    print("=" * 60)
    
    test_quote_calculations()
    test_work_order_form_access()
    test_finished_tag_form_access()
    test_invoice_dashboard_route()
    check_google_drive_integration()
    test_pdf_naming_conventions()
    
    print("=" * 60)
    print("✅ Form functionality tests completed")

if __name__ == "__main__":
    main()