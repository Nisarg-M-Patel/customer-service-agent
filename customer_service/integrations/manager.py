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

# Module-level singleton variables
_instance = None
_config_hash = None

class IntegrationManager:
    """Manages all integrations and routes requests to appropriate providers."""
    
    def __init__(self, config: Config):
        self.config = config
        self._providers = {}
        self._search_provider = None
        self._initialize_providers()

    @classmethod
    def get_instance(cls) -> 'IntegrationManager':
        """Get singleton instance of IntegrationManager."""
        global _instance, _config_hash
        
        # Create config to check if it changed
        config = Config()
        current_config_hash = hash(f"{config.INTEGRATION_MODE}_{config.DATABASE_URL}")
        
        # Create new instance if none exists or config changed
        if _instance is None or _config_hash != current_config_hash:
            logger.info("Creating new IntegrationManager instance")
            _instance = cls(config)
            _config_hash = current_config_hash
        
        return _instance
    
    def _initialize_providers(self):
        """Initialize configured providers."""
        # Always initialize mock provider as fallback
        self._providers["mock"] = MockProvider()
        logger.info("Initialized mock provider")
        
        # Initialize Shopify provider if configured
        if hasattr(self.config, 'SHOPIFY_SHOP_URL') and self.config.SHOPIFY_SHOP_URL:
            try:
                from .shopify.provider import ShopifyProvider
                self._providers["shopify"] = ShopifyProvider(
                    shop_domain=self.config.SHOPIFY_SHOP_URL,
                    access_token=self.config.SHOPIFY_ACCESS_TOKEN
                    )
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
            logger.info(f"Using primary provider for sync: {type(primary_provider).__name__}")
            
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

    def search_products_with_intent(self, query: str = None, intent_mode: bool = True, **filters):
        """Search for products using intent analysis or fallback to keyword search."""
        
        # Try intent search first if available and enabled
        if intent_mode and self._search_provider:
            try:
                intent_matches = self._search_provider.search_by_intent(query, **filters)
                
                if intent_matches:
                    # Build enhanced results with metadata
                    enhanced_results = []
                    for match in intent_matches:
                        product = self.get_product_by_id(match.product_id)
                        if product:
                            enhanced_results.append({
                                "product": product,
                                "confidence_score": match.confidence,
                                "match_reasons": match.reasons
                            })
                    
                    logger.info(f"Intent search returned {len(enhanced_results)} products")
                    return enhanced_results
                else:
                    logger.info("Intent search returned no results, falling back to keyword search")
                    
            except Exception as e:
                logger.error(f"Intent search failed, falling back to keyword search: {e}")
        
        # Fallback to regular keyword search - return products in same enhanced format
        products = self.search_products(query=query, **filters)
        
        # Wrap regular products in enhanced format (no confidence scores)
        enhanced_results = []
        for product in products:
            enhanced_results.append({
                "product": product,
                "confidence_score": None,
                "match_reasons": ["keyword_match"]
            })
        
        return enhanced_results