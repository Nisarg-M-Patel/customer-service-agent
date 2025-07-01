"""Minimal Shopify provider - just fixes the None issues."""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from ...database.models import StandardProduct, StandardCustomer
from .auth import ShopifyAuth
from .products import ShopifyProducts
from .customers import ShopifyCustomers

logger = logging.getLogger(__name__)

class ShopifyProvider:
    """Shopify integration provider."""
    
    def __init__(self, shop_domain: str, access_token: str):
        self.auth = ShopifyAuth(shop_domain, access_token)
        self.products_api = ShopifyProducts(self.auth)
        self.customers_api = ShopifyCustomers(self.auth)
    
    def search_products(self, query: str = None, category: str = None, **filters) -> List[StandardProduct]:
        """Search Shopify products and convert to standard format."""
        try:
            shopify_products = self.products_api.search(query=query, collection=category, **filters)
            return [self._convert_product(p) for p in shopify_products]
        except Exception as e:
            logger.error(f"Error searching Shopify products: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get specific Shopify product by ID."""
        try:
            shopify_product = self.products_api.get_by_id(product_id)
            return self._convert_product(shopify_product) if shopify_product else None
        except Exception as e:
            logger.error(f"Error getting Shopify product {product_id}: {e}")
            return None
    
    def check_inventory(self, product_id: str) -> Dict:
        """Check Shopify inventory levels."""
        try:
            return self.products_api.get_inventory(product_id)
        except Exception as e:
            logger.error(f"Error checking Shopify inventory: {e}")
            return {"available": False, "error": str(e)}
    
    def get_customer_by_id(self, customer_id: str) -> Optional[StandardCustomer]:
        """Get Shopify customer and convert to standard format."""
        try:
            shopify_customer = self.customers_api.get_customer_with_orders(customer_id)
            return self._convert_customer(shopify_customer) if shopify_customer else None
        except Exception as e:
            logger.error(f"Error getting Shopify customer {customer_id}: {e}")
            return None
    
    def _convert_product(self, shopify_product: Dict) -> StandardProduct:
        """Convert Shopify product to StandardProduct - handles None values."""
        variant = shopify_product.get("variants", [{}])[0]
        
        # Safe string conversion - handles None
        def safe_str(value):
            return str(value or "").strip()
        
        # Safe int conversion
        def safe_int(value, default=0):
            try:
                return int(value) if value is not None else default
            except:
                return default
        
        # Safe float conversion
        def safe_float(value, default=None):
            try:
                return float(value) if value is not None else default
            except:
                return default
        
        # Parse tags safely
        tags_str = safe_str(shopify_product.get("tags"))
        tags = [tag.strip() for tag in tags_str.split(",")] if tags_str else []
        
        # Parse dates safely
        def parse_date(date_str):
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else datetime.now()
            except:
                return datetime.now()
        
        return StandardProduct(
            id=str(shopify_product.get("id", "")),
            title=safe_str(shopify_product.get("title")),
            description=safe_str(shopify_product.get("body_html")),
            price=safe_float(variant.get("price"), 0.0),
            compare_at_price=safe_float(variant.get("compare_at_price")),
            sku=safe_str(variant.get("sku")),
            inventory_quantity=sum(safe_int(v.get("inventory_quantity")) for v in shopify_product.get("variants", [])),
            tags=tags,
            categories=[safe_str(shopify_product.get("product_type"))] if shopify_product.get("product_type") else [],
            images=[img["src"] for img in shopify_product.get("images", []) if img.get("src")],
            availability=any(safe_int(v.get("inventory_quantity")) > 0 for v in shopify_product.get("variants", [])),
            created_at=parse_date(shopify_product.get("created_at")),
            updated_at=parse_date(shopify_product.get("updated_at"))
        )
    
    def _convert_customer(self, shopify_customer: Dict) -> StandardCustomer:
        """Convert Shopify customer to StandardCustomer."""
        def safe_str(value):
            return str(value or "").strip()
        
        def parse_date(date_str):
            try:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else datetime.now()
            except:
                return datetime.now()
        
        return StandardCustomer(
            id=str(shopify_customer.get("id", "")),
            first_name=safe_str(shopify_customer.get("first_name")),
            last_name=safe_str(shopify_customer.get("last_name")),
            email=safe_str(shopify_customer.get("email")),
            phone=safe_str(shopify_customer.get("phone")),
            purchase_history=shopify_customer.get("purchase_history", []),
            loyalty_points=shopify_customer.get("loyalty_points", 0),
            preferences={"tags": safe_str(shopify_customer.get("tags")).split(",") if shopify_customer.get("tags") else []},
            created_at=parse_date(shopify_customer.get("created_at")),
            updated_at=parse_date(shopify_customer.get("updated_at"))
        )