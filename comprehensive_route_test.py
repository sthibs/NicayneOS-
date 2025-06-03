#!/usr/bin/env python3
"""
Comprehensive Route Testing for Nicayne OS
Tests all routes and API endpoints to verify actual accessibility
"""

import requests
import json
from datetime import datetime

def test_all_routes():
    """Test all routes and endpoints systematically"""
    base_url = "http://127.0.0.1:5000"
    
    # Main navigation routes that should exist
    main_routes = [
        ("/", "Main/Dashboard"),
        ("/dashboard", "Dashboard"),
        ("/login", "Login Page"),
        ("/logout", "Logout"),
        ("/oauth2callback", "OAuth Callback"),
        ("/user-admin", "User Administration"),
        ("/user-directory", "User Directory"),
        ("/create-user", "Create User"),
        ("/control", "Control Panel"),
    ]
    
    # Core functionality routes
    core_routes = [
        ("/bol-extractor", "BOL Extractor"),
        ("/upload", "File Upload"),
        ("/work-order-form", "Work Order Form"),
        ("/finished-tag", "Finished Tag Form"),
    ]
    
    # History and tracking routes
    history_routes = [
        ("/work-order-history", "Work Order History"),
        ("/bol-history", "BOL History"),
        ("/history", "Job History"),
    ]
    
    # Invoice system routes
    invoice_routes = [
        ("/invoices", "Invoice Dashboard"),
        ("/generate-invoice", "Invoice Generator"),
        ("/audit-invoice-integrity", "Invoice Audit"),
    ]
    
    # BOL management routes
    bol_routes = [
        ("/upload-signed-bol", "Upload Signed BOL"),
    ]
    
    # Supplier and data routes
    data_routes = [
        ("/suppliers", "Suppliers Management"),
    ]
    
    # API endpoints that JavaScript depends on
    api_routes = [
        ("/work_orders.json", "Work Orders JSON Data"),
        ("/api/invoices", "Invoice API Data"),
        ("/api/bol-history", "BOL History API"),
        ("/api/lookup-heat-numbers", "Heat Number Lookup API"),
    ]
    
    all_route_groups = [
        ("Main Navigation", main_routes),
        ("Core Functionality", core_routes),
        ("History & Tracking", history_routes),
        ("Invoice System", invoice_routes),
        ("BOL Management", bol_routes),
        ("Data Management", data_routes),
        ("API Endpoints", api_routes),
    ]
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_routes_tested': 0,
        'successful_routes': 0,
        'failed_routes': 0,
        'detailed_results': {},
        'missing_routes': [],
        'working_routes': []
    }
    
    print("🔍 COMPREHENSIVE ROUTE TESTING")
    print("=" * 60)
    
    for group_name, routes in all_route_groups:
        print(f"\n📂 {group_name}:")
        print("-" * 40)
        
        group_results = []
        
        for route, description in routes:
            results['total_routes_tested'] += 1
            
            try:
                response = requests.get(f"{base_url}{route}", timeout=5, allow_redirects=False)
                
                # Accept 200, 302 (redirect to login), and 405 (method not allowed for POST routes)
                if response.status_code in [200, 302, 405]:
                    status = "✅ WORKING"
                    results['successful_routes'] += 1
                    results['working_routes'].append(route)
                    
                    if response.status_code == 302:
                        status += " (redirects to login - expected)"
                    elif response.status_code == 405:
                        status += " (POST route - expected)"
                        
                elif response.status_code == 404:
                    status = "❌ NOT FOUND"
                    results['failed_routes'] += 1
                    results['missing_routes'].append(route)
                else:
                    status = f"⚠️ STATUS {response.status_code}"
                    results['failed_routes'] += 1
                
                print(f"  {route:<25} {description:<25} {status}")
                group_results.append({
                    'route': route,
                    'description': description,
                    'status_code': response.status_code,
                    'result': status
                })
                
            except requests.exceptions.RequestException as e:
                status = f"❌ CONNECTION ERROR: {str(e)}"
                results['failed_routes'] += 1
                results['missing_routes'].append(route)
                print(f"  {route:<25} {description:<25} {status}")
                group_results.append({
                    'route': route,
                    'description': description,
                    'error': str(e),
                    'result': status
                })
        
        results['detailed_results'][group_name] = group_results
    
    # Summary
    print(f"\n📊 SUMMARY")
    print("=" * 60)
    print(f"Total Routes Tested: {results['total_routes_tested']}")
    print(f"Working Routes: {results['successful_routes']}")
    print(f"Failed Routes: {results['failed_routes']}")
    print(f"Success Rate: {(results['successful_routes']/results['total_routes_tested']*100):.1f}%")
    
    if results['missing_routes']:
        print(f"\n❌ MISSING ROUTES ({len(results['missing_routes'])}):")
        for route in results['missing_routes']:
            print(f"  - {route}")
    
    if results['working_routes']:
        print(f"\n✅ WORKING ROUTES ({len(results['working_routes'])}):")
        for route in results['working_routes']:
            print(f"  - {route}")
    
    # Save detailed results
    report_file = f"route_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    return results

if __name__ == "__main__":
    test_all_routes()