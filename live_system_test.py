#!/usr/bin/env python3
"""
Comprehensive Live System Test for Nicayne OS Platform
Tests all routes, functionality, and workflows without authentication
"""

import requests
import json
from datetime import datetime

def test_all_routes():
    """Test all routes systematically"""
    base_url = "http://127.0.0.1:5000"
    
    # Core navigation routes
    routes_to_test = [
        # Main navigation
        ("/", "Main/Dashboard"),
        ("/dashboard", "Dashboard"),
        ("/login", "Login Page"),
        
        # Core functionality
        ("/bol-extractor", "BOL Extractor"),
        ("/work-order-form", "Work Order Form"),
        ("/finished-tag", "Finished Tag Form"),
        ("/invoices", "Invoice Dashboard"),
        ("/generate-invoice", "Invoice Generator"),
        
        # History and tracking
        ("/work-order-history", "Work Order History"),
        ("/bol-history", "BOL History"),
        ("/history", "Job History"),
        ("/finished-tags-archive", "Finished Tags Archive"),
        
        # Management sections
        ("/quotes", "Quotes Dashboard"),
        ("/quotes/form", "Quote Form"),
        ("/purchase-orders", "Purchase Orders"),
        ("/manual-upload", "Manual Upload"),
        ("/upload-signed-bol", "Upload Signed BOL"),
        ("/suppliers", "Suppliers Management"),
        
        # System routes
        ("/health", "Health Check"),
        ("/health-status", "Health Status Page"),
        ("/control", "Control Panel"),
        ("/control-panel", "Admin Control Panel"),
        ("/user-admin", "User Administration"),
        ("/user-directory", "User Directory"),
        
        # New restored routes
        ("/summary", "Summary Page"),
        ("/quotes-pos", "Quotes & POs"),
        ("/bol-generator", "BOL Generator"),
        ("/finished-tags", "Finished Tags"),
    ]
    
    # API endpoints to test
    api_routes = [
        ("/work_orders.json", "Work Orders JSON"),
        ("/api/invoices", "Invoice API"),
        ("/api/bol-history", "BOL History API"),
        ("/api/get-quotes", "Quotes API"),
        ("/api/work-orders", "Work Orders API"),
        ("/api/bol-uploads", "BOL Uploads API"),
        ("/api/po-uploads", "PO Uploads API"),
        ("/api/signed-bol-uploads", "Signed BOL Uploads API"),
    ]
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_tested': 0,
        'successful': 0,
        'failed': 0,
        'results': []
    }
    
    print("🔍 COMPREHENSIVE LIVE SYSTEM TEST")
    print("=" * 60)
    
    # Test main routes
    print("\n📂 Main Navigation Routes:")
    print("-" * 40)
    
    for route, description in routes_to_test:
        results['total_tested'] += 1
        try:
            response = requests.get(f"{base_url}{route}", timeout=10, allow_redirects=False)
            
            # Accept success codes: 200 (OK), 302 (redirect to login), 405 (method not allowed)
            if response.status_code in [200, 302, 405]:
                status = "✅ WORKING"
                results['successful'] += 1
                if response.status_code == 302:
                    status += " (redirects - expected)"
                elif response.status_code == 405:
                    status += " (POST only - expected)"
            else:
                status = f"❌ ERROR {response.status_code}"
                results['failed'] += 1
                
            print(f"  {route:<25} {description:<25} {status}")
            results['results'].append({
                'route': route,
                'description': description,
                'status_code': response.status_code,
                'result': status
            })
            
        except Exception as e:
            status = f"❌ EXCEPTION: {str(e)}"
            results['failed'] += 1
            print(f"  {route:<25} {description:<25} {status}")
            results['results'].append({
                'route': route,
                'description': description,
                'error': str(e),
                'result': status
            })
    
    # Test API endpoints
    print(f"\n📡 API Endpoints:")
    print("-" * 40)
    
    for route, description in api_routes:
        results['total_tested'] += 1
        try:
            response = requests.get(f"{base_url}{route}", timeout=10, allow_redirects=False)
            
            if response.status_code in [200, 302]:
                status = "✅ RESPONDING"
                results['successful'] += 1
                if response.status_code == 302:
                    status += " (redirects - expected)"
            else:
                status = f"❌ ERROR {response.status_code}"
                results['failed'] += 1
                
            print(f"  {route:<25} {description:<25} {status}")
            results['results'].append({
                'route': route,
                'description': description,
                'status_code': response.status_code,
                'result': status
            })
            
        except Exception as e:
            status = f"❌ EXCEPTION: {str(e)}"
            results['failed'] += 1
            print(f"  {route:<25} {description:<25} {status}")
            results['results'].append({
                'route': route,
                'description': description,
                'error': str(e),
                'result': status
            })
    
    # Summary
    print(f"\n📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Total Routes Tested: {results['total_tested']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {(results['successful']/results['total_tested']*100):.1f}%")
    
    # Save detailed results
    report_file = f"live_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    return results

if __name__ == "__main__":
    test_all_routes()