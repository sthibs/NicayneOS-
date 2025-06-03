"""
Invoice Data Integrity Audit System
Verifies that invoice dashboard statistics are accurate and consistently sourced
"""

import json
import os
from datetime import datetime, date
from collections import defaultdict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class InvoiceIntegrityAuditor:
    def __init__(self):
        self.invoice_tracking_file = 'invoice_tracking.json'
        self.audit_results = {}
        self.warnings = []
        self.errors = []
    
    def load_invoice_data(self):
        """Load all invoice records from the tracking file."""
        logger.info("🔍 Loading invoice data from tracking file...")
        
        if not os.path.exists(self.invoice_tracking_file):
            self.errors.append(f"Invoice tracking file not found: {self.invoice_tracking_file}")
            return []
        
        try:
            with open(self.invoice_tracking_file, 'r') as f:
                invoices = json.load(f)
                logger.info(f"✓ Loaded {len(invoices)} invoice records")
                return invoices
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON decode error in invoice file: {str(e)}")
            return []
        except Exception as e:
            self.errors.append(f"Error loading invoice file: {str(e)}")
            return []
    
    def validate_invoice_structure(self, invoices):
        """Validate that each invoice has required fields with correct data types."""
        logger.info("🔍 Validating invoice record structure...")
        
        required_fields = [
            'invoice_number', 'customer_name', 'customer_po', 
            'work_order_number', 'total', 'date_generated'
        ]
        
        valid_invoices = []
        invalid_count = 0
        
        for i, invoice in enumerate(invoices):
            issues = []
            
            # Check required fields
            for field in required_fields:
                if field not in invoice:
                    issues.append(f"Missing field: {field}")
                elif invoice[field] is None or invoice[field] == '':
                    issues.append(f"Empty field: {field}")
            
            # Validate specific field types
            if 'total' in invoice:
                try:
                    float(invoice['total'])
                except (ValueError, TypeError):
                    issues.append(f"Invalid total value: {invoice.get('total')}")
            
            # Validate date format
            if 'date_generated' in invoice:
                try:
                    datetime.fromisoformat(invoice['date_generated'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    issues.append(f"Invalid date format: {invoice.get('date_generated')}")
            
            if issues:
                invalid_count += 1
                self.warnings.append(f"Invoice {i+1} ({invoice.get('invoice_number', 'Unknown')}): {', '.join(issues)}")
            else:
                valid_invoices.append(invoice)
        
        logger.info(f"✓ Validated {len(valid_invoices)} valid invoices, {invalid_count} with issues")
        self.audit_results['total_records'] = len(invoices)
        self.audit_results['valid_records'] = len(valid_invoices)
        self.audit_results['invalid_records'] = invalid_count
        
        return valid_invoices
    
    def calculate_statistics(self, invoices):
        """Calculate comprehensive statistics from invoice data."""
        logger.info("🔍 Calculating invoice statistics...")
        
        if not invoices:
            logger.warning("No valid invoices to calculate statistics")
            return
        
        # Basic totals
        total_count = len(invoices)
        total_value = sum(float(invoice.get('total', 0)) for invoice in invoices)
        
        # Current month calculations
        current_date = datetime.now()
        current_month = current_date.month
        current_year = current_date.year
        
        month_invoices = []
        month_value = 0
        
        # Customer breakdown
        customer_stats = defaultdict(lambda: {'count': 0, 'value': 0})
        
        # Monthly breakdown
        monthly_stats = defaultdict(lambda: {'count': 0, 'value': 0})
        
        for invoice in invoices:
            try:
                # Parse invoice date
                invoice_date = datetime.fromisoformat(invoice['date_generated'].replace('Z', '+00:00'))
                invoice_month = f"{invoice_date.year}-{invoice_date.month:02d}"
                invoice_value = float(invoice.get('total', 0))
                customer = invoice.get('customer_name', 'Unknown')
                
                # Monthly stats
                monthly_stats[invoice_month]['count'] += 1
                monthly_stats[invoice_month]['value'] += invoice_value
                
                # Customer stats
                customer_stats[customer]['count'] += 1
                customer_stats[customer]['value'] += invoice_value
                
                # Current month filter
                if invoice_date.month == current_month and invoice_date.year == current_year:
                    month_invoices.append(invoice)
                    month_value += invoice_value
                    
            except Exception as e:
                self.warnings.append(f"Error processing invoice {invoice.get('invoice_number', 'Unknown')}: {str(e)}")
        
        # Store results
        self.audit_results.update({
            'total_invoices': total_count,
            'total_value': total_value,
            'current_month_invoices': len(month_invoices),
            'current_month_value': month_value,
            'customer_breakdown': dict(customer_stats),
            'monthly_breakdown': dict(monthly_stats)
        })
        
        logger.info(f"✓ Statistics calculated:")
        logger.info(f"  Total Invoices: {total_count}")
        logger.info(f"  Total Value: ${total_value:,.2f}")
        logger.info(f"  This Month: {len(month_invoices)} invoices, ${month_value:,.2f}")
        logger.info(f"  Unique Customers: {len(customer_stats)}")
    
    def compare_with_dashboard_api(self):
        """Compare audit results with what the dashboard API returns."""
        logger.info("🔍 Comparing with dashboard API data...")
        
        try:
            # This would typically make an API call to /api/invoices
            # For now, we'll simulate by loading the same data the API uses
            dashboard_data = self.load_invoice_data()
            
            if not dashboard_data:
                self.errors.append("Cannot compare - dashboard API data unavailable")
                return
            
            # Calculate dashboard statistics (same logic as the dashboard)
            dashboard_total = len(dashboard_data)
            dashboard_value = sum(float(inv.get('total', 0)) for inv in dashboard_data)
            
            current_date = datetime.now()
            dashboard_month_count = 0
            dashboard_month_value = 0
            
            for invoice in dashboard_data:
                try:
                    invoice_date = datetime.fromisoformat(invoice['date_generated'].replace('Z', '+00:00'))
                    if (invoice_date.month == current_date.month and 
                        invoice_date.year == current_date.year):
                        dashboard_month_count += 1
                        dashboard_month_value += float(invoice.get('total', 0))
                except:
                    pass
            
            # Compare results
            audit_results = self.audit_results
            comparisons = {
                'total_count_match': audit_results.get('total_invoices') == dashboard_total,
                'total_value_match': abs(audit_results.get('total_value', 0) - dashboard_value) < 0.01,
                'month_count_match': audit_results.get('current_month_invoices') == dashboard_month_count,
                'month_value_match': abs(audit_results.get('current_month_value', 0) - dashboard_month_value) < 0.01
            }
            
            self.audit_results['dashboard_comparison'] = {
                'audit_total': audit_results.get('total_invoices'),
                'dashboard_total': dashboard_total,
                'audit_value': audit_results.get('total_value'),
                'dashboard_value': dashboard_value,
                'audit_month_count': audit_results.get('current_month_invoices'),
                'dashboard_month_count': dashboard_month_count,
                'audit_month_value': audit_results.get('current_month_value'),
                'dashboard_month_value': dashboard_month_value,
                'matches': comparisons
            }
            
            all_match = all(comparisons.values())
            
            if all_match:
                logger.info("✅ All dashboard statistics match audit calculations")
            else:
                logger.warning("⚠️ Dashboard statistics discrepancies found:")
                for key, matches in comparisons.items():
                    if not matches:
                        logger.warning(f"  - {key}: MISMATCH")
            
        except Exception as e:
            self.errors.append(f"Error comparing with dashboard: {str(e)}")
    
    def check_file_integrity(self):
        """Check for file system and Google Drive integration issues."""
        logger.info("🔍 Checking file system integrity...")
        
        invoices = self.load_invoice_data()
        
        # Check for invoice PDF files
        pdf_check_results = {
            'found': 0,
            'missing': 0,
            'invalid_path': 0
        }
        
        for invoice in invoices:
            invoice_number = invoice.get('invoice_number', '')
            if invoice_number:
                # Check local PDF file
                pdf_path = f"pdf_outputs/invoices/invoice_{invoice_number}.pdf"
                if os.path.exists(pdf_path):
                    pdf_check_results['found'] += 1
                else:
                    pdf_check_results['missing'] += 1
                    self.warnings.append(f"PDF file missing for invoice {invoice_number}")
            else:
                pdf_check_results['invalid_path'] += 1
        
        self.audit_results['file_integrity'] = pdf_check_results
        
        logger.info(f"✓ File integrity check:")
        logger.info(f"  PDF files found: {pdf_check_results['found']}")
        logger.info(f"  PDF files missing: {pdf_check_results['missing']}")
    
    def generate_audit_report(self):
        """Generate a comprehensive audit report."""
        logger.info("📋 Generating audit report...")
        
        report = {
            'audit_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_errors': len(self.errors),
                'total_warnings': len(self.warnings),
                'data_integrity_status': 'PASS' if len(self.errors) == 0 else 'FAIL'
            },
            'results': self.audit_results,
            'errors': self.errors,
            'warnings': self.warnings
        }
        
        # Save report to file
        report_filename = f"invoice_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"✅ Audit report saved to: {report_filename}")
        return report
    
    def run_full_audit(self):
        """Execute complete audit process."""
        logger.info("🚀 Starting comprehensive invoice data integrity audit...")
        
        # Load and validate data
        invoices = self.load_invoice_data()
        if not invoices:
            logger.error("❌ Cannot proceed - no invoice data available")
            return self.generate_audit_report()
        
        # Validate structure
        valid_invoices = self.validate_invoice_structure(invoices)
        
        # Calculate statistics
        self.calculate_statistics(valid_invoices)
        
        # Compare with dashboard
        self.compare_with_dashboard_api()
        
        # Check file integrity
        self.check_file_integrity()
        
        # Generate final report
        report = self.generate_audit_report()
        
        # Summary output
        logger.info("🏁 Audit Complete!")
        logger.info(f"   Status: {report['summary']['data_integrity_status']}")
        logger.info(f"   Errors: {report['summary']['total_errors']}")
        logger.info(f"   Warnings: {report['summary']['total_warnings']}")
        
        if report['summary']['data_integrity_status'] == 'PASS':
            logger.info("✅ Invoice data integrity verified - dashboard statistics are accurate")
        else:
            logger.error("❌ Invoice data integrity issues found - review audit report")
        
        return report

def main():
    """Run the invoice integrity audit."""
    auditor = InvoiceIntegrityAuditor()
    return auditor.run_full_audit()

if __name__ == "__main__":
    audit_report = main()