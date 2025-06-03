"""
User Role Management System for Nicayne OS
Defines role-based access control and permissions
"""

# Define basic user roles and their access privileges
USER_ROLES = {
    "operator": {
        "description": "Operator - Limited access to Finished Tag form only.",
        "can_access": ["finished_tag"],
        "email_required": True,
        "dashboard_modules": ["finished_tag_form"],
        "default_route": "/finished-tag"
    },
    "manager": {
        "description": "Manager - Full access to all forms and email dashboard.",
        "can_access": ["work_order", "finished_tag", "bol", "invoice", "email_dashboard"],
        "email_required": True,
        "dashboard_modules": ["work_order_form", "finished_tag_form", "bol_generator", "invoice_generator", "email_dashboard"],
        "default_route": "/dashboard"
    },
    "admin": {
        "description": "Admin - Superuser access to all modules including user management.",
        "can_access": ["work_order", "finished_tag", "bol", "invoice", "email_dashboard", "user_admin"],
        "email_required": True,
        "dashboard_modules": ["work_order_form", "finished_tag_form", "bol_generator", "invoice_generator", "email_dashboard", "user_management"],
        "default_route": "/dashboard"
    }
}

def get_user_role(role_name):
    """Get role configuration by name"""
    return USER_ROLES.get(role_name.lower(), None)

def can_user_access(user_role, module):
    """Check if a user role can access a specific module"""
    role_config = get_user_role(user_role)
    if not role_config:
        return False
    return module in role_config.get("can_access", [])

def get_user_dashboard_modules(user_role):
    """Get dashboard modules available to a user role"""
    role_config = get_user_role(user_role)
    if not role_config:
        return []
    return role_config.get("dashboard_modules", [])

def get_default_route(user_role):
    """Get default route for a user role after login"""
    role_config = get_user_role(user_role)
    if not role_config:
        return "/"
    return role_config.get("default_route", "/")

def validate_role(role_name):
    """Validate if a role name exists"""
    return role_name.lower() in USER_ROLES

def get_all_roles():
    """Get all available roles"""
    return list(USER_ROLES.keys())

def get_role_description(role_name):
    """Get description for a role"""
    role_config = get_user_role(role_name)
    if not role_config:
        return "Unknown role"
    return role_config.get("description", "No description available")