"""Shopify customers API integration."""

import logging
from typing import List, Dict, Optional
from .auth import ShopifyAuth

logger = logging.getLogger(__name__)

class ShopifyCustomers:
    """Handles Shopify Customers API operations."""
    
    def __init__(self, auth: ShopifyAuth):
        self.auth = auth
    
    def get_by_id(self, customer_id: str) -> Optional[Dict]:
        """Get customer by ID."""
        try:
            response = self.auth.make_request(f"customers/{customer_id}.json")
            return response.get("customer")
        except Exception as e:
            logger.error(f"Error getting Shopify customer {customer_id}: {e}")
            return None
    
    def get_customer_with_orders(self, customer_id: str) -> Dict:
        """Get customer data with order history."""
        try:
            customer = self.get_by_id(customer_id)
            if not customer:
                return {}
            
            # Get orders for this customer
            try:
                params = {"customer_id": customer_id, "limit": 50}
                response = self.auth.make_request("orders.json", params=params)
                orders = response.get("orders", [])
                
                # Convert to purchase history format
                purchase_history = []
                total_spent = 0
                
                for order in orders:
                    order_total = float(order.get("total_price", 0))
                    total_spent += order_total
                    
                    purchase_history.append({
                        "date": order.get("created_at", "").split("T")[0],
                        "total": order_total,
                        "order_id": order.get("id"),
                        "items": [item.get("product_id") for item in order.get("line_items", [])]
                    })
                
                customer["purchase_history"] = purchase_history
                customer["loyalty_points"] = int(total_spent)
                
            except Exception as e:
                logger.error(f"Error getting orders for customer {customer_id}: {e}")
                customer["purchase_history"] = []
                customer["loyalty_points"] = 0
            
            return customer
            
        except Exception as e:
            logger.error(f"Error getting enriched customer data {customer_id}: {e}")
            return {}