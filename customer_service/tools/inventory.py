"""Inventory-related tools for the customer service agent."""

import logging
from typing import Optional
from ..config import Config
from ..integrations.manager import IntegrationManager

logger = logging.getLogger(__name__)

# Initialize integration manager
config = Config()
integration_manager = IntegrationManager(config)

def check_product_availability(product_id: str, store_id: Optional[str] = None) -> dict:
    """
    Check availability of a specific product.
    
    Args:
        product_id: ID of the product to check
        store_id: Optional store ID (for future multi-store support)
        
    Returns:
        Dictionary with availability information
    """
    logger.info(f"Checking availability for product: {product_id}")
    
    try:
        result = integration_manager.check_inventory(product_id)
        return result
        
    except Exception as e:
        logger.error(f"Error checking product availability: {e}")
        return {"available": False, "error": str(e)}

def get_low_stock_products(threshold: int = 10) -> dict:
    """
    Get products that are low in stock.
    
    Args:
        threshold: Stock quantity threshold for "low stock"
        
    Returns:
        Dictionary with low stock products
    """
    logger.info(f"Getting low stock products with threshold: {threshold}")
    
    try:
        # For now, this is a placeholder since we need to implement
        # bulk inventory checking in the integration layer
        # This would typically query all products and filter by quantity
        
        return {
            "low_stock_products": [],
            "threshold": threshold,
            "message": "Low stock checking not yet implemented"
        }
        
    except Exception as e:
        logger.error(f"Error getting low stock products: {e}")
        return {"low_stock_products": [], "error": str(e)}
