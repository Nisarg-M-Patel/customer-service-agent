"""Service-related tools for the customer service agent."""

import logging
from typing import Optional
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger(__name__)

def schedule_service_appointment(customer_id: str, service_type: str, 
                               date: str, time_range: str, details: str = "") -> dict:
    """
    Schedule a service appointment.
    
    Args:
        customer_id: Customer identifier
        service_type: Type of service (e.g., "planting", "consultation")
        date: Desired date (YYYY-MM-DD)
        time_range: Time range (e.g., "9-12", "14-17")
        details: Additional details
        
    Returns:
        Dictionary with appointment confirmation
    """
    logger.info(f"Scheduling {service_type} service for customer {customer_id} on {date}")
    
    try:
        # Generate appointment ID
        appointment_id = str(uuid.uuid4())
        
        # Calculate confirmation time
        start_time = time_range.split("-")[0]
        confirmation_time = f"{date} {start_time}:00"
        
        return {
            "status": "success",
            "appointment_id": appointment_id,
            "customer_id": customer_id,
            "service_type": service_type,
            "date": date,
            "time_range": time_range,
            "details": details,
            "confirmation_time": confirmation_time,
            "message": f"Appointment scheduled for {date} from {time_range}"
        }
        
    except Exception as e:
        logger.error(f"Error scheduling appointment: {e}")
        return {"status": "error", "message": str(e)}

def get_available_service_times(date: str, service_type: Optional[str] = None) -> dict:
    """
    Get available service time slots for a date.
    
    Args:
        date: Date to check (YYYY-MM-DD)
        service_type: Optional service type filter
        
    Returns:
        Dictionary with available time slots
    """
    logger.info(f"Getting available service times for {date}")
    
    try:
        # Mock available time slots
        available_times = ["9-12", "13-16", "16-19"]
        
        return {
            "date": date,
            "service_type": service_type,
            "available_times": available_times,
            "message": f"Available time slots for {date}"
        }
        
    except Exception as e:
        logger.error(f"Error getting available times: {e}")
        return {"available_times": [], "error": str(e)}

def send_service_instructions(customer_id: str, service_type: str, 
                            delivery_method: str = "email") -> dict:
    """
    Send service instructions to customer.
    
    Args:
        customer_id: Customer identifier
        service_type: Type of service
        delivery_method: How to send instructions ("email" or "sms")
        
    Returns:
        Dictionary with send status
    """
    logger.info(f"Sending {service_type} instructions to customer {customer_id} via {delivery_method}")
    
    try:
        return {
            "status": "success",
            "customer_id": customer_id,
            "service_type": service_type,
            "delivery_method": delivery_method,
            "message": f"Instructions for {service_type} sent via {delivery_method}"
        }
        
    except Exception as e:
        logger.error(f"Error sending instructions: {e}")
        return {"status": "error", "message": str(e)}

def generate_service_qr_code(customer_id: str, discount_value: float, 
                           discount_type: str = "percentage", 
                           expiration_days: int = 30) -> dict:
    """
    Generate QR code for service discount.
    
    Args:
        customer_id: Customer identifier
        discount_value: Discount amount
        discount_type: "percentage" or "fixed"
        expiration_days: Days until expiration
        
    Returns:
        Dictionary with QR code information
    """
    logger.info(f"Generating QR code for customer {customer_id}: {discount_value} {discount_type}")
    
    try:
        # Basic validation
        if discount_type == "percentage" and discount_value > 50:
            return {"status": "error", "message": "Percentage discount cannot exceed 50%"}
        if discount_type == "fixed" and discount_value > 100:
            return {"status": "error", "message": "Fixed discount cannot exceed $100"}
        
        # Calculate expiration date
        expiration_date = (datetime.now() + timedelta(days=expiration_days)).strftime("%Y-%m-%d")
        
        return {
            "status": "success",
            "customer_id": customer_id,
            "discount_value": discount_value,
            "discount_type": discount_type,
            "expiration_date": expiration_date,
            "qr_code_data": f"DISCOUNT_{customer_id}_{discount_value}_{discount_type}",
            "message": f"{discount_value}{'%' if discount_type == 'percentage' else '$'} discount QR code generated"
        }
        
    except Exception as e:
        logger.error(f"Error generating QR code: {e}")
        return {"status": "error", "message": str(e)}
