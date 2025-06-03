# utils/user_registry.py

registered_users = [
    {'email': 'shayne@nicayneos.com', 'name': 'Shayne', 'role': 'admin'},
    {'email': 'kp@caios.app', 'name': 'KP Operator', 'role': 'operator'},
    {'email': 'qa@nicayneos.com', 'name': 'QA Inspector', 'role': 'viewer'},
    {'email': 'admin@caios.app', 'name': 'System Administrator', 'role': 'admin'},
    # Add more users here as needed
]

def get_user_by_email(email):
    """Find a user by their email address (case-insensitive)"""
    return next((u for u in registered_users if u['email'].lower() == email.lower()), None)

def get_all_users():
    """Get all registered users"""
    return registered_users

def add_user(email, name, role):
    """Add a new user to the registry"""
    if get_user_by_email(email):
        return False  # User already exists
    
    new_user = {'email': email, 'name': name, 'role': role}
    registered_users.append(new_user)
    return True

def remove_user(email):
    """Remove a user from the registry"""
    global registered_users
    original_count = len(registered_users)
    registered_users = [u for u in registered_users if u['email'].lower() != email.lower()]
    return len(registered_users) < original_count