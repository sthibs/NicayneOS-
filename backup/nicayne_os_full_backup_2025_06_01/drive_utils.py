"""
Google Drive utilities for uploading finished tag PDFs
"""
import os
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

def get_folder_id(secret_name):
    """Extract folder ID from URL or return direct ID."""
    val = os.environ.get(secret_name)
    if val is None:
        raise Exception(f"Missing secret: {secret_name}")
    return val.split('folders/')[-1].split('?')[0] if 'folders/' in val else val

class DriveUploader:
    def __init__(self):
        """Initialize Google Drive service using existing service account credentials."""
        try:
            # Use the same service account key as the sheets integration
            service_account_key = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY_NMP')
            if not service_account_key:
                raise ValueError("Google service account key not found")
                
            # Parse the service account credentials - same as sheets integration
            creds_info = json.loads(service_account_key)
            
            # Use same scopes as the working sheets integration
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Create credentials exactly like the sheets integration
            credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
            
            # Build the Drive service
            self.service = build('drive', 'v3', credentials=credentials)
            print("Google Drive service initialized successfully")
            
        except Exception as e:
            print(f"Error initializing Google Drive service: {str(e)}")
            self.service = None

    def share_file_with_user(self, file_id):
        """Make file publicly accessible to anyone with the link."""
        try:
            # Make file accessible to anyone with the link
            public_permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=public_permission
            ).execute()
            
            print(f"✓ File made publicly accessible")
            return True
            
        except Exception as e:
            print(f"Warning: Could not make file public: {str(e)}")
            return False

    def create_or_get_folder(self, name, parent_id=None):
        """Create a folder or get existing folder ID."""
        if not self.service:
            return None
            
        try:
            # Search for existing folder
            query = f"name='{name}' and mimeType='application/vnd.google-apps.folder'"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            query += " and trashed=false"
            
            results = self.service.files().list(q=query).execute()
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            
            # Create new folder
            folder_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_id:
                folder_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(body=folder_metadata).execute()
            return folder.get('id')
            
        except Exception as e:
            print(f"Error creating/getting folder '{name}': {str(e)}")
            return None

    def upload_finished_tag_pdf(self, pdf_path, customer_name, po_number):
        """Upload finished tag PDF to organized Drive structure."""
        if not self.service or not os.path.exists(pdf_path):
            print(f"Upload failed: Service unavailable or file not found: {pdf_path}")
            return None
            
        try:
            print(f"Starting Google Drive upload for: {os.path.basename(pdf_path)}")
            
            # Create folder structure: Chaos > Clients > Nicayne Metal Processing - Chaos > Customers
            print("Creating/verifying folder structure...")
            chaos_folder = self.create_or_get_folder("Chaos")
            if not chaos_folder:
                print("Failed to create/access Chaos folder")
                return None
                
            clients_folder = self.create_or_get_folder("Clients", chaos_folder)
            if not clients_folder:
                print("Failed to create/access Clients folder")
                return None
                
            nmp_folder = self.create_or_get_folder("Nicayne Metal Processing - Chaos", clients_folder)
            if not nmp_folder:
                print("Failed to create/access NMP folder")
                return None
                
            customers_folder = self.create_or_get_folder("Customers", nmp_folder)
            if not customers_folder:
                print("Failed to create/access Customers folder")
                return None
            
            # Create customer and PO folders
            print(f"Creating customer folder: {customer_name}")
            customer_folder = self.create_or_get_folder(customer_name, customers_folder)
            if not customer_folder:
                print(f"Failed to create/access customer folder: {customer_name}")
                return None
                
            customer_po_folder_name = f"{customer_name} - PO#{po_number}"
            print(f"Creating PO folder: {customer_po_folder_name}")
            po_folder = self.create_or_get_folder(customer_po_folder_name, customer_folder)
            if not po_folder:
                print(f"Failed to create/access PO folder: {customer_po_folder_name}")
                return None
            
            # Upload the PDF file
            file_name = os.path.basename(pdf_path)
            file_metadata = {
                'name': file_name,
                'parents': [po_folder]
            }
            
            print(f"Uploading PDF: {file_name}")
            media = MediaFileUpload(pdf_path, mimetype='application/pdf')
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            file_id = file.get('id')
            file_link = file.get('webViewLink')
            
            print(f"✓ Upload successful!")
            print(f"  File ID: {file_id}")
            print(f"  File Link: {file_link}")
            print(f"  Folder Path: Chaos/Clients/Nicayne Metal Processing - Chaos/Customers/{customer_name}/{customer_po_folder_name}")
            
            return {
                'file_id': file_id,
                'file_link': file_link,
                'folder_path': f"Chaos/Clients/Nicayne Metal Processing - Chaos/Customers/{customer_name}/{customer_po_folder_name}",
                'upload_success': True
            }
            
        except Exception as e:
            print(f"✗ Google Drive upload failed: {str(e)}")
            return {
                'upload_success': False,
                'error': str(e)
            }
    
    def upload_work_order_pdf(self, pdf_path, customer_name, po_number):
        """Upload work order PDF to organized Drive structure."""
        if not self.service:
            print("Google Drive service not available")
            return {'upload_success': False, 'error': 'Drive service not initialized'}
            
        try:
            # Create the folder structure first
            folder_result = self.create_po_folder_structure(customer_name, po_number)
            if not folder_result or not folder_result.get('po_folder_id'):
                return {'upload_success': False, 'error': 'Failed to create folder structure'}
            
            po_folder_id = folder_result['po_folder_id']
            
            # Upload the PDF file directly to the PO folder (not subfolder)
            print(f"✓ Uploading work order PDF directly to PO folder: {po_folder_id}")
            
            file_name = os.path.basename(pdf_path)
            file_metadata = {
                'name': file_name,
                'parents': [po_folder_id]
            }
            
            print(f"Uploading work order PDF: {file_name}")
            media = MediaFileUpload(pdf_path, mimetype='application/pdf')
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            file_id = file.get('id')
            file_link = file.get('webViewLink')
            
            # Share the file with the user
            self.share_file_with_user(file_id)
            
            print(f"✓ Work order PDF uploaded successfully!")
            print(f"  File ID: {file_id}")
            print(f"  File Link: {file_link}")
            
            return {
                'file_id': file_id,
                'file_link': file_link,
                'folder_path': f"Chaos/Clients/Nicayne Metal Processing - Chaos/Customers/{customer_name}/PO#{po_number}",
                'upload_success': True
            }
            
        except Exception as e:
            print(f"✗ Work order PDF upload failed: {str(e)}")
            return {
                'upload_success': False,
                'error': str(e)
            }
    
    def create_po_folder_structure(self, customer_name, po_number):
        """
        Create complete folder structure for a work order using existing folder IDs:
        My Drive > Chaos > Clients > Nicayne Metal Processing - Chaos > 
        Customers > [Customer Name] > PO#[PO Number]
        
        With subfolders: Finished Tags, Bills of Lading, Invoices
        """
        if not self.service:
            print("Google Drive service not available")
            return None
            
        try:
            print(f"Creating PO folder structure for {customer_name}, PO: {po_number}")
            
            # Get existing folder IDs from secrets
            CHAOS_ROOT_ID = get_folder_id("CAIOS_ROOT_FOLDER_URL")
            CLIENTS_FOLDER_ID = get_folder_id("CLIENTS_FOLDER_URL") 
            NMP_FOLDER_ID = get_folder_id("NMP_FOLDER_URL")
            
            print("✓ Using existing folder structure from secrets")
            
            folder_ids = {
                "Chaos": CHAOS_ROOT_ID,
                "Clients": CLIENTS_FOLDER_ID,
                "Nicayne Metal Processing - Chaos": NMP_FOLDER_ID
            }
            
            # Create Customers folder under NMP folder  
            customers_folder_id = self.create_or_get_folder("Customers", NMP_FOLDER_ID)
            if not customers_folder_id:
                print("✗ Failed to create Customers folder")
                return None
            folder_ids["Customers"] = customers_folder_id
            print("✓ Created/found folder: Customers")
            
            # Create customer folder under Customers
            customer_folder_id = self.create_or_get_folder(customer_name, customers_folder_id)
            if not customer_folder_id:
                print(f"✗ Failed to create customer folder: {customer_name}")
                return None
            folder_ids[customer_name] = customer_folder_id
            print(f"✓ Created/found folder: {customer_name}")
            
            # Create PO folder under customer folder
            po_folder_name = f"PO#{po_number}"
            po_folder_id = self.create_or_get_folder(po_folder_name, customer_folder_id)
            if not po_folder_id:
                print(f"✗ Failed to create PO folder: {po_folder_name}")
                return None
            folder_ids[po_folder_name] = po_folder_id
            print(f"✓ Created/found folder: {po_folder_name}")
            
            # PO folder was already created above
            # Use the po_folder_id from the creation step
            
            print(f"Successfully created PO folder structure for PO#{po_number}")
            return {
                'po_folder_id': po_folder_id,
                'customer_folder_id': folder_ids.get(customer_name),
                'full_path': f"Chaos/Clients/Nicayne Metal Processing - Chaos/Customers/{customer_name}/PO#{po_number}"
            }
            
        except Exception as e:
            print(f"Error creating PO folder structure: {str(e)}")
            return None

    def upload_invoice_pdf(self, pdf_path, customer_name, po_number):
        """Upload invoice PDF to organized Drive structure."""
        if not self.service:
            print("Google Drive service not available")
            return {'upload_success': False, 'error': 'Drive service not initialized'}
            
        try:
            # Create the folder structure first
            folder_result = self.create_po_folder_structure(customer_name, po_number)
            if not folder_result or not folder_result.get('po_folder_id'):
                return {'upload_success': False, 'error': 'Failed to create folder structure'}
            
            po_folder_id = folder_result['po_folder_id']
            
            # Check if Invoice.pdf already exists and delete it
            existing_files = self.service.files().list(
                q=f"name='Invoice.pdf' and parents in '{po_folder_id}' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            for file_item in existing_files.get('files', []):
                self.service.files().delete(fileId=file_item['id']).execute()
                print(f"Replaced existing Invoice.pdf in {customer_name}/PO#{po_number}")
            
            # Upload the invoice PDF as "Invoice.pdf"
            file_metadata = {
                'name': 'Invoice.pdf',
                'parents': [po_folder_id]
            }
            
            print(f"Uploading invoice PDF as Invoice.pdf to PO#{po_number}")
            media = MediaFileUpload(pdf_path, mimetype='application/pdf')
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            file_id = file.get('id')
            file_link = file.get('webViewLink')
            
            # Share the file with the user
            self.share_file_with_user(file_id)
            
            print(f"✓ Invoice PDF uploaded successfully!")
            print(f"  File ID: {file_id}")
            print(f"  File Link: {file_link}")
            print(f"  Location: Customers/{customer_name}/PO#{po_number}/Invoice.pdf")
            
            return {
                'file_id': file_id,
                'file_link': file_link,
                'folder_path': f"Chaos/Clients/Nicayne Metal Processing - Chaos/Customers/{customer_name}/PO#{po_number}",
                'upload_success': True
            }
            
        except Exception as e:
            print(f"✗ Invoice PDF upload failed: {str(e)}")
            return {
                'upload_success': False,
                'error': str(e)
            }

    def upload_signed_bol(self, file_path, customer_name, po_number, bol_number):
        """Upload signed BOL to organized Drive structure."""
        if not self.service:
            print("Google Drive service not available")
            return {'upload_success': False, 'error': 'Drive service not initialized'}
            
        try:
            # Create the folder structure first
            folder_result = self.create_po_folder_structure(customer_name, po_number)
            if not folder_result or not folder_result.get('po_folder_id'):
                return {'upload_success': False, 'error': 'Failed to create folder structure'}
            
            po_folder_id = folder_result['po_folder_id']
            
            # Generate filename
            file_extension = os.path.splitext(file_path)[1]
            filename = f"NMP-SIGNED-BOL-{bol_number}{file_extension}"
            
            # Check if file already exists and delete it
            existing_files = self.service.files().list(
                q=f"name='{filename}' and parents in '{po_folder_id}' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            for file_item in existing_files.get('files', []):
                self.service.files().delete(fileId=file_item['id']).execute()
                print(f"Replaced existing {filename} in {customer_name}/PO#{po_number}")
            
            # Upload the signed BOL
            file_metadata = {
                'name': filename,
                'parents': [po_folder_id]
            }
            
            print(f"Uploading signed BOL as {filename} to PO#{po_number}")
            
            # Determine MIME type based on file extension
            mime_type = 'application/pdf' if file_extension.lower() == '.pdf' else 'image/jpeg'
            media = MediaFileUpload(file_path, mimetype=mime_type)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            
            file_id = file.get('id')
            file_link = file.get('webViewLink')
            
            print(f"✓ Signed BOL uploaded successfully!")
            print(f"  File ID: {file_id}")
            print(f"  File Link: {file_link}")
            print(f"  Location: Customers/{customer_name}/PO#{po_number}/{filename}")
            
            return {
                'file_id': file_id,
                'file_link': file_link,
                'filename': filename,
                'folder_path': f"Chaos/Clients/Nicayne Metal Processing - Chaos/Customers/{customer_name}/PO#{po_number}",
                'upload_success': True
            }
            
        except Exception as e:
            print(f"✗ Signed BOL upload failed: {str(e)}")
            return {
                'upload_success': False,
                'error': str(e)
            }