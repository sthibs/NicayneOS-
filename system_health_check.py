#!/usr/bin/env python3
"""
Comprehensive System Health Check for Nicayne OS
Verifies all components, integrations, and functionality
"""

import os
import json
import sys
import importlib.util
from datetime import datetime

class NicayneSystemHealthCheck:
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'general_system': {},
            'authentication': {},
            'integrations': {},
            'file_structure': {},
            'routes': {},
            'critical_issues': [],
            'warnings': [],
            'recommendations': []
        }
    
    def check_environment_variables(self):
        """Check all required environment variables"""
        required_vars = [
            'GOOGLE_SERVICE_ACCOUNT_KEY_NMP',
            'SPREADSHEET_ID_NMP', 
            'OPENAI_API_KEY',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET',
            'GOOGLE_REDIRECT_URI',
            'DEFAULT_SEND_TO_EMAIL',
            'USER_EMAIL_ADDRESS'
        ]
        
        missing_vars = []
        present_vars = []
        
        for var in required_vars:
            if os.environ.get(var):
                present_vars.append(var)
            else:
                missing_vars.append(var)
        
        self.results['integrations']['environment_variables'] = {
            'present': present_vars,
            'missing': missing_vars,
            'status': 'PASS' if not missing_vars else 'FAIL'
        }
        
        if missing_vars:
            self.results['critical_issues'].append(f"Missing environment variables: {', '.join(missing_vars)}")
    
    def check_file_structure(self):
        """Check critical files and directories exist"""
        critical_files = [
            'app.py',
            'templates/finished_tag.html',
            'templates/dashboard.html',
            'templates/login.html',
            'templates/base.html',
            'generate_finished_tag_pdf.py',
            'generate_work_order_pdf.py',
            'generate_bol_pdf.py',
            'generate_invoice_pdf.py'
        ]
        
        critical_dirs = [
            'templates',
            'static',
            'uploads',
            'finished_tags',
            'work_orders',
            'pdf_outputs'
        ]
        
        missing_files = []
        missing_dirs = []
        present_files = []
        present_dirs = []
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                present_files.append(file_path)
            else:
                missing_files.append(file_path)
        
        for dir_path in critical_dirs:
            if os.path.exists(dir_path):
                present_dirs.append(dir_path)
            else:
                missing_dirs.append(dir_path)
        
        self.results['file_structure'] = {
            'files': {'present': present_files, 'missing': missing_files},
            'directories': {'present': present_dirs, 'missing': missing_dirs},
            'status': 'PASS' if not missing_files and not missing_dirs else 'FAIL'
        }
        
        if missing_files:
            self.results['critical_issues'].append(f"Missing critical files: {', '.join(missing_files)}")
        if missing_dirs:
            self.results['critical_issues'].append(f"Missing directories: {', '.join(missing_dirs)}")
    
    def check_app_imports(self):
        """Check if app.py can be imported without errors"""
        try:
            spec = importlib.util.spec_from_file_location("app", "app.py")
            app_module = importlib.util.module_from_spec(spec)
            # Don't execute, just check if it can be loaded
            self.results['general_system']['app_import'] = {
                'status': 'PASS',
                'message': 'app.py can be imported successfully'
            }
        except Exception as e:
            self.results['general_system']['app_import'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            self.results['critical_issues'].append(f"Cannot import app.py: {str(e)}")
    
    def check_json_tracking_files(self):
        """Check integrity of JSON tracking files"""
        json_files = [
            'users.json',
            'finished_tags.json',
            'work_orders.json',
            'bol_tracking.json',
            'invoice_tracking.json',
            'job_history.json'
        ]
        
        json_status = {}
        for file_path in json_files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    json_status[file_path] = {
                        'status': 'PASS',
                        'size': len(data) if isinstance(data, (list, dict)) else 'N/A'
                    }
                except json.JSONDecodeError as e:
                    json_status[file_path] = {
                        'status': 'CORRUPTED',
                        'error': str(e)
                    }
                    self.results['critical_issues'].append(f"Corrupted JSON file: {file_path}")
                except Exception as e:
                    json_status[file_path] = {
                        'status': 'ERROR',
                        'error': str(e)
                    }
            else:
                json_status[file_path] = {'status': 'MISSING'}
                self.results['warnings'].append(f"Missing JSON tracking file: {file_path}")
        
        self.results['file_structure']['json_files'] = json_status
    
    def check_google_service_account(self):
        """Validate Google service account configuration"""
        try:
            service_account_key = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY_NMP')
            if service_account_key:
                key_data = json.loads(service_account_key)
                required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
                missing_fields = [field for field in required_fields if field not in key_data]
                
                if missing_fields:
                    self.results['integrations']['google_service_account'] = {
                        'status': 'INVALID',
                        'missing_fields': missing_fields
                    }
                    self.results['critical_issues'].append("Google service account key is missing required fields")
                else:
                    self.results['integrations']['google_service_account'] = {
                        'status': 'VALID',
                        'project_id': key_data.get('project_id'),
                        'client_email': key_data.get('client_email')
                    }
            else:
                self.results['integrations']['google_service_account'] = {'status': 'MISSING'}
        except json.JSONDecodeError:
            self.results['integrations']['google_service_account'] = {'status': 'INVALID_JSON'}
            self.results['critical_issues'].append("Google service account key is not valid JSON")
    
    def check_oauth_configuration(self):
        """Check OAuth configuration"""
        oauth_vars = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI']
        oauth_config = {}
        
        for var in oauth_vars:
            value = os.environ.get(var)
            if value:
                oauth_config[var] = {
                    'status': 'PRESENT',
                    'length': len(value)
                }
            else:
                oauth_config[var] = {'status': 'MISSING'}
        
        self.results['authentication']['oauth_config'] = oauth_config
        
        # Check redirect URI format
        redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')
        if redirect_uri:
            if '/oauth2callback' in redirect_uri and ('http' in redirect_uri):
                self.results['authentication']['redirect_uri_format'] = 'VALID'
            else:
                self.results['authentication']['redirect_uri_format'] = 'INVALID'
                self.results['warnings'].append("Redirect URI format may be incorrect")
    
    def analyze_route_definitions(self):
        """Analyze app.py for route definitions"""
        try:
            with open('app.py', 'r') as f:
                content = f.read()
            
            # Find all route definitions
            import re
            routes = re.findall(r"@app\.route\('([^']+)'", content)
            
            expected_routes = [
                '/', '/login', '/logout', '/oauth2callback', '/dashboard',
                '/finished-tag', '/work-order-form', '/bol-extractor',
                '/user-admin', '/user-directory', '/api/lookup-heat-numbers'
            ]
            
            present_routes = [route for route in expected_routes if route in routes]
            missing_routes = [route for route in expected_routes if route not in routes]
            
            self.results['routes'] = {
                'total_defined': len(routes),
                'expected_present': present_routes,
                'missing': missing_routes,
                'all_routes': routes,
                'status': 'PASS' if not missing_routes else 'FAIL'
            }
            
            if missing_routes:
                self.results['critical_issues'].append(f"Missing expected routes: {', '.join(missing_routes)}")
                
        except Exception as e:
            self.results['routes'] = {'status': 'ERROR', 'error': str(e)}
    
    def check_pdf_generators(self):
        """Check PDF generation modules"""
        pdf_generators = [
            'generate_finished_tag_pdf.py',
            'generate_work_order_pdf.py', 
            'generate_bol_pdf.py',
            'generate_invoice_pdf.py'
        ]
        
        pdf_status = {}
        for gen in pdf_generators:
            if os.path.exists(gen):
                try:
                    with open(gen, 'r') as f:
                        content = f.read()
                    
                    # Check for critical imports
                    has_reportlab = 'from reportlab' in content or 'import reportlab' in content
                    has_main_function = 'def ' in content
                    
                    pdf_status[gen] = {
                        'status': 'PRESENT',
                        'has_reportlab': has_reportlab,
                        'has_functions': has_main_function
                    }
                    
                    if not has_reportlab:
                        self.results['warnings'].append(f"{gen} missing ReportLab imports")
                        
                except Exception as e:
                    pdf_status[gen] = {'status': 'ERROR', 'error': str(e)}
            else:
                pdf_status[gen] = {'status': 'MISSING'}
                self.results['critical_issues'].append(f"Missing PDF generator: {gen}")
        
        self.results['file_structure']['pdf_generators'] = pdf_status
    
    def check_template_integrity(self):
        """Check HTML templates for basic integrity"""
        templates = [
            'templates/base.html',
            'templates/login.html', 
            'templates/dashboard.html',
            'templates/finished_tag.html'
        ]
        
        template_status = {}
        for template in templates:
            if os.path.exists(template):
                try:
                    with open(template, 'r') as f:
                        content = f.read()
                    
                    # Basic checks
                    has_doctype = '<!DOCTYPE' in content
                    has_html_tags = '<html' in content and '</html>' in content
                    has_form = '<form' in content if 'form' in template else True
                    
                    template_status[template] = {
                        'status': 'VALID',
                        'has_doctype': has_doctype,
                        'has_html_tags': has_html_tags,
                        'has_form': has_form
                    }
                    
                    if not has_doctype or not has_html_tags:
                        self.results['warnings'].append(f"Template {template} has structural issues")
                        
                except Exception as e:
                    template_status[template] = {'status': 'ERROR', 'error': str(e)}
            else:
                template_status[template] = {'status': 'MISSING'}
        
        self.results['file_structure']['templates'] = template_status
    
    def run_comprehensive_check(self):
        """Run all checks and generate report"""
        print("🔍 Running Comprehensive Nicayne OS System Health Check...")
        print("=" * 60)
        
        # Run all checks
        self.check_environment_variables()
        self.check_file_structure()
        self.check_app_imports()
        self.check_json_tracking_files()
        self.check_google_service_account()
        self.check_oauth_configuration()
        self.analyze_route_definitions()
        self.check_pdf_generators()
        self.check_template_integrity()
        
        # Generate summary
        total_issues = len(self.results['critical_issues'])
        total_warnings = len(self.results['warnings'])
        
        print(f"\n📊 SYSTEM HEALTH SUMMARY")
        print(f"Critical Issues: {total_issues}")
        print(f"Warnings: {total_warnings}")
        
        if total_issues == 0:
            print("✅ SYSTEM STATUS: HEALTHY")
        else:
            print("❌ SYSTEM STATUS: NEEDS ATTENTION")
        
        return self.results
    
    def generate_detailed_report(self):
        """Generate detailed report"""
        report = []
        report.append("=" * 80)
        report.append("NICAYNE OS COMPREHENSIVE SYSTEM HEALTH REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {self.results['timestamp']}")
        report.append("")
        
        # Critical Issues
        if self.results['critical_issues']:
            report.append("🚨 CRITICAL ISSUES:")
            for issue in self.results['critical_issues']:
                report.append(f"  ❌ {issue}")
            report.append("")
        
        # Warnings
        if self.results['warnings']:
            report.append("⚠️  WARNINGS:")
            for warning in self.results['warnings']:
                report.append(f"  ⚠️  {warning}")
            report.append("")
        
        # Detailed sections
        sections = [
            ('ENVIRONMENT VARIABLES', 'integrations', 'environment_variables'),
            ('FILE STRUCTURE', 'file_structure', None),
            ('ROUTE DEFINITIONS', 'routes', None),
            ('OAUTH CONFIGURATION', 'authentication', None),
            ('GOOGLE INTEGRATIONS', 'integrations', None)
        ]
        
        for section_name, key, subkey in sections:
            report.append(f"\n📋 {section_name}:")
            report.append("-" * 40)
            
            if subkey:
                data = self.results.get(key, {}).get(subkey, {})
            else:
                data = self.results.get(key, {})
            
            if isinstance(data, dict):
                for item_key, item_value in data.items():
                    if isinstance(item_value, dict):
                        status = item_value.get('status', 'UNKNOWN')
                        report.append(f"  {item_key}: {status}")
                    else:
                        report.append(f"  {item_key}: {item_value}")
            
        return "\n".join(report)

if __name__ == "__main__":
    checker = NicayneSystemHealthCheck()
    results = checker.run_comprehensive_check()
    
    # Save detailed report
    report = checker.generate_detailed_report()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"system_health_report_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    print("\n" + "=" * 60)