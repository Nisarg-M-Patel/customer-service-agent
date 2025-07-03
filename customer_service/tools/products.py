"""Product-related tools for the customer service agent."""

import logging
from typing import Optional
from ..integrations.manager import IntegrationManager

logger = logging.getLogger(__name__)

def get_product_recommendations(query: str, customer_id: str) -> dict:
    """
    Get product recommendations based on search query.
    
    Args:
        query: Search query for products customer is interested in
        customer_id: Customer ID for personalization
        
    Returns:
        Dictionary with product recommendations
    """
    logger.info(f"Getting recommendations for query: {query}, customer: {customer_id}")
    
    try:
        # Get singleton integration manager instance
        integration_manager = IntegrationManager.get_instance()
        
        # Search for products related to the query
        products = integration_manager.search_products(query=query)
        
        # Format recommendations
        recommendations = []
        for product in products[:5]:  # Top 5 recommendations
            recommendations.append({
                "product_id": product.id,
                "name": product.title,
                "description": product.description,
                "price": product.price,
                "availability": product.availability,
                "image": product.images[0] if product.images else None
            })
        
        return {"recommendations": recommendations}
        
    except Exception as e:
        logger.error(f"Error getting product recommendations: {e}")
        return {"recommendations": [], "error": str(e)}

def search_products(query: str, category: Optional[str]=None) -> dict:
    """
    Search for products by query and optional category.
    
    Args:
        query: Search query
        category: Optional category filter
        
    Returns:
        Dictionary with search results
    """
    logger.info(f"Searching products: query='{query}', category='{category}'")
    
    try:
        # Get singleton integration manager instance
        integration_manager = IntegrationManager.get_instance()
        
        products = integration_manager.search_products(query=query, category=category)
        
        results = []
        for product in products:
            results.append({
                "product_id": product.id,
                "name": product.title,
                "description": product.description,
                "price": product.price,
                "sku": product.sku,
                "availability": product.availability,
                "tags": product.tags
            })
        
        return {
            "results": results,
            "total": len(results),
            "query": query,
            "category": category
        }
        
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        return {"results": [], "error": str(e)}

def get_product_details(product_id: str) -> dict:
    """
    Get detailed information about a specific product.
    
    Args:
        product_id: ID of the product
        
    Returns:
        Dictionary with product details
    """
    logger.info(f"Getting product details for: {product_id}")
    
    try:
        # Get singleton integration manager instance
        integration_manager = IntegrationManager.get_instance()
        
        product = integration_manager.get_product_by_id(product_id)
        
        if not product:
            return {"error": f"Product {product_id} not found"}
        
        return {
            "product_id": product.id,
            "name": product.title,
            "description": product.description,
            "price": product.price,
            "compare_at_price": product.compare_at_price,
            "sku": product.sku,
            "inventory_quantity": product.inventory_quantity,
            "availability": product.availability,
            "tags": product.tags,
            "categories": product.categories,
            "images": product.images
        }
        
    except Exception as e:
        logger.error(f"Error getting product details: {e}")
        return {"error": str(e)}