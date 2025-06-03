#!/usr/bin/env python3
"""
Comprehensive test suite for the Finished Tags system.
Tests all functionality including form submission, PDF generation, 
Google Sheets integration, and archive functionality.
"""

import requests
import json
import os
import sys
from datetime import datetime

BASE_URL = "http://localhost:5000"

def test_route_accessibility():
    """Test that all finished tags routes are accessible."""
    print("🔍 Testing Route Accessibility...")
    
    routes = [
        "/",
        "/finished-tag", 
        "/finished-tags",
        "/health"
    ]
    
    results = {}
    for route in routes:
        try:
            response = requests.get(f"{BASE_URL}{route}", timeout=10)
            results[route] = response.status_code
            print(f"  ✓ {route}: {response.status_code}")
        except Exception as e:
            results[route] = f"Error: {str(e)}"
            print(f"  ✗ {route}: {str(e)}")
    
    return results

def test_form_submission():
    """Test finished tag form submission with sample data."""
    print("\n📝 Testing Form Submission...")
    
    # Sample form data
    form_data = {
        "tag_id": f"TEST-TAG-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "date": datetime.now().strftime('%Y-%m-%d'),
        "work_order_number": "WO-TEST-001",
        "customer_name": "Test Customer Inc",
        "customer_po": "PO-TEST-12345",
        "material_grade": "A36",
        "material_description": "Hot Rolled Steel Plate",
        "pieces_or_coils": "5",
        "finished_weight": "1250.75",
        "heat_numbers": "H123456, H789012",
        "operator_initials": "JD",
        "incoming_tags": "INC-001, INC-002",
        "created_at": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(f"{BASE_URL}/finished-tag", data=form_data, timeout=30)
        print(f"  ✓ Form submission response: {response.status_code}")
        
        if response.status_code in [200, 302]:
            # Check if finished tag was saved locally
            if os.path.exists('finished_tags/finished_tags.json'):
                with open('finished_tags/finished_tags.json', 'r') as f:
                    tags = json.load(f)
                    if any(tag.get('tag_id') == form_data['tag_id'] for tag in tags):
                        print(f"  ✓ Tag {form_data['tag_id']} saved to local JSON")
                    else:
                        print(f"  ⚠ Tag {form_data['tag_id']} not found in local JSON")
            else:
                print("  ⚠ No finished_tags.json file found")
        
        return form_data['tag_id'], response.status_code
        
    except Exception as e:
        print(f"  ✗ Form submission failed: {str(e)}")
        return None, str(e)

def test_pdf_generation(tag_id):
    """Test PDF generation for a finished tag."""
    print(f"\n📄 Testing PDF Generation for {tag_id}...")
    
    try:
        response = requests.get(f"{BASE_URL}/finished-tags/{tag_id}/pdf", timeout=30)
        print(f"  ✓ PDF generation response: {response.status_code}")
        
        if response.status_code == 200:
            print(f"  ✓ PDF generated successfully")
            print(f"  ✓ Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"  ✓ Content-Length: {len(response.content)} bytes")
        else:
            print(f"  ⚠ PDF generation response: {response.status_code}")
            
        return response.status_code
        
    except Exception as e:
        print(f"  ✗ PDF generation failed: {str(e)}")
        return str(e)

def test_archive_functionality():
    """Test the finished tags archive page."""
    print(f"\n📚 Testing Archive Functionality...")
    
    try:
        response = requests.get(f"{BASE_URL}/finished-tags", timeout=10)
        print(f"  ✓ Archive page response: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            # Check for key elements
            checks = [
                ("Search filters", "search-tag" in content),
                ("Statistics summary", "Total Tags" in content),
                ("Action buttons", "Export CSV" in content),
                ("Table structure", "tags-table" in content)
            ]
            
            for check_name, result in checks:
                if result:
                    print(f"  ✓ {check_name}: Present")
                else:
                    print(f"  ⚠ {check_name}: Missing")
        
        return response.status_code
        
    except Exception as e:
        print(f"  ✗ Archive test failed: {str(e)}")
        return str(e)

def test_file_structure():
    """Test required file structure exists."""
    print(f"\n📁 Testing File Structure...")
    
    required_files = [
        "app.py",
        "templates/finished_tag.html",
        "templates/finished_tags_archive.html",
        "generate_finished_tag_pdf.py",
        "drive_utils.py"
    ]
    
    required_dirs = [
        "finished_tags",
        "pdf_outputs",
        "templates"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✓ {file_path}: Exists")
        else:
            print(f"  ✗ {file_path}: Missing")
    
    for dir_path in required_dirs:
        if os.path.exists(dir_path):
            print(f"  ✓ {dir_path}/: Exists")
        else:
            print(f"  ✗ {dir_path}/: Missing")

def test_google_sheets_connection():
    """Test Google Sheets connectivity."""
    print(f"\n🔗 Testing Google Sheets Connection...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            sheets_status = health_data.get('google_sheets', 'Unknown')
            print(f"  ✓ Sheets connection status: {sheets_status}")
        else:
            print(f"  ⚠ Health check failed: {response.status_code}")
            
    except Exception as e:
        print(f"  ⚠ Could not check sheets connection: {str(e)}")

def run_comprehensive_test():
    """Run all tests and provide summary."""
    print("🚀 STARTING COMPREHENSIVE FINISHED TAGS SYSTEM TEST")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Route accessibility
    results['routes'] = test_route_accessibility()
    
    # Test 2: File structure
    test_file_structure()
    
    # Test 3: Google Sheets connection
    test_google_sheets_connection()
    
    # Test 4: Form submission
    tag_id, submission_result = test_form_submission()
    results['form_submission'] = submission_result
    
    # Test 5: PDF generation (if tag was created)
    if tag_id:
        results['pdf_generation'] = test_pdf_generation(tag_id)
    
    # Test 6: Archive functionality
    results['archive'] = test_archive_functionality()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        if isinstance(result, dict):
            print(f"{test_name}: {len([r for r in result.values() if str(r).startswith('2')])} routes passed")
        elif str(result).startswith('2'):
            print(f"{test_name}: ✓ PASSED")
        else:
            print(f"{test_name}: ⚠ {result}")
    
    print("\n🏁 Test completed. Check logs above for detailed results.")

if __name__ == "__main__":
    run_comprehensive_test()