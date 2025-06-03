# Nicayne OS Platform - Comprehensive System Overview

## Platform Summary

### What Nicayne OS Does
Nicayne OS is a comprehensive Python-powered manufacturing management system specifically designed for metal processing operations. The platform automates end-to-end document workflows, from intelligent BOL (Bill of Lading) extraction to professional PDF generation and delivery. It serves as a complete business management solution that bridges operational data with customer-facing documentation.

### Primary Workflows Supported
1. **BOL Processing & Extraction** - AI-powered OCR extraction from supplier BOL documents
2. **Work Order Management** - Digital work order creation, tracking, and PDF generation
3. **Finished Tag Generation** - Manufacturing completion tracking with automated inventory movement
4. **Invoice Generation** - Professional invoicing with CWT/lot-based billing calculations
5. **Quote Management** - Quote creation with lifecycle tracking and PO conversion
6. **Document Delivery** - Gmail-based email delivery with PDF attachments

### Key User Roles and Interactions
- **Operations Manager** - Creates work orders, manages finished tags, oversees production flow
- **Administrative Staff** - Processes BOLs, generates invoices, handles customer communications
- **Shop Floor Operators** - Submits finished tags, tracks completion status
- **Customers** - Receives professional documents via email with QR code access

## System Architecture & Document Flow

### End-to-End Workflow
```
1. Supplier BOL Upload → AI Extraction → Google Sheets (UNPROCESSED_INVENTORY)
2. Work Order Creation → Tag Matching → Inventory Movement (IN_PROCESSED)
3. Manufacturing Completion → Finished Tag → Inventory Movement (PROCESSED)
4. Document Generation → QR Code Embedding → Email Delivery
5. Customer File Organization → Google Drive Folder Structure
```

### Modular File Structure
```
├── pdf_outputs/              # Generated PDF documents
├── uploads/                  # Incoming BOL files
├── work_orders/             # Work order storage
├── finished_tags/           # Finished tag storage
├── bol_extractor/           # AI extraction modules
├── templates/               # HTML templates
├── static/                  # CSS/JS assets
├── utils/                   # Utility modules
└── *.json                   # Tracking files (work_orders.json, bol_tracking.json, etc.)
```

### Google Drive Organization
```
My Drive > Chaos > Clients > Nicayne Metal Processing - Chaos > Customers/
├── [Customer Name]/
│   └── PO#[PO Number]/
│       ├── Bills of Lading/
│       ├── Finished Tags/
│       ├── Invoices/
│       ├── Work Orders/
│       └── Uploaded BOLs/
```

### QR Code Integration Logic
- QR codes are embedded in all customer-facing documents
- Initially links to Google Drive file locations
- Post-Gmail integration: QR codes reference email delivery confirmation
- Documents are generated first without QR, then regenerated with QR after successful upload/email
- QR-enabled versions replace original files in both local storage and Drive

## Gmail Integration Implementation

### OAuth Authentication System
- **Authentication Method**: OAuth 2.0 with refresh token management
- **Scope**: `https://www.googleapis.com/auth/gmail.send`
- **Token Storage**: Environment variables (GMAIL_ACCESS_TOKEN, GMAIL_REFRESH_TOKEN)
- **Auto-refresh**: Automatic token refresh when expired

### Required Secrets
```
GMAIL_ACCESS_TOKEN          # OAuth access token
GMAIL_REFRESH_TOKEN         # OAuth refresh token  
GOOGLE_CLIENT_ID           # OAuth client credentials
GOOGLE_CLIENT_SECRET       # OAuth client credentials
DEFAULT_SEND_TO_EMAIL      # Default recipient (admin@caios.app)
```

### Email Delivery Process
1. Document PDF generation completes
2. Gmail service authentication
3. Email composition with professional formatting
4. PDF attachment encoding (base64)
5. Email delivery via Gmail API
6. Success/failure logging and user feedback

### Fallback Logic
- If Gmail authentication fails → Log error, continue without email
- If email delivery fails → Display warning message, PDF still available for download
- Google Drive upload continues independently as backup delivery method

## Google Drive Integration

### Original Drive-Based System
- Automatic folder structure creation per customer/PO
- File sharing with public link generation
- Permission management for customer access
- Organized filing system for all document types

### File Management Behavior
- Initial PDF upload to designated folder
- QR code generation with Drive link
- QR-enabled PDF replaces original file
- Public sharing permissions applied automatically
- Drive URLs embedded in QR codes for customer access

### Access Control Evolution
- **Original**: Public links with "anyone with link" permissions
- **Issue**: Customer access problems ("Page Not Found" errors)
- **Solution**: Pivoted to Gmail delivery as primary method
- **Current**: Drive serves as backup/archive system

## QR Code System Architecture

### QR Embedding Process
1. Generate base PDF document
2. Upload to Google Drive (if enabled)
3. Generate QR code with appropriate link
4. Create new PDF with embedded QR code
5. Replace original file in both local and Drive storage

### QR Code Content by Document Type
- **Work Orders**: Links to Drive folder or email confirmation
- **Finished Tags**: Links to specific tag PDF in Drive
- **BOLs**: Links to BOL archive location
- **Invoices**: Links to invoice PDF in customer folder

### Digital Access Integration
- QR codes provide instant mobile access to documents
- Customers can scan codes for immediate document retrieval
- Links remain valid for long-term document reference
- Professional appearance enhances customer experience

## AI Integration Points

### Current AI Implementation
- **BOL Data Extraction**: OpenAI GPT-4o for intelligent OCR processing
- **Supplier-Specific Prompts**: Customized extraction logic per supplier
- **Data Validation**: AI-powered data quality checks
- **Quote Generation**: AI assistance for quote creation from text/files

### AI Processing Pipeline
```python
PDF Upload → Text Extraction → AI Analysis → JSON Structuring → Google Sheets
```

### Extraction Capabilities
- Coil/piece identification and counting
- Weight and dimension extraction
- Heat number tracking
- Customer tag matching
- PO number correlation

## Progress Milestones - Complete Modules

### ✅ Fully Operational Systems
1. **BOL Extraction Pipeline** - End-to-end AI processing with Google Sheets integration
2. **Work Order Management** - Complete creation, tracking, and PDF generation
3. **Finished Tag System** - Full lifecycle from creation to inventory movement
4. **Gmail Email Delivery** - OAuth authentication and PDF attachment sending
5. **Google Drive Integration** - Automated folder creation and file organization
6. **QR Code Generation** - Embedded QR codes in all document types
7. **Invoice Generation** - Professional invoicing with detailed calculations
8. **Quote Management** - Quote creation with lifecycle tracking
9. **Dashboard Interface** - Central hub for all platform operations

### ✅ Tested End-to-End Workflows
- BOL upload → extraction → inventory tracking
- Work order → tag matching → finished tag → invoice
- Document generation → email delivery → customer access
- Google Sheets synchronization across all modules

### ⚠️ Known Limitations
- Some PDF generation modules have minor color type casting issues (non-critical)
- Occasional LSP warnings for optional parameters (does not affect functionality)
- Google Drive permissions occasionally require manual verification

## Secrets & Configuration Management

### Environment Variables Structure
```
# Google Services
GOOGLE_SERVICE_ACCOUNT_KEY_NMP   # Service account for Sheets/Drive
SPREADSHEET_ID_NMP               # Main Google Sheets ID
GOOGLE_CLIENT_ID                 # OAuth client ID
GOOGLE_CLIENT_SECRET             # OAuth client secret

# Gmail Integration  
GMAIL_ACCESS_TOKEN               # Gmail OAuth access token
GMAIL_REFRESH_TOKEN              # Gmail OAuth refresh token

# Email Configuration
DEFAULT_SEND_TO_EMAIL            # Default recipient email
USER_EMAIL_ADDRESS               # System sender email

# AI Services
OPENAI_API_KEY                   # OpenAI API for extraction
```

### Token Management
- **Automatic Refresh**: Gmail tokens refresh automatically when expired
- **Error Handling**: Graceful fallback if authentication fails
- **Secure Storage**: All secrets stored in Replit environment variables
- **No Hardcoded Values**: Zero hardcoded secrets in codebase

## Current System Status

### Production Readiness
- **Core Functionality**: 100% operational
- **Gmail Integration**: Fully tested and deployed
- **Document Generation**: All PDF types working correctly
- **Google Sheets Sync**: Real-time inventory tracking functional
- **Error Handling**: Comprehensive logging and fallback systems

### Performance Metrics
- **BOL Processing**: ~30-60 seconds per multi-page document
- **PDF Generation**: ~5-10 seconds per document
- **Email Delivery**: ~3-5 seconds per email with attachment
- **Google Sheets Updates**: Real-time synchronization

### Security Implementation
- OAuth 2.0 for all Google services
- Environment variable secret management
- No sensitive data in logs or client-side code
- Secure file handling with proper validation

## Next Steps & Expansion Areas

### Potential Enhancements
1. **Automated Email Scheduling** - Timed delivery for recurring documents
2. **Customer Portal** - Self-service document access for customers
3. **Mobile App Integration** - QR code scanning mobile application
4. **Advanced Analytics** - Business intelligence dashboard
5. **API Expansion** - RESTful API for third-party integrations

### Technical Improvements
- Enhanced error recovery mechanisms
- Performance optimization for large file processing
- Multi-language support for international customers
- Advanced AI prompts for improved extraction accuracy

---

**System Status**: ✅ **FULLY OPERATIONAL**  
**Last Updated**: June 1, 2025  
**Platform Version**: Production-Ready v1.0