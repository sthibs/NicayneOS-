"""
Flask web application for BOL PDF upload and processing.
Provides a simple interface for uploading PDFs and processing them through the BOL extractor.
"""

import os
import logging
import time
import queue
import json
import base64
import re
from datetime import datetime, date, timedelta
from flask import Flask, request, render_template, jsonify, flash, redirect, url_for, send_file, Response, stream_with_context, session
from werkzeug.utils import secure_filename

# Import user authentication system
from utils.user_registry import get_user_by_email
from bol_extractor.extractor import BOLExtractor

# OAuth imports for Google integration
from requests_oauthlib import OAuth2Session
from bol_extractor.config import Config
from utils.prompt_loader import PromptLoader
from drive_utils import DriveUploader
from email_utils import send_email_with_attachment

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
live_log_stream = queue.Queue()

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Authentication helper functions
def login_required(f):
    """Decorator to require login for routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    """Decorator to require specific role for routes"""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            
            user_role = session['user'].get('role', '')
            
            # Admin can access everything
            if user_role == 'admin':
                return f(*args, **kwargs)
            
            # Check if user has the required role
            if user_role != required_role:
                flash('Access denied. Insufficient permissions.', 'error')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_user():
    """Get the current logged-in user"""
    return session.get('user', None)

# Authentication Routes
@app.route('/login')
def login():
    """Start Google OAuth login flow"""
    # Build dynamic redirect URI based on current environment
    base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
    redirect_uri = f"{base_url}/oauth2callback"
    
    google = OAuth2Session(
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        redirect_uri=redirect_uri,
        scope=['https://www.googleapis.com/auth/userinfo.email']
    )
    authorization_url, state = google.authorization_url(
        'https://accounts.google.com/o/oauth2/auth',
        access_type='offline',
        prompt='consent'
    )
    session['oauth_state'] = state
    session['redirect_uri'] = redirect_uri  # Store for callback use
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    """Handle OAuth callback and log user in"""
    try:
        # Use the stored redirect URI from the login session
        redirect_uri = session.get('redirect_uri')
        if not redirect_uri:
            # Fallback to dynamic generation if not stored
            base_url = os.getenv('BASE_URL', request.host_url.rstrip('/'))
            redirect_uri = f"{base_url}/oauth2callback"
        
        google = OAuth2Session(
            client_id=os.environ['GOOGLE_CLIENT_ID'],
            redirect_uri=redirect_uri,
            state=session.get('oauth_state')
        )
        token = google.fetch_token(
            'https://oauth2.googleapis.com/token',
            client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
            authorization_response=request.url
        )
        session['oauth_token'] = token

        user_info = google.get('https://www.googleapis.com/oauth2/v1/userinfo').json()
        email = user_info.get('email')

        # Match email to registered system users
        user_record = get_user_by_email(email)

        if not user_record:
            flash('Unauthorized: Your email is not registered for this system', 'error')
            return redirect(url_for('login'))

        session['user'] = {
            'email': user_record['email'],
            'role': user_record['role'],
            'name': user_record['name']
        }

        flash(f'Welcome, {user_record["name"]}!', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        flash(f'Login failed: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    """Logout current user"""
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Main page - redirect to login if not authenticated."""
    if 'user' not in session:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Main system dashboard"""
    user = session['user']
    return render_template('dashboard.html', user=user)

@app.route('/user-admin')
@login_required
@role_required('admin')
def user_admin():
    """User administration page (admin only)"""
    from utils.user_registry import get_all_users
    users = get_all_users()
    return render_template('user_admin.html', users=users)

@app.route('/user-directory')
@login_required
@role_required('admin')
def user_directory():
    """User directory dashboard showing all registered users"""
    from utils.user_registry import get_all_users
    users = get_all_users()
    return render_template('user_directory.html', users=users)

@app.route('/bol-extractor')
@login_required
def bol_extractor():
    """BOL Extractor page for PDF upload and processing."""
    return render_template('bol_extractor.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle PDF file upload and processing."""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename or "unknown.pdf")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            flash(f'File {filename} uploaded successfully! Processing...', 'success')
            return redirect(url_for('dashboard'))
                
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(url_for('bol_extractor'))
    
    flash('Invalid file type. Please upload a PDF file.')
    return redirect(request.url)

# Additional routes that templates are expecting
@app.route('/work-order-form')
@login_required
def work_order_form():
    """Work order form placeholder"""
    return "<h1>Work Order Form</h1><p>This feature will be implemented soon.</p>"

@app.route('/finished-tag')
@login_required
def finished_tag():
    """Finished tag form"""
    return render_template('finished_tag.html')

@app.route('/create-user')
@login_required
@role_required('admin')
def create_user():
    """Create user placeholder"""
    return "<h1>Create User</h1><p>This feature will be implemented soon.</p>"

@app.route('/control')
@login_required
@role_required('admin')
def control():
    """Control panel placeholder"""
    return "<h1>Control Panel</h1><p>This feature will be implemented soon.</p>"

@app.route('/api/lookup-heat-numbers', methods=['POST'])
@login_required
def lookup_heat_numbers():
    """API endpoint to lookup heat numbers from incoming tag numbers"""
    try:
        data = request.get_json()
        incoming_tags = data.get('incoming_tags', '').strip()
        
        if not incoming_tags:
            return jsonify({'heat_numbers': ''})
        
        # Parse incoming tags
        import re
        tag_list = re.split(r'[,\n\r]+', incoming_tags)
        tag_list = [tag.strip().upper() for tag in tag_list if tag.strip()]
        
        if not tag_list:
            return jsonify({'heat_numbers': ''})
        
        # Initialize Google Sheets connection using existing infrastructure
        import os
        import json
        import gspread
        from google.oauth2.service_account import Credentials
        
        try:
            # Set up credentials
            SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
            credentials = Credentials.from_service_account_info(
                json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_KEY_NMP']), scopes=SCOPES
            )
            
            client = gspread.authorize(credentials)
            spreadsheet = client.open_by_key(os.environ['SPREADSHEET_ID_NMP'])
            
            # Access IN_PROCESS worksheet
            in_process_sheet = spreadsheet.worksheet("IN_PROCESS")
            
            # Get all data from IN_PROCESS sheet
            in_process_data = in_process_sheet.get_all_records()
            
            # Find matching heat numbers
            found_heat_numbers = []
            
            for row in in_process_data:
                # Look for tag number in various possible column names
                tag_value = None
                for col_name in ['Tag #', 'Tag Number', 'tag_number', 'Customer Tag', 'customer_tag']:
                    if col_name in row and row[col_name]:
                        tag_value = str(row[col_name]).strip().upper()
                        break
                
                if tag_value and tag_value in tag_list:
                    # Look for heat number in various possible column names
                    heat_number = None
                    for heat_col in ['Heat Number', 'Heat', 'heat_number', 'heat']:
                        if heat_col in row and row[heat_col]:
                            heat_number = str(row[heat_col]).strip()
                            break
                    
                    if heat_number and heat_number not in found_heat_numbers:
                        found_heat_numbers.append(heat_number)
            
            return jsonify({'heat_numbers': ', '.join(found_heat_numbers)})
            
        except Exception as e:
            logger.error(f"Error accessing Google Sheets: {str(e)}")
            return jsonify({'heat_numbers': '', 'error': 'Unable to access inventory data'})
        
    except Exception as e:
        logger.error(f"Error in heat number lookup: {str(e)}")
        return jsonify({'heat_numbers': '', 'error': 'Lookup failed'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)