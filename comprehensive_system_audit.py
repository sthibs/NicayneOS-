#!/usr/bin/env python3
"""
Comprehensive System Audit & Portability Test for Nicayne Metal Processing OS
Tests all functionality, data routing, integrity, and portability requirements
"""

import os
import json
import traceback
from datetime import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials

class NicayneSystemAuditor:
    def __init__(self):
        self.results = {
            "functionality": {},
            "file_routing": {},
            "integrity": {},
            "portability": {},
            "summary": {
                "passed": 0,
                "warnings": 0,
                "errors": 0,
                "suggestions": []
            }
        }
        self.base_url = "http://127.0.0.1:5000"
        
    def log_result(self, category, test_name, status, message, suggestion=None):
        """Log audit result"""
        self.results[category][test_name] = {
            "status": status,
            "message": message,
            "suggestion": suggestion or ""
        }
        
        if status == "PASS":
            self.results["summary"]["passed"] += 1
        elif status == "WARNING":
            self.results["summary"]["warnings"] += 1
        elif status == "ERROR":
            self.results["summary"]["errors"] += 1
            
        if suggestion:
            self.results["summary"]["suggestions"].append(f"{test_name}: {suggestion}")
    
    def test_environment_variables(self):
        """Test all required environment variables"""
        print("🔒 Testing Environment Variables...")
        
        required_vars = [
            "GOOGLE_SERVICE_ACCOUNT_KEY_NMP",
            "SPREADSHEET_ID_NMP", 
            "OPENAI_API_KEY"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.log_result("portability", "environment_variables", "ERROR", 
                          f"Missing environment variables: {missing_vars}",
                          "All secrets must be configured for system to function")
        else:
            self.log_result("portability", "environment_variables", "PASS",
                          "All required environment variables are present")
    
    def test_google_sheets_connection(self):
        """Test Google Sheets API connectivity"""
        print("📊 Testing Google Sheets Connection...")
        
        try:
            service_account_key = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_NMP")
            spreadsheet_id = os.getenv("SPREADSHEET_ID_NMP")
            
            if not service_account_key or not spreadsheet_id:
                self.log_result("integrity", "google_sheets", "ERROR",
                              "Missing Google Sheets credentials")
                return
            
            # Parse service account key
            creds_data = json.loads(service_account_key)
            creds = Credentials.from_service_account_info(
                creds_data, 
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(spreadsheet_id)
            
            # Test accessing worksheets
            worksheets = spreadsheet.worksheets()
            worksheet_names = [ws.title for ws in worksheets]
            
            expected_sheets = ["UNPROCESSED_INVENTORY", "IN_PROCESS", "PROCESSED", "FINISHED_TAGS", "WORK_ORDERS"]
            missing_sheets = [sheet for sheet in expected_sheets if sheet not in worksheet_names]
            
            if missing_sheets:
                self.log_result("integrity", "google_sheets", "WARNING",
                              f"Missing worksheets: {missing_sheets}",
                              "Create missing worksheets for full functionality")
            else:
                self.log_result("integrity", "google_sheets", "PASS",
                              f"Google Sheets connected successfully. Worksheets: {worksheet_names}")
                
        except Exception as e:
            self.log_result("integrity", "google_sheets", "ERROR",
                          f"Google Sheets connection failed: {str(e)}")
    
    def test_openai_connection(self):
        """Test OpenAI API connectivity"""
        print("🤖 Testing OpenAI Connection...")
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                self.log_result("integrity", "openai", "ERROR", "Missing OpenAI API key")
                return
            
            # Test API with a simple request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            test_data = {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 10
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=test_data,
                timeout=10
            )
            
            if response.status_code == 200:
                self.log_result("integrity", "openai", "PASS", "OpenAI API connection successful")
            else:
                self.log_result("integrity", "openai", "ERROR", 
                              f"OpenAI API returned status {response.status_code}")
                
        except Exception as e:
            self.log_result("integrity", "openai", "ERROR", f"OpenAI connection failed: {str(e)}")
    
    def test_web_routes(self):
        """Test all major web routes"""
        print("🌐 Testing Web Routes...")
        
        routes_to_test = [
            "/",
            "/dashboard", 
            "/work-order-form",
            "/finished-tag",
            "/bol-generator",
            "/quote-generator",
            "/invoices-dashboard",
            "/manual-upload",
            "/quotes",
            "/purchase-orders"
        ]
        
        for route in routes_to_test:
            try:
                response = requests.get(f"{self.base_url}{route}", timeout=5)
                if response.status_code == 200:
                    self.log_result("functionality", f"route_{route.replace('/', '_')}", "PASS",
                                  f"Route {route} accessible")
                else:
                    self.log_result("functionality", f"route_{route.replace('/', '_')}", "ERROR",
                                  f"Route {route} returned status {response.status_code}")
            except Exception as e:
                self.log_result("functionality", f"route_{route.replace('/', '_')}", "ERROR",
                              f"Route {route} failed: {str(e)}")
    
    def test_file_structure(self):
        """Test required file and folder structure"""
        print("📁 Testing File Structure...")
        
        required_files = [
            "app.py",
            "templates/base.html",
            "templates/quote_generator.html", 
            "templates/work_order_form.html",
            "templates/finished_tag.html",
            "static/nmp-style.css",
            "generate_bol_pdf.py",
            "generate_invoice_pdf.py",
            "generate_finished_tag_pdf.py",
            "drive_utils.py"
        ]
        
        required_folders = [
            "templates",
            "static", 
            "uploads",
            "pdf_outputs",
            "work_orders",
            "finished_tags",
            "bol_extractor"
        ]
        
        missing_files = [f for f in required_files if not os.path.exists(f)]
        missing_folders = [f for f in required_folders if not os.path.exists(f)]
        
        if missing_files:
            self.log_result("integrity", "file_structure", "ERROR",
                          f"Missing files: {missing_files}")
        elif missing_folders:
            self.log_result("integrity", "file_structure", "ERROR", 
                          f"Missing folders: {missing_folders}")
        else:
            self.log_result("integrity", "file_structure", "PASS",
                          "All required files and folders present")
    
    def test_pdf_generation(self):
        """Test PDF generation capabilities"""
        print("📄 Testing PDF Generation...")
        
        try:
            # Test importing PDF generation modules
            from generate_bol_pdf import generate_bol_pdf
            from generate_invoice_pdf import generate_invoice_pdf  
            from generate_finished_tag_pdf import generate_finished_tag_pdf
            
            self.log_result("functionality", "pdf_imports", "PASS",
                          "All PDF generation modules import successfully")
                          
        except ImportError as e:
            self.log_result("functionality", "pdf_imports", "ERROR",
                          f"PDF import failed: {str(e)}")
    
    def test_json_tracking_files(self):
        """Test JSON tracking file integrity"""
        print("📋 Testing JSON Tracking Files...")
        
        tracking_files = [
            "work_orders.json",
            "finished_tags.json", 
            "job_history.json",
            "bol_tracking.json",
            "invoice_tracking.json"
        ]
        
        for file in tracking_files:
            try:
                if os.path.exists(file):
                    with open(file, 'r') as f:
                        data = json.load(f)
                    self.log_result("integrity", f"json_{file}", "PASS",
                                  f"{file} exists and is valid JSON with {len(data)} records")
                else:
                    self.log_result("integrity", f"json_{file}", "WARNING",
                                  f"{file} does not exist - will be created on first use")
            except json.JSONDecodeError:
                self.log_result("integrity", f"json_{file}", "ERROR",
                              f"{file} contains invalid JSON")
            except Exception as e:
                self.log_result("integrity", f"json_{file}", "ERROR",
                              f"Error reading {file}: {str(e)}")
    
    def test_portability_hardcoded_paths(self):
        """Check for hardcoded paths and non-portable references"""
        print("🔧 Testing Portability - Hardcoded Paths...")
        
        files_to_check = ["app.py", "drive_utils.py", "generate_bol_pdf.py", 
                         "generate_invoice_pdf.py", "generate_finished_tag_pdf.py"]
        
        hardcoded_issues = []
        
        for file in files_to_check:
            if os.path.exists(file):
                try:
                    with open(file, 'r') as f:
                        content = f.read()
                    
                    # Check for potential hardcoded issues
                    if "/Users/" in content or "C:\\" in content:
                        hardcoded_issues.append(f"{file}: Contains absolute paths")
                    if "1BrE" in content or "1Agh" in content:  # Sample folder IDs
                        hardcoded_issues.append(f"{file}: Contains hardcoded folder IDs")
                        
                except Exception as e:
                    hardcoded_issues.append(f"{file}: Error reading file - {str(e)}")
        
        if hardcoded_issues:
            self.log_result("portability", "hardcoded_paths", "WARNING",
                          f"Potential portability issues: {hardcoded_issues}",
                          "Replace hardcoded values with environment variables")
        else:
            self.log_result("portability", "hardcoded_paths", "PASS",
                          "No obvious hardcoded paths detected")
    
    def test_configuration_management(self):
        """Test configuration file management"""
        print("⚙️ Testing Configuration Management...")
        
        try:
            if os.path.exists("config.json"):
                with open("config.json", 'r') as f:
                    config = json.load(f)
                
                # Check for environment-driven configuration
                env_driven = all(
                    isinstance(v, str) and v.startswith("${") for v in config.values() 
                    if isinstance(v, str)
                )
                
                if env_driven:
                    self.log_result("portability", "configuration", "PASS",
                                  "Configuration uses environment variables")
                else:
                    self.log_result("portability", "configuration", "WARNING",
                                  "Some configuration values may be hardcoded",
                                  "Move all config to environment variables")
            else:
                self.log_result("portability", "configuration", "WARNING",
                              "No config.json found - using defaults")
                              
        except Exception as e:
            self.log_result("portability", "configuration", "ERROR",
                          f"Configuration test failed: {str(e)}")
    
    def calculate_portability_score(self):
        """Calculate overall portability confidence score"""
        portability_tests = self.results["portability"]
        total_tests = len(portability_tests)
        
        if total_tests == 0:
            return 0
        
        passed_tests = sum(1 for test in portability_tests.values() 
                         if test["status"] == "PASS")
        warning_tests = sum(1 for test in portability_tests.values() 
                          if test["status"] == "WARNING")
        
        # PASS = 1.0, WARNING = 0.5, ERROR = 0.0
        score = (passed_tests + (warning_tests * 0.5)) / total_tests * 100
        return round(score, 1)
    
    def run_full_audit(self):
        """Execute complete system audit"""
        print("🔍 Starting Comprehensive Nicayne System Audit...")
        print("=" * 60)
        
        # Environment and connectivity tests
        self.test_environment_variables()
        self.test_google_sheets_connection()
        self.test_openai_connection()
        
        # Functionality tests
        self.test_web_routes()
        self.test_pdf_generation()
        
        # Integrity tests
        self.test_file_structure()
        self.test_json_tracking_files()
        
        # Portability tests
        self.test_portability_hardcoded_paths()
        self.test_configuration_management()
        
        print("\n" + "=" * 60)
        print("🎯 AUDIT COMPLETE - Generating Report...")
        
    def generate_report(self):
        """Generate comprehensive audit report"""
        portability_score = self.calculate_portability_score()
        
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NICAYNE METAL PROCESSING OS - SYSTEM AUDIT REPORT         ║
║                              {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

📊 EXECUTIVE SUMMARY:
├─ Total Tests Run: {sum([len(cat) for cat in [self.results["functionality"], self.results["file_routing"], self.results["integrity"], self.results["portability"]]])}
├─ ✅ Passed: {self.results["summary"]["passed"]}
├─ ⚠️  Warnings: {self.results["summary"]["warnings"]}
├─ ❌ Errors: {self.results["summary"]["errors"]}
└─ 🔧 Portability Score: {portability_score}%

"""

        # Add detailed results for each category
        for category, tests in self.results.items():
            if category == "summary":
                continue
                
            report += f"\n{'='*80}\n"
            report += f"📋 {category.upper()} TESTS:\n"
            report += f"{'='*80}\n"
            
            for test_name, result in tests.items():
                status_icon = {"PASS": "✅", "WARNING": "⚠️", "ERROR": "❌"}[result["status"]]
                report += f"{status_icon} {test_name}: {result['message']}\n"
                if result["suggestion"]:
                    report += f"   💡 Suggestion: {result['suggestion']}\n"
            
        # Portability assessment
        report += f"\n{'='*80}\n"
        report += "🚀 PORTABILITY ASSESSMENT:\n"
        report += f"{'='*80}\n"
        
        if portability_score >= 90:
            report += "🟢 EXCELLENT: System is highly portable and ready for deployment\n"
        elif portability_score >= 70:
            report += "🟡 GOOD: System is mostly portable with minor improvements needed\n"
        elif portability_score >= 50:
            report += "🟠 MODERATE: System requires several portability improvements\n"
        else:
            report += "🔴 POOR: System needs significant work for portability\n"
        
        # Suggestions
        if self.results["summary"]["suggestions"]:
            report += f"\n{'='*80}\n"
            report += "💡 RECOMMENDATIONS:\n"
            report += f"{'='*80}\n"
            for suggestion in self.results["summary"]["suggestions"]:
                report += f"• {suggestion}\n"
        
        report += f"\n{'='*80}\n"
        report += "📝 AUDIT COMPLETED\n"
        report += f"{'='*80}\n"
        
        return report

def main():
    """Run the comprehensive audit"""
    auditor = NicayneSystemAuditor()
    
    try:
        auditor.run_full_audit()
        report = auditor.generate_report()
        
        # Save report to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"system_audit_report_{timestamp}.txt"
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(report)
        print(f"\n📄 Full report saved to: {report_file}")
        
        return auditor.results
        
    except Exception as e:
        print(f"❌ Audit failed with error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    main()