"""
Configuration management for BOL extractor.
Loads secrets and configuration from Replit environment variables.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for BOL extractor using Replit Secrets."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self._load_config()
        self._validate_config()
        logger.info("Configuration loaded successfully")
    
    def _load_config(self):
        """Load configuration values from environment variables."""
        # Google Sheets configuration
        self.google_service_account_key = (
            os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY_NMP') or 
            os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY_CAIOS_NMP')
        )
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID_NMP')
        self.worksheet_name = os.getenv('WORKSHEET_NAME', 'UNPROCESSED_INVENTORY')
        
        # LLM API keys
        self.openai_api_key = (
            os.getenv('OPENAI_API_KEY') or 
            os.getenv('OPEN_AI_API_KEY_CAIOS')
        )
        self.deepseek_api_key = (
            os.getenv('DEEPSEEK_API_KEY') or 
            os.getenv('DEEP_SEEK_API')
        )
        
        # OCR configuration
        self.tesseract_cmd = os.getenv('TESSERACT_CMD')
        
        # Application settings
        self.test_mode = os.getenv('TEST_MODE', 'False').lower() == 'true'
        self.debug_mode = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
        
        # File upload settings
        self.max_file_size_mb = int(os.getenv('MAX_FILE_SIZE_MB', '16'))
        self.upload_folder = os.getenv('UPLOAD_FOLDER', 'uploads')
        
        # Logging level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_level = getattr(logging, log_level, logging.INFO)
    
    def _validate_config(self):
        """Validate required configuration values."""
        required_configs = []
        
        # Check Google Sheets configuration
        if not self.google_service_account_key:
            required_configs.append('GOOGLE_SERVICE_ACCOUNT_KEY_NMP')
        
        if not self.spreadsheet_id:
            required_configs.append('SPREADSHEET_ID_NMP')
        
        # Check LLM API keys (at least one required)
        if not self.openai_api_key and not self.deepseek_api_key:
            required_configs.append('OPENAI_API_KEY or DEEPSEEK_API_KEY')
        
        if required_configs:
            error_msg = f"Missing required configuration: {', '.join(required_configs)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Warn about missing optional configurations
        if not self.openai_api_key:
            logger.warning("OpenAI API key not provided - will use DeepSeek only")
        
        if not self.deepseek_api_key:
            logger.warning("DeepSeek API key not provided - will use OpenAI only")
    
    @property
    def is_test_mode(self) -> bool:
        """Check if running in test mode."""
        return self.test_mode
    
    @property
    def is_debug_mode(self) -> bool:
        """Check if running in debug mode."""
        return self.debug_mode
    
    def get_upload_path(self, filename: str) -> str:
        """
        Get full upload path for a filename.
        
        Args:
            filename: Name of the file
            
        Returns:
            Full path to the upload file
        """
        os.makedirs(self.upload_folder, exist_ok=True)
        return os.path.join(self.upload_folder, filename)
    
    def configure_logging(self):
        """Configure logging based on configuration settings."""
        logging.basicConfig(
            level=self.log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        if self.debug_mode:
            logging.getLogger().setLevel(logging.DEBUG)
        
        logger.info(f"Logging configured at level: {logging.getLevelName(self.log_level)}")
    
    def __str__(self) -> str:
        """String representation of configuration (excluding sensitive data)."""
        return f"""
BOL Extractor Configuration:
- Google Sheets: {'Configured' if self.google_service_account_key else 'Not configured'}
- Spreadsheet ID: {'Configured' if self.spreadsheet_id else 'Not configured'}
- OpenAI API: {'Configured' if self.openai_api_key else 'Not configured'}
- DeepSeek API: {'Configured' if self.deepseek_api_key else 'Not configured'}
- Test Mode: {self.test_mode}
- Debug Mode: {self.debug_mode}
- Max File Size: {self.max_file_size_mb}MB
- Upload Folder: {self.upload_folder}
"""
