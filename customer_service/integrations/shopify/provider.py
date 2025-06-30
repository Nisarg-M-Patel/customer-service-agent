from typing import List, Dict, Optional
from ...database.models import StandardProduct, StandardCustomer
from .auth import ShopifyAuth
from .products import ShopifyProducts

class ShopifyProvider:
    """Shopify integration provider."""
    
    def __init__(self, shop_domain: str, access_token: str):
        self.auth = ShopifyAuth(shop_domain, access_token)
        self.products_api = ShopifyProducts(self.auth)
        
        # Test connection on init
        if not self.auth.test_connection():
            raise Exception("Failed to connect to Shopify")
    
    def search_products(self, query: str = None, category: str = None, **filters) -> List[StandardProduct]:
        """Search products."""
        if query:
            return self.products_api.search_products(query)
        else:
            return self.products_api.get_products()
    
    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get product by ID."""
        return self.products_api.get_product_by_id(product_id)
    
    def check_inventory(self, product_id: str) -> Dict:
        """Check product inventory."""
        product = self.get_product_by_id(product_id)
        if not product:
            return {"available": False, "error": "Product not found"}
        
        return {
            "available": product.inventory_quantity > 0,
            "quantity": product.inventory_quantity,
            "product_name": product.title
        }
    
    def get_customer_by_id(self, customer_id: str) -> Optional[StandardCustomer]:
        """Get customer by ID - placeholder for now."""
        return None