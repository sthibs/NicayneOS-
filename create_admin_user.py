#!/usr/bin/env python3
"""
Create initial admin user for Nicayne OS
Run this script once to set up the default admin account
"""

from utils.user_auth import user_manager

def create_default_admin():
    """Create a default admin user for initial system access"""
    
    # Check if admin already exists
    existing_admin = user_manager.get_user('admin')
    if existing_admin:
        print("Admin user already exists")
        return
    
    # Create default admin user
    result = user_manager.create_user(
        username='admin',
        password='admin123',  # Default password - should be changed after first login
        email='admin@caios.app',
        role='admin'
    )
    
    if result['success']:
        print("✅ Default admin user created successfully!")
        print("Username: admin")
        print("Password: admin123")
        print("Email: admin@caios.app")
        print("\n⚠️  IMPORTANT: Change the password after first login!")
    else:
        print(f"❌ Failed to create admin user: {result['error']}")

if __name__ == "__main__":
    create_default_admin()