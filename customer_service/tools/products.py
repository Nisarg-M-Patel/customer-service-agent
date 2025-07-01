"""Product-related tools for the customer service agent."""

import logging
from typing import Optional
from ..config import Config
from ..integrations.manager import IntegrationManager

logger = logging.getLogger(__name__)

# Initialize integration manager
config = Config()
integration_manager = IntegrationManager(config)

def get_product_recommendations(plant_type: str, customer_id: str) -> dict:
    """
    Get product recommendations based on plant type.
    
    Args:
        plant_type: Type of plant customer is interested in
        customer_id: Customer ID for personalization
        
    Returns:
        Dictionary with product recommendations
    """
    logger.info(f"Getting recommendations for plant type: {plant_type}, customer: {customer_id}")
    
    try:
        # Search for products related to the plant type
        products = integration_manager.search_products(query=plant_type)
        
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

def search_products(query: str, category: Optional[str] = None, intent_mode: bool = True) -> dict:
    """
    Search for products by query and optional category, with optional intent analysis.
    
    Args:
        query: Search query
        category: Optional category filter
        intent_mode: Whether to use intent-based search (default: True)
        
    Returns:
        Dictionary with search results including confidence metadata for intent searches
    """
    logger.info(f"Searching products: query='{query}', category='{category}', intent_mode={intent_mode}")
    
    try:
        # Use intent search if enabled, otherwise fall back to keyword search
        if intent_mode:
            enhanced_results = integration_manager.search_products_with_intent(
                query=query, 
                category=category, 
                intent_mode=True
            )
            
            # Handle enhanced results with metadata
            if enhanced_results and isinstance(enhanced_results[0], dict) and "product" in enhanced_results[0]:
                formatted_results = []
                for item in enhanced_results:
                    product = item["product"]
                    result = {
                        "product_id": product.id,
                        "name": product.title,
                        "description": product.description,
                        "price": product.price,
                        "sku": product.sku,
                        "availability": product.availability,
                        "tags": product.tags
                    }
                    
                    # Add intent search metadata if available
                    if item.get("confidence_score") is not None:
                        result["confidence_score"] = round(item["confidence_score"], 2)
                        result["match_reasons"] = item.get("match_reasons", [])
                    
                    formatted_results.append(result)
                
                return {
                    "results": formatted_results,
                    "total": len(formatted_results),
                    "query": query,
                    "category": category,
                    "search_mode": "intent"
                }
        
        # Fallback to keyword-only search
        products = integration_manager.search_products(query=query, category=category)
        
        # Format regular products
        results = []
        for product in products:
            result = {
                "product_id": product.id,
                "name": product.title,
                "description": product.description,
                "price": product.price,
                "sku": product.sku,
                "availability": product.availability,
                "tags": product.tags
            }
            results.append(result)
        
        return {
            "results": results,
            "total": len(results),
            "query": query,
            "category": category,
            "search_mode": "keyword"
        }
        
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        return {"results": [], "error": str(e), "search_mode": "error"}

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
