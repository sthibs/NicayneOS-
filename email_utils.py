"""
Gmail integration for Nicayne OS platform
OAuth-based email functionality for sending documents with PDF attachments
"""

import os
import json
import base64
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import logging

logger = logging.getLogger(__name__)

class GmailSender:
    def __init__(self):
        """Initialize Gmail sender with OAuth authentication"""
        self.service = None
        self.credentials = None
        self.scopes = ['https://www.googleapis.com/auth/gmail.send']
        
    def authenticate(self):
        """Authenticate with Gmail using OAuth 2.0"""
        try:
            # Check for token secrets
            access_token = os.environ.get('GMAIL_ACCESS_TOKEN')
            refresh_token = os.environ.get('GMAIL_REFRESH_TOKEN')
            client_id = os.environ.get('GOOGLE_CLIENT_ID')
            client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                logger.error("Gmail OAuth credentials not found in environment")
                return False
                
            # Create credentials from tokens
            if access_token and refresh_token:
                try:
                    self.credentials = Credentials(
                        token=access_token,
                        refresh_token=refresh_token,
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=client_id,
                        client_secret=client_secret,
                        scopes=self.scopes
                    )
                    
                    # Refresh credentials if needed
                    if self.credentials.expired:
                        try:
                            self.credentials.refresh(Request())
                            logger.info("Gmail credentials refreshed successfully")
                        except Exception as e:
                            logger.error(f"Failed to refresh credentials: {e}")
                            return self._initiate_oauth_flow(client_id, client_secret)
                    
                    # Build Gmail service
                    self.service = build('gmail', 'v1', credentials=self.credentials)
                    logger.info("Gmail service initialized successfully")
                    return True
                    
                except Exception as e:
                    logger.error(f"Failed to create credentials from tokens: {e}")
                    
            # If no valid credentials, initiate OAuth flow
            return self._initiate_oauth_flow(client_id, client_secret)
                
        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False
            
    def _initiate_oauth_flow(self, client_id, client_secret):
        """Initiate OAuth flow for new authentication"""
        try:
            # Create flow configuration for installed app (no redirect)
            flow_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            
            flow = Flow.from_client_config(
                flow_config,
                scopes=self.scopes,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            
            # Get authorization URL
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            logger.warning(f"Gmail OAuth required. Please visit: {auth_url}")
            print(f"\n🔐 Gmail Authentication Required")
            print(f"Please visit this URL to authorize Gmail access:")
            print(f"{auth_url}")
            print(f"\nAfter authorization, copy the authorization code and provide it to complete authentication.\n")
            
            return False  # Return False to indicate manual intervention needed
            
        except Exception as e:
            logger.error(f"OAuth flow initiation failed: {e}")
            return False
            
    def complete_oauth_flow(self, authorization_code):
        """Complete OAuth flow with authorization code"""
        try:
            client_id = os.environ.get('GOOGLE_CLIENT_ID')
            client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
            
            flow_config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            
            flow = Flow.from_client_config(
                flow_config,
                scopes=self.scopes,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            
            # Exchange authorization code for credentials
            flow.fetch_token(code=authorization_code)
            self.credentials = flow.credentials
            
            # Save credentials for future use
            token_data = {
                'token': self.credentials.token,
                'refresh_token': self.credentials.refresh_token,
                'token_uri': self.credentials.token_uri,
                'client_id': self.credentials.client_id,
                'client_secret': self.credentials.client_secret,
                'scopes': self.credentials.scopes
            }
            
            print(f"✅ Gmail authentication successful!")
            print(f"Please add this token to your Replit secrets as GMAIL_OAUTH_TOKEN:")
            print(f"{json.dumps(token_data)}")
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=self.credentials)
            return True
            
        except Exception as e:
            logger.error(f"OAuth completion failed: {e}")
            return False
            
    def send_email_with_attachment(self, to_email, subject, body, attachment_path, filename=None):
        """
        Send email with PDF attachment via Gmail API
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            body (str): Email body content
            attachment_path (str): Path to attachment file
            filename (str): Optional custom filename for attachment
            
        Returns:
            dict: Result with success status and message details
        """
        if not self.service:
            if not self.authenticate():
                return {
                    'success': False,
                    'error': 'Gmail authentication required',
                    'message': 'Please complete OAuth authentication first'
                }
                
        try:
            # Create message
            message = MIMEMultipart()
            message['to'] = to_email
            message['from'] = os.environ.get('DEFAULT_SEND_TO_EMAIL', 'admin@caios.app')
            message['subject'] = subject
            
            # Add body
            message.attach(MIMEText(body, 'plain'))
            
            # Add attachment if provided
            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())
                    
                encoders.encode_base64(part)
                
                # Use custom filename or derive from path
                attach_filename = filename or os.path.basename(attachment_path)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attach_filename}'
                )
                
                message.attach(part)
                
            # Convert message to raw format
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send email
            send_result = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"✅ Email sent to {to_email} with {attach_filename if attachment_path else 'no attachment'}")
            
            return {
                'success': True,
                'message_id': send_result.get('id'),
                'recipient': to_email,
                'subject': subject,
                'attachment': attach_filename if attachment_path else None
            }
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(f"❌ Email send failed: {error_msg}")
            
            return {
                'success': False,
                'error': error_msg,
                'recipient': to_email,
                'subject': subject
            }


# Global Gmail sender instance
gmail_sender = GmailSender()

def send_email_with_attachment(to_email, subject, body, attachment_path, filename=None):
    """
    Convenient wrapper function for sending emails with attachments
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content
        attachment_path (str): Path to attachment file
        filename (str): Optional custom filename for attachment
        
    Returns:
        dict: Result with success status and message details
    """
    return gmail_sender.send_email_with_attachment(
        to_email, subject, body, attachment_path, filename
    )

def test_gmail_connection():
    """Test Gmail connection and authentication"""
    try:
        if gmail_sender.authenticate():
            print("✅ Gmail connection successful")
            return True
        else:
            print("❌ Gmail authentication required")
            return False
    except Exception as e:
        print(f"❌ Gmail connection failed: {e}")
        return False

def setup_gmail_oauth():
    """Interactive setup for Gmail OAuth authentication"""
    print("\n🔧 Gmail OAuth Setup")
    print("This will guide you through setting up Gmail integration.")
    
    # Check for required secrets
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("\n❌ Missing OAuth credentials")
        print("Please add the following secrets to your Replit environment:")
        print("- GOOGLE_CLIENT_ID")
        print("- GOOGLE_CLIENT_SECRET")
        print("\nGet these from Google Cloud Console > APIs & Services > Credentials")
        return False
        
    # Start authentication flow
    if gmail_sender.authenticate():
        print("✅ Gmail already authenticated and ready")
        return True
    else:
        print("\n⚠️  OAuth authorization required")
        print("Follow the instructions above to complete authentication")
        return False

if __name__ == "__main__":
    # Test Gmail setup
    setup_gmail_oauth()