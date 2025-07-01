"""Shopify products API integration."""

import logging
from typing import List, Dict, Optional
from .auth import ShopifyAuth

logger = logging.getLogger(__name__)

class ShopifyProducts:
    """Handles Shopify Products API operations."""
    
    def __init__(self, auth: ShopifyAuth):
        self.auth = auth
    
    def search(self, query: str = None, category: str = None, 
              limit: int = 50, **filters) -> List[Dict]:
        """Search for products in Shopify."""
        params = {"limit": min(limit, 250)}
        
        # Add search filters
        if query:
            params["title"] = query
        
        # Add other supported filters
        for key, value in filters.items():
            if key in ["vendor", "product_type", "status", "published_status"]:
                params[key] = value
        
        try:
            response = self.auth.make_request("products.json", params=params)
            return response.get("products", [])
            
        except Exception as e:
            logger.error(f"Error searching Shopify products: {e}")
            return []
    
    def get_by_id(self, product_id: str) -> Optional[Dict]:
        """Get specific product by ID."""
        try:
            response = self.auth.make_request(f"products/{product_id}.json")
            return response.get("product")
        except Exception as e:
            logger.error(f"Error getting Shopify product {product_id}: {e}")
            return None
    
    def get_inventory(self, product_id: str) -> Dict:
        """Get inventory information for a product."""
        try:
            product = self.get_by_id(product_id)
            if not product:
                return {"available": False, "quantity": 0}
            
            # Calculate total inventory across all variants
            variants = product.get("variants", [])
            total_quantity = sum(v.get("inventory_quantity", 0) or 0 for v in variants)
            
            return {
                "available": total_quantity > 0,
                "quantity": total_quantity,
                "title": product.get("title", ""),
                "variants": len(variants)
            }
            
        except Exception as e:
            logger.error(f"Error getting inventory for product {product_id}: {e}")
            return {"available": False, "quantity": 0, "error": str(e)}