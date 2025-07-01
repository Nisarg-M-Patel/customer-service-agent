# customer_service/integrations/manager.py
"""Integration manager - routes requests to configured providers."""

import logging
from typing import List, Dict, Optional
from ..config import Config
from ..database.models import StandardProduct, StandardCustomer
from .mock.provider import MockProvider

# Import Elasticsearch integration
try:
    from .elasticsearch.provider import ElasticsearchProvider
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    ElasticsearchProvider = None

logger = logging.getLogger(__name__)

class IntegrationManager:
    """Manages all integrations and routes requests to appropriate providers."""
    
    def __init__(self, config: Config):
        self.config = config
        self._providers = {}
        self._search_provider = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize configured providers."""
        # Always initialize mock provider as fallback
        self._providers["mock"] = MockProvider()
        logger.info("Initialized mock provider")
        
        # Initialize Shopify provider if configured
        if hasattr(self.config, 'SHOPIFY_SHOP_URL') and self.config.SHOPIFY_SHOP_URL:
            try:
                from .shopify.provider import ShopifyProvider
                self._providers["shopify"] = ShopifyProvider(self.config)
                logger.info("Initialized Shopify provider")
            except ImportError:
                logger.warning("Shopify provider not available")
        
        # Initialize Elasticsearch provider if available and configured
        if ELASTICSEARCH_AVAILABLE and self.config.SEARCH_PROVIDER == "elasticsearch":
            try:
                self._search_provider = ElasticsearchProvider(self.config)
                logger.info("Initialized Elasticsearch search provider")
                
                # Sync data to Elasticsearch if needed
                self._sync_to_elasticsearch()
                
            except Exception as e:
                logger.error(f"Failed to initialize Elasticsearch provider: {e}")
                logger.info("Falling back to standard provider for search")
                self._search_provider = None
        
        logger.info(f"Search provider: {'Elasticsearch' if self._search_provider else self.config.INTEGRATION_MODE}")
    
    def _sync_to_elasticsearch(self):
        """Sync products from primary provider to Elasticsearch if needed."""
        if not self._search_provider:
            return
            
        try:
            # Get primary data provider (Shopify or mock)
            primary_provider = self._get_primary_provider()
            
            # Check if sync is needed (could add timestamp checking here)
            logger.info("Checking if Elasticsearch sync is needed...")
            
            # For now, always sync on startup (you could optimize this later)
            indexed_count = self._search_provider.sync_from_provider(primary_provider)
            if indexed_count > 0:
                logger.info(f"Synced {indexed_count} products to Elasticsearch")
            
        except Exception as e:
            logger.error(f"Elasticsearch sync failed: {e}")
    
    def _get_primary_provider(self):
        """Get the primary data provider (for non-search operations)."""
        provider_name = self.config.INTEGRATION_MODE
        return self._providers.get(provider_name, self._providers["mock"])
    
    def search_products(self, query: str = None, category: str = None, **filters) -> List[StandardProduct]:
        """Search for products using the configured search provider."""
        
        # Use Elasticsearch for search if available
        if self._search_provider:
            try:
                return self._search_provider.search_products(query=query, category=category, **filters)
            except Exception as e:
                logger.error(f"Elasticsearch search failed, falling back: {e}")
                # Fall through to standard provider
        
        # Fallback to standard provider
        primary_provider = self._get_primary_provider()
        try:
            return primary_provider.search_products(query=query, category=category, **filters)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get specific product by ID from primary provider."""
        primary_provider = self._get_primary_provider()
        try:
            return primary_provider.get_product_by_id(product_id)
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None
    
    def check_inventory(self, product_id: str) -> Dict:
        """Check product inventory from primary provider."""
        primary_provider = self._get_primary_provider()
        try:
            return primary_provider.check_inventory(product_id)
        except Exception as e:
            logger.error(f"Error checking inventory for {product_id}: {e}")
            return {"available": False, "error": str(e)}
    
    def get_customer_by_id(self, customer_id: str) -> Optional[StandardCustomer]:
        """Get customer by ID from primary provider."""
        primary_provider = self._get_primary_provider()
        try:
            return primary_provider.get_customer_by_id(customer_id)
        except Exception as e:
            logger.error(f"Error getting customer {customer_id}: {e}")
            return None
    
    def get_search_suggestions(self, query: str, size: int = 5) -> List[str]:
        """Get search suggestions."""
        if self._search_provider:
            try:
                return self._search_provider.get_search_suggestions(query, size)
            except Exception as e:
                logger.error(f"Search suggestions failed: {e}")
        return []