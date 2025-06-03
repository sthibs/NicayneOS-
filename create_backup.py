#!/usr/bin/env python3
"""
Create a comprehensive backup of the Nicayne OS system
"""

import shutil
import os
from datetime import datetime

def create_full_backup():
    """Create a complete backup of the system"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"full_system_backup_{timestamp}"
    
    print(f"Creating backup: {backup_name}.zip")
    
    # Create backup directory structure
    backup_dir = f"backups/{backup_name}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Files and directories to backup
    items_to_backup = [
        # Core application files
        "app.py",
        "app_old.py", 
        "app_current_with_heat_feature.py",
        
        # Configuration and data files
        "config.json",
        "users.json",
        "work_orders.json", 
        "finished_tags.json",
        "job_history.json",
        "invoice_tracking.json",
        "bol_tracking.json",
        "supplier_prompts.json",
        
        # PDF generators
        "generate_work_order_pdf.py",
        "generate_finished_tag_pdf.py", 
        "generate_bol_pdf.py",
        "generate_invoice_pdf.py",
        
        # Utility modules
        "drive_utils.py",
        "email_utils.py",
        
        # System files
        "pyproject.toml",
        "uv.lock",
        ".replit",
        
        # Test and audit files
        "comprehensive_route_test.py",
        "comprehensive_system_audit.py",
        "audit_invoice_integrity.py",
        
        # Directories
        "templates/",
        "static/",
        "utils/",
        "uploads/",
        "pdf_outputs/",
        "work_orders/",
        "finished_tags/",
        "test_docs/",
    ]
    
    # Copy each item
    for item in items_to_backup:
        src_path = item
        dest_path = os.path.join(backup_dir, item)
        
        if os.path.exists(src_path):
            if os.path.isfile(src_path):
                # Copy file
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(src_path, dest_path)
                print(f"✓ Backed up file: {item}")
            elif os.path.isdir(src_path):
                # Copy directory
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                print(f"✓ Backed up directory: {item}")
        else:
            print(f"⚠ Missing: {item}")
    
    # Create the zip file
    shutil.make_archive(f"backups/{backup_name}", 'zip', backup_dir)
    
    # Clean up temporary directory
    shutil.rmtree(backup_dir)
    
    print(f"\n✅ Backup completed: backups/{backup_name}.zip")
    
    # Show backup size
    zip_path = f"backups/{backup_name}.zip"
    if os.path.exists(zip_path):
        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"📦 Backup size: {size_mb:.2f} MB")
    
    return zip_path

if __name__ == "__main__":
    create_full_backup()