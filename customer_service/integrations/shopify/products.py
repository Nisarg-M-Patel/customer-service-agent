import requests
import logging
from typing import List, Optional
from datetime import datetime
from ...database.models import StandardProduct
from .auth import ShopifyAuth

logger = logging.getLogger(__name__)

class ShopifyProducts:
    def __init__(self, auth: ShopifyAuth):
        self.auth = auth
    
    def get_products(self, limit: int = 50) -> List[StandardProduct]:
        """Get products from Shopify."""
        try:
            response = requests.get(
                f"{self.auth.base_url}/products.json",
                headers=self.auth.get_headers(),
                params={"limit": limit},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Shopify API error: {response.status_code}")
                return []
            
            data = response.json()
            products = []
            
            for product_data in data.get("products", []):
                product = self._convert_to_standard(product_data)
                if product:
                    products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            return []
    
    def search_products(self, query: str) -> List[StandardProduct]:
        """Search products by title, description, and tags."""
        try:
            # Get all products and filter locally since Shopify's title search is exact match only
            response = requests.get(
                f"{self.auth.base_url}/products.json",
                headers=self.auth.get_headers(),
                params={"limit": 50},
                timeout=30
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            products = []
            
            for product_data in data.get("products", []):
                product = self._convert_to_standard(product_data)
                if product:
                    products.append(product)
            
            # If no query, return all products
            if not query:
                return products
            
            # Filter products by query (case-insensitive partial match)
            query_lower = query.lower()
            filtered_products = []
            
            for product in products:
                if (query_lower in product.title.lower() or
                    query_lower in product.description.lower() or
                    any(query_lower in tag.lower() for tag in product.tags)):
                    filtered_products.append(product)
            
            return filtered_products
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get a specific product by ID."""
        try:
            response = requests.get(
                f"{self.auth.base_url}/products/{product_id}.json",
                headers=self.auth.get_headers(),
                timeout=30
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            return self._convert_to_standard(data.get("product"))
            
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None
    
    def _convert_to_standard(self, shopify_product: dict) -> Optional[StandardProduct]:
        """Convert Shopify product to StandardProduct."""
        try:
            # Get first variant for pricing/inventory
            variants = shopify_product.get("variants", [])
            first_variant = variants[0] if variants else {}
            
            # Get images
            images = [img["src"] for img in shopify_product.get("images", [])]
            
            return StandardProduct(
                id=str(shopify_product["id"]),
                title=shopify_product["title"],
                description=shopify_product.get("body_html", "").strip(),
                price=float(first_variant.get("price", 0)),
                compare_at_price=float(first_variant.get("compare_at_price", 0)) if first_variant.get("compare_at_price") else None,
                sku=first_variant.get("sku", ""),
                inventory_quantity=first_variant.get("inventory_quantity", 0),
                tags=shopify_product.get("tags", "").split(",") if shopify_product.get("tags") else [],
                categories=[shopify_product.get("product_type", "")],
                images=images,
                availability=shopify_product.get("status") == "active",
                created_at=datetime.fromisoformat(shopify_product["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(shopify_product["updated_at"].replace("Z", "+00:00"))
            )
        except Exception as e:
            logger.error(f"Error converting product: {e}")
            return None