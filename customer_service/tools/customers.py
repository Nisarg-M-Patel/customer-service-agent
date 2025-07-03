"""Customer-related tools for the customer service agent."""

import logging
from typing import Dict, Optional
from ..config import Config
from ..integrations.manager import IntegrationManager

logger = logging.getLogger(__name__)

# Initialize integration manager
config = Config()
integration_manager = IntegrationManager.get_instance()

def get_customer_info(customer_id: str) -> dict:
    """
    Get customer information by ID.
    
    Args:
        customer_id: Customer identifier
        
    Returns:
        Dictionary with customer information
    """
    logger.info(f"Getting customer info for: {customer_id}")
    
    try:
        customer = integration_manager.get_customer_by_id(customer_id)
        
        if not customer:
            return {"error": f"Customer {customer_id} not found"}
        
        return {
            "customer_id": customer.id,
            "name": f"{customer.first_name} {customer.last_name}",
            "email": customer.email,
            "phone": customer.phone,
            "loyalty_points": customer.loyalty_points,
            "preferences": customer.preferences,
            "purchase_history": customer.purchase_history
        }
        
    except Exception as e:
        logger.error(f"Error getting customer info: {e}")
        return {"error": str(e)}

def get_customer_purchase_history(customer_id: str) -> dict:
    """
    Get customer's purchase history.
    
    Args:
        customer_id: Customer identifier
        
    Returns:
        Dictionary with purchase history
    """
    logger.info(f"Getting purchase history for customer: {customer_id}")
    
    try:
        customer = integration_manager.get_customer_by_id(customer_id)
        
        if not customer:
            return {"error": f"Customer {customer_id} not found"}
        
        return {
            "customer_id": customer.id,
            "purchase_history": customer.purchase_history,
            "total_purchases": len(customer.purchase_history)
        }
        
    except Exception as e:
        logger.error(f"Error getting purchase history: {e}")
        return {"error": str(e)}

def get_customer_recommendations(customer_id: str) -> dict:
    """
    Get personalized product recommendations for a customer.
    
    Args:
        customer_id: Customer identifier
        
    Returns:
        Dictionary with personalized recommendations
    """
    logger.info(f"Getting personalized recommendations for customer: {customer_id}")
    
    try:
        customer = integration_manager.get_customer_by_id(customer_id)
        
        if not customer:
            return {"error": f"Customer {customer_id} not found"}
        
        # Use customer preferences to search for relevant products
        interests = customer.preferences.get("interests", [])
        
        if interests:
            # Search for products matching customer interests
            products = integration_manager.search_products(query=" ".join(interests))
            
            recommendations = []
            for product in products[:3]:  # Top 3 personalized recommendations
                recommendations.append({
                    "product_id": product.id,
                    "name": product.title,
                    "price": product.price,
                    "reason": f"Based on your interest in {', '.join(interests)}"
                })
            
            return {"recommendations": recommendations}
        else:
            return {"recommendations": [], "message": "No customer preferences available"}
        
    except Exception as e:
        logger.error(f"Error getting customer recommendations: {e}")
        return {"recommendations": [], "error": str(e)}