"""Main agent module for the customer service agent."""

import logging
import warnings
from google.adk import Agent
from .config import Config
from .prompts import GLOBAL_INSTRUCTION, INSTRUCTION
from .tools.products import get_product_recommendations, search_products, get_product_details
from .tools.inventory import check_product_availability, get_low_stock_products
from .tools.customers import get_customer_info, get_customer_purchase_history, get_customer_recommendations
from .tools.services import (
    schedule_service_appointment, 
    get_available_service_times, 
    send_service_instructions,
    generate_service_qr_code
)

warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")

config = Config()
logger = logging.getLogger(__name__)

# Create the agent with all tools
root_agent = Agent(
    model=config.agent_settings.model,
    global_instruction=GLOBAL_INSTRUCTION,
    instruction=INSTRUCTION,
    name=config.agent_settings.name,
    tools=[
        # Product tools
        get_product_recommendations,
        search_products,
        get_product_details,
        
        # Inventory tools
        check_product_availability,
        get_low_stock_products,
        
        # Customer tools
        get_customer_info,
        get_customer_purchase_history,
        get_customer_recommendations,
        
        # Service tools
        schedule_service_appointment,
        get_available_service_times,
        send_service_instructions,
        generate_service_qr_code,
    ],
)