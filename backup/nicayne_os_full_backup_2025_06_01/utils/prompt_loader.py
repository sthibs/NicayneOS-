"""
Supplier-specific prompt loading utilities.
Manages loading and saving of custom extraction prompts per supplier.
"""

import json
import logging
import os
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class PromptLoader:
    """Manages supplier-specific extraction prompts."""
    
    def __init__(self, prompts_file: str = "supplier_prompts.json"):
        """
        Initialize prompt loader.
        
        Args:
            prompts_file: Path to the supplier prompts JSON file
        """
        self.prompts_file = prompts_file
        self.prompts = {}
        self.load_prompts()
        logger.info("Prompt loader initialized")
    
    def load_prompts(self):
        """Load supplier prompts from JSON file."""
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    self.prompts = json.load(f)
                logger.info(f"Loaded {len(self.prompts)} supplier prompts")
            else:
                logger.warning(f"Prompts file {self.prompts_file} not found, using empty prompts")
                self.prompts = {}
        except Exception as e:
            logger.error(f"Error loading prompts: {str(e)}")
            self.prompts = {}
    
    def save_prompts(self):
        """Save current prompts to JSON file."""
        try:
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.prompts)} supplier prompts to {self.prompts_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving prompts: {str(e)}")
            return False
    
    def get_prompt_for_supplier(self, supplier_name: str) -> str:
        """
        Get the extraction prompt for a specific supplier.
        
        Args:
            supplier_name: Name/ID of the supplier
            
        Returns:
            Supplier-specific prompt or default prompt
        """
        # Force reload prompts to ensure we have the latest version
        self.load_prompts()
        
        supplier_key = supplier_name.lower().replace(' ', '_').replace('-', '_')
        
        if supplier_key in self.prompts and self.prompts[supplier_key].get('active', True):
            prompt = self.prompts[supplier_key].get('prompt', '')
            logger.info(f"Using custom prompt for supplier: {supplier_name}")
            return prompt
        elif 'default' in self.prompts:
            prompt = self.prompts['default'].get('prompt', '')
            logger.info(f"Using default prompt for supplier: {supplier_name}")
            return prompt
        else:
            logger.warning(f"No prompt found for supplier: {supplier_name}, using fallback")
            return "Extract BOL data with standard field mapping. Focus on accuracy and completeness."
    
    def get_supplier_info(self, supplier_name: str) -> Optional[Dict]:
        """
        Get full supplier information including prompt and metadata.
        
        Args:
            supplier_name: Name/ID of the supplier
            
        Returns:
            Supplier information dictionary or None
        """
        supplier_key = supplier_name.lower().replace(' ', '_').replace('-', '_')
        return self.prompts.get(supplier_key)
    
    def add_supplier(self, supplier_name: str, prompt: str, display_name: str = None) -> bool:
        """
        Add a new supplier with custom prompt.
        
        Args:
            supplier_name: Unique supplier identifier
            prompt: Custom extraction prompt
            display_name: Human-readable supplier name
            
        Returns:
            True if successfully added, False otherwise
        """
        try:
            supplier_key = supplier_name.lower().replace(' ', '_').replace('-', '_')
            
            self.prompts[supplier_key] = {
                'name': display_name or supplier_name,
                'prompt': prompt,
                'active': True,
                'created': datetime.now().isoformat(),
                'last_modified': datetime.now().isoformat()
            }
            
            success = self.save_prompts()
            if success:
                logger.info(f"Added new supplier: {supplier_name}")
            return success
            
        except Exception as e:
            logger.error(f"Error adding supplier {supplier_name}: {str(e)}")
            return False
    
    def update_supplier_prompt(self, supplier_name: str, prompt: str) -> bool:
        """
        Update the prompt for an existing supplier.
        
        Args:
            supplier_name: Supplier identifier
            prompt: New extraction prompt
            
        Returns:
            True if successfully updated, False otherwise
        """
        try:
            supplier_key = supplier_name.lower().replace(' ', '_').replace('-', '_')
            
            if supplier_key in self.prompts:
                self.prompts[supplier_key]['prompt'] = prompt
                self.prompts[supplier_key]['last_modified'] = datetime.now().isoformat()
                
                success = self.save_prompts()
                if success:
                    logger.info(f"Updated prompt for supplier: {supplier_name}")
                return success
            else:
                logger.error(f"Supplier {supplier_name} not found")
                return False
                
        except Exception as e:
            logger.error(f"Error updating supplier {supplier_name}: {str(e)}")
            return False
    
    def remove_supplier(self, supplier_name: str) -> bool:
        """
        Remove a supplier and their custom prompt.
        
        Args:
            supplier_name: Supplier identifier
            
        Returns:
            True if successfully removed, False otherwise
        """
        try:
            supplier_key = supplier_name.lower().replace(' ', '_').replace('-', '_')
            
            if supplier_key in self.prompts and supplier_key != 'default':
                del self.prompts[supplier_key]
                success = self.save_prompts()
                if success:
                    logger.info(f"Removed supplier: {supplier_name}")
                return success
            else:
                logger.error(f"Supplier {supplier_name} not found or cannot be removed")
                return False
                
        except Exception as e:
            logger.error(f"Error removing supplier {supplier_name}: {str(e)}")
            return False
    
    def get_all_suppliers(self) -> Dict[str, Dict]:
        """
        Get all active suppliers and their information.
        
        Returns:
            Dictionary of all supplier data
        """
        active_suppliers = {
            key: data for key, data in self.prompts.items() 
            if data.get('active', True)
        }
        logger.info(f"Retrieved {len(active_suppliers)} active suppliers")
        return active_suppliers
    
    def deactivate_supplier(self, supplier_name: str) -> bool:
        """
        Deactivate a supplier without removing their data.
        
        Args:
            supplier_name: Supplier identifier
            
        Returns:
            True if successfully deactivated, False otherwise
        """
        try:
            supplier_key = supplier_name.lower().replace(' ', '_').replace('-', '_')
            
            if supplier_key in self.prompts:
                self.prompts[supplier_key]['active'] = False
                self.prompts[supplier_key]['last_modified'] = datetime.now().isoformat()
                
                success = self.save_prompts()
                if success:
                    logger.info(f"Deactivated supplier: {supplier_name}")
                return success
            else:
                logger.error(f"Supplier {supplier_name} not found")
                return False
                
        except Exception as e:
            logger.error(f"Error deactivating supplier {supplier_name}: {str(e)}")
            return False
    
    def create_enhanced_prompt(self, base_text: str, supplier_name: str) -> str:
        """
        Create an enhanced prompt by combining base BOL extraction instructions
        with supplier-specific guidance.
        
        Args:
            base_text: Extracted text from PDF
            supplier_name: Supplier identifier
            
        Returns:
            Enhanced prompt with supplier-specific instructions
        """
        supplier_prompt = self.get_prompt_for_supplier(supplier_name)
        
        enhanced_prompt = f"""
SUPPLIER-SPECIFIC INSTRUCTIONS:
{supplier_prompt}

STANDARD BOL EXTRACTION TASK:
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
- DATE_RECEIVED: Date the shipment was received
- HEAT_NUMBER: Heat number or batch number
- CUSTOMER_PO: Customer purchase order number
- NOTES: Any additional notes or special instructions

EXTRACTION RULES:
1. Follow the supplier-specific instructions above for this supplier
2. Extract exact values as they appear in the document
3. If a field is not found, use an empty string ""
4. For dates, use YYYY-MM-DD format when possible
5. For measurements, include units (e.g., "12 inches", "2500 lbs")
6. Be case-sensitive for codes and numbers
7. Look for alternative terms (e.g., "Consignee" for customer, "Shipper" for vendor)

DOCUMENT TEXT:
{base_text[:4000]}  

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
    "DATE_RECEIVED": "",
    "HEAT_NUMBER": "",
    "CUSTOMER_PO": "",
    "NOTES": ""
}}
"""
        
        logger.info(f"Created enhanced prompt for supplier: {supplier_name}")
        return enhanced_prompt


# Global instance for easy access
prompt_loader = PromptLoader()

def get_prompt_for_supplier(supplier_name: str) -> str:
    """
    Convenience function to get supplier prompt.
    
    Args:
        supplier_name: Supplier identifier
        
    Returns:
        Supplier-specific extraction prompt
    """
    return prompt_loader.get_prompt_for_supplier(supplier_name)