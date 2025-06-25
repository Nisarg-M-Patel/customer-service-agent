"""Integration manager - routes requests to configured providers."""

import logging
from typing import List, Dict, Optional
from ..config import Config
from ..database.models import StandardProduct, StandardCustomer
from .mock.provider import MockProvider

logger = logging.getLogger(__name__)

class IntegrationManager:
    """Manages all integrations and routes requests to appropriate providers."""
    
    def __init__(self, config: Config):
        self.config = config
        self._providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize configured providers."""
        # For now, always use mock provider
        # Later this will check config and initialize real providers
        self._providers["mock"] = MockProvider()
        logger.info("Initialized mock provider")
    
    def search_products(self, query: str = None, category: str = None, **filters) -> List[StandardProduct]:
        """Search for products using configured provider."""
        provider_name = self.config.INTEGRATION_MODE
        provider = self._providers.get(provider_name)
        
        if not provider:
            logger.error(f"No provider found for {provider_name}")
            return []
        
        try:
            return provider.search_products(query=query, category=category, **filters)
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get specific product by ID."""
        provider_name = self.config.INTEGRATION_MODE
        provider = self._providers.get(provider_name)
        
        if not provider:
            logger.error(f"No provider found for {provider_name}")
            return None
        
        try:
            return provider.get_product_by_id(product_id)
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None
    
    def check_inventory(self, product_id: str) -> Dict:
        """Check product inventory."""
        provider_name = self.config.INTEGRATION_MODE
        provider = self._providers.get(provider_name)
        
        if not provider:
            logger.error(f"No provider found for {provider_name}")
            return {"available": False, "error": "No provider configured"}
        
        try:
            return provider.check_inventory(product_id)
        except Exception as e:
            logger.error(f"Error checking inventory for {product_id}: {e}")
            return {"available": False, "error": str(e)}
    
    def get_customer_by_id(self, customer_id: str) -> Optional[StandardCustomer]:
        """Get customer by ID."""
        provider_name = self.config.INTEGRATION_MODE
        provider = self._providers.get(provider_name)
        
        if not provider:
            logger.error(f"No provider found for {provider_name}")
            return None
        
        try:
            return provider.get_customer_by_id(customer_id)
        except Exception as e:
            logger.error(f"Error getting customer {customer_id}: {e}")
            return None