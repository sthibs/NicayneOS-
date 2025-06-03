"""
User Authentication and Session Management for Nicayne OS
Handles user creation, login, and session management with role-based access
"""

import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, redirect, url_for, flash
from .user_roles import get_user_role, can_user_access, get_default_route

# User database file
USERS_FILE = 'users.json'

class UserManager:
    def __init__(self):
        self.users_file = USERS_FILE
        self._ensure_users_file()
    
    def _ensure_users_file(self):
        """Ensure users.json exists with proper structure"""
        if not os.path.exists(self.users_file):
            initial_data = {
                "users": {},
                "sessions": {}
            }
            with open(self.users_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
    
    def _load_users(self):
        """Load users from JSON file"""
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"users": {}, "sessions": {}}
    
    def _save_users(self, data):
        """Save users to JSON file"""
        with open(self.users_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username, password, email, role):
        """Create a new user with specified role"""
        data = self._load_users()
        
        if username in data["users"]:
            return {"success": False, "error": "Username already exists"}
        
        # Validate role
        role_config = get_user_role(role)
        if not role_config:
            return {"success": False, "error": "Invalid role specified"}
        
        # Create user record
        user_record = {
            "username": username,
            "email": email,
            "role": role.lower(),
            "password_hash": self._hash_password(password),
            "created_at": datetime.now().isoformat(),
            "active": True,
            "last_login": None
        }
        
        data["users"][username] = user_record
        self._save_users(data)
        
        return {"success": True, "message": f"User {username} created successfully"}
    
    def authenticate_user(self, username, password):
        """Authenticate user credentials"""
        data = self._load_users()
        
        if username not in data["users"]:
            return {"success": False, "error": "Invalid username or password"}
        
        user = data["users"][username]
        
        if not user.get("active", False):
            return {"success": False, "error": "Account is disabled"}
        
        password_hash = self._hash_password(password)
        if user["password_hash"] != password_hash:
            return {"success": False, "error": "Invalid username or password"}
        
        # Update last login
        user["last_login"] = datetime.now().isoformat()
        data["users"][username] = user
        self._save_users(data)
        
        return {
            "success": True, 
            "user": {
                "username": username,
                "email": user["email"],
                "role": user["role"]
            }
        }
    
    def get_user(self, username):
        """Get user information"""
        data = self._load_users()
        user = data["users"].get(username)
        if user:
            return {
                "username": username,
                "email": user["email"],
                "role": user["role"],
                "active": user.get("active", False),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login")
            }
        return None
    
    def list_users(self):
        """List all users (admin function)"""
        data = self._load_users()
        users = []
        for username, user_data in data["users"].items():
            users.append({
                "username": username,
                "email": user_data["email"],
                "role": user_data["role"],
                "active": user_data.get("active", False),
                "last_login": user_data.get("last_login")
            })
        return users
    
    def update_user_status(self, username, active):
        """Enable or disable user account"""
        data = self._load_users()
        if username in data["users"]:
            data["users"][username]["active"] = active
            self._save_users(data)
            return {"success": True, "message": f"User {username} {'activated' if active else 'deactivated'}"}
        return {"success": False, "error": "User not found"}
    
    def delete_user(self, username):
        """Delete user account"""
        data = self._load_users()
        if username in data["users"]:
            del data["users"][username]
            self._save_users(data)
            return {"success": True, "message": f"User {username} deleted"}
        return {"success": False, "error": "User not found"}

# Initialize user manager
user_manager = UserManager()

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_module):
    """Decorator to require specific role access for routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            
            user_role = session['user'].get('role')
            if not can_user_access(user_role, required_module):
                flash("Access denied. Insufficient permissions.", "error")
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_user():
    """Get current logged-in user from session"""
    return session.get('user', None)

def is_admin():
    """Check if current user is admin"""
    user = get_current_user()
    return user and user.get('role') == 'admin'