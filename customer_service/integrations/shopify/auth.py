import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ShopifyAuth:
    def __init__(self, shop_domain: str, access_token: str):
        """
        Initialize Shopify auth.
        
        Args:
            shop_domain: The original myshopify.com subdomain (e.g., 'my-store' or 'my-store.myshopify.com')
                        This is NOT the custom domain - use the original Shopify subdomain
            access_token: Private app access token
        """
        # Clean domain - remove .myshopify.com if present
        self.shop_domain = shop_domain.replace('.myshopify.com', '')
        self.access_token = access_token
        # API always uses the .myshopify.com domain
        self.base_url = f"https://{self.shop_domain}.myshopify.com/admin/api/2024-01"
        
    def get_headers(self) -> dict:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }
    
    def test_connection(self) -> bool:
        """Test if the auth credentials work."""
        try:
            response = requests.get(
                f"{self.base_url}/shop.json",
                headers=self.get_headers(),
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Auth test failed: {e}")
            return False