"""
LLM-powered data extraction and refinement for BOL documents.
Uses OpenAI GPT-4o with DeepSeek fallback for structuring extracted text.
"""

import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
import requests
from .config import Config

logger = logging.getLogger(__name__)

class LLMRefiner:
    """LLM-powered data extraction and refinement for BOL documents."""
    
    def __init__(self, config: Config):
        """Initialize LLM refiner with API configurations."""
        self.config = config
        self.openai_client = None
        
        # Initialize OpenAI client
        if config.openai_api_key:
            self.openai_client = OpenAI(api_key=config.openai_api_key)
            logger.info("OpenAI client initialized")
        else:
            logger.warning("OpenAI API key not provided")
        
        # DeepSeek configuration
        self.deepseek_api_key = config.deepseek_api_key
        self.deepseek_base_url = "https://api.deepseek.com/v1/chat/completions"
        
        if self.deepseek_api_key:
            logger.info("DeepSeek API key configured")
    
    def extract_bol_data(self, text: str, supplier_name: str = "default") -> Optional[Dict[str, Any]]:
        """
        Extract structured BOL data from raw text using LLM with supplier-specific prompts.
        
        Args:
            text: Raw text extracted from PDF
            supplier_name: Supplier identifier for custom prompt
            
        Returns:
            Structured BOL data dictionary or None if extraction fails
        """
        # Check for all BOL numbers in input text (including OCR variations)
        bol_numbers_in_input = []
        test_patterns = ["1641211", "164121t1", "164121l1", "1641212", "1641213"]
        for pattern in test_patterns:
            if pattern in text:
                bol_numbers_in_input.append(pattern)
        logger.info(f"🔍 BOL patterns found in input text: {bol_numbers_in_input}")
        
        # Try OpenAI first
        if self.openai_client:
            try:
                logger.info(f"Attempting data extraction with OpenAI GPT-4o for supplier: {supplier_name}")
                result = self._extract_with_openai(text, supplier_name)
                if result:
                    logger.info("Successfully extracted data with OpenAI")
                    return result
            except Exception as e:
                logger.warning(f"OpenAI extraction failed: {str(e)}")
        
        # Fallback to DeepSeek
        if self.deepseek_api_key:
            try:
                logger.info(f"Falling back to DeepSeek API for supplier: {supplier_name}")
                result = self._extract_with_deepseek(text, supplier_name)
                if result:
                    logger.info("Successfully extracted data with DeepSeek")
                    return result
            except Exception as e:
                logger.error(f"DeepSeek extraction failed: {str(e)}")
        
        logger.error("All LLM extraction methods failed")
        return None
    
    def _extract_with_openai(self, text: str, supplier_name: str = "default") -> Optional[Dict[str, Any]]:
        """
        Extract BOL data using OpenAI GPT-4o with supplier-specific prompts.
        
        Args:
            text: Raw text from PDF
            supplier_name: Supplier identifier for custom prompt
            
        Returns:
            Structured data dictionary or None if extraction fails
        """
        prompt = self._create_extraction_prompt(text, supplier_name)
        
        try:
            # Debug logging for prompt and response
            logger.info(f"🧾 Prompt preview (first 500 chars): {prompt[:500]}")
            
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "Extract coil-level data from the following BOL text and return one row per coil. Format as JSON with 'coils' array. Only include coils with valid customer tags."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0,  # Zero temperature for consistent extraction
                max_tokens=1500
            )
            
            result_text = response.choices[0].message.content
            logger.info(f"🧠 Raw OpenAI response length: {len(result_text)} chars")
            logger.info(f"🧠 Response preview: {result_text[:200]}...")
            
            # Check for BOL numbers in response
            if "1641213" in result_text:
                logger.info("✓ BOL #1641213 found in response")
            else:
                logger.warning("⚠️ BOL #1641213 NOT found in response")
            
            if not result_text or result_text.strip() == "":
                logger.error("OpenAI returned empty response")
                return None
            
            # Clean the response text to handle potential formatting issues
            result_text = result_text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            result_text = result_text.strip()
            
            return self._safe_json_parse(result_text)
            
        except json.JSONDecodeError as e:
            logger.error(f"OpenAI returned invalid JSON: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
    
    def _extract_with_deepseek(self, text: str, supplier_name: str = "default") -> Optional[Dict[str, Any]]:
        """
        Extract BOL data using DeepSeek API as fallback with supplier-specific prompts.
        
        Args:
            text: Raw text from PDF
            supplier_name: Supplier identifier for custom prompt
            
        Returns:
            Structured data dictionary or None if extraction fails
        """
        prompt = self._create_extraction_prompt(text, supplier_name)
        
        headers = {
            "Authorization": f"Bearer {self.deepseek_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "Extract coil-level data from the following BOL text and return one row per coil. Format as JSON with 'coils' array. Only include coils with valid customer tags."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.0,
            "max_tokens": 1500
        }
        
        try:
            response = requests.post(
                self.deepseek_base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Clean up potential JSON formatting issues
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"DeepSeek returned invalid JSON: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"DeepSeek API error: {str(e)}")
            raise
    
    def _create_extraction_prompt(self, text: str, supplier_name: str = "default") -> str:
        """
        Create a detailed prompt for BOL data extraction with supplier-specific instructions.
        
        Args:
            text: Raw text from PDF
            supplier_name: Supplier identifier for custom prompt
            
        Returns:
            Formatted prompt for LLM with supplier-specific guidance
        """
        # Import here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        try:
            from utils.prompt_loader import prompt_loader
            return prompt_loader.create_enhanced_prompt(text, supplier_name)
        except ImportError:
            logger.warning("Could not import prompt_loader, using default prompt")
            return self._create_default_prompt(text)
    
    def _safe_json_parse(self, response_text: str):
        """
        Safely parse JSON response with better error handling.
        
        Args:
            response_text: Raw response text from LLM
            
        Returns:
            Parsed JSON data or None if parsing fails
        """
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"🚫 JSON parse failed. Raw response: {response_text}")
            logger.error(f"JSON error: {str(e)}")
            return None

    def _create_default_prompt(self, text: str) -> str:
        """
        Create a default extraction prompt when supplier-specific prompts are unavailable.
        
        Args:
            text: Raw text from PDF
            
        Returns:
            Default formatted prompt for LLM
        """
        return f"""
Please analyze the following Bill of Lading (BOL) document text and extract the specified information into a JSON format.

REQUIRED FIELDS TO EXTRACT:
- BOL_NUMBER: The Bill of Lading number/ID
- CUSTOMER_NAME: Customer or consignee name
- VENDOR_NAME: Vendor, shipper, or supplier name  
- COIL_TAG#: Coil tag number or material identifier
- MATERIAL: Material type/description (steel, aluminum, etc.)
- WIDTH: Material width (include units if available)
- THICKNESS: Material thickness (include units if available)
- WEIGHT: Total weight (include units if available)
- NUMBER_OF_COILS: Number of coils in the shipment (numeric value)
- DATE_RECEIVED: Date the shipment was received
- HEAT_NUMBER: Heat number or batch number
- CUSTOMER_PO: Customer purchase order number
- NOTES: Any additional notes or special instructions

EXTRACTION RULES:
1. Extract exact values as they appear in the document
2. If a field is not found, use an empty string ""
3. For dates, use YYYY-MM-DD format when possible
4. For measurements, include units (e.g., "12 inches", "2500 lbs")
5. Be case-sensitive for codes and numbers
6. Look for alternative terms (e.g., "Consignee" for customer, "Shipper" for vendor)

DOCUMENT TEXT:
{text[:4000]}  

Return the extracted data in this exact JSON format:
{{
    "BOL_NUMBER": "",
    "CUSTOMER_NAME": "",
    "VENDOR_NAME": "",
    "COIL_TAG#": "",
    "MATERIAL": "",
    "WIDTH": "",
    "THICKNESS": "",
    "WEIGHT": "",
    "NUMBER_OF_COILS": "",
    "DATE_RECEIVED": "",
    "HEAT_NUMBER": "",
    "CUSTOMER_PO": "",
    "NOTES": ""
}}
"""
