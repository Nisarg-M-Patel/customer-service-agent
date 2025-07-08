# customer_service/agent.py
"""Main agent module for the customer service agent."""

import logging
import warnings
from google.adk import Agent
from .config import Config
from .prompts import GLOBAL_INSTRUCTION, INSTRUCTION

# Import the proper ADK parallel workflow
from .agents.search_agents import coordinated_search_workflow

# Import other existing tools (unchanged)
from .tools.products import get_product_details
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
logger.info("Initializing customer service agent with proper ADK parallel workflow")

# Create the agent with ADK parallel workflow and other tools
root_agent = Agent(
    model=config.agent_settings.model,
    global_instruction=GLOBAL_INSTRUCTION,
    instruction=INSTRUCTION,
    name=config.agent_settings.name,
    sub_agents=[
        # MOVED: ADK parallel workflow goes here, not in tools
        coordinated_search_workflow,
    ],
    tools=[
        # EXISTING: Product tools (kept)
        get_product_details,
        
        # EXISTING: Inventory tools (unchanged)
        check_product_availability,
        get_low_stock_products,
        
        # EXISTING: Customer tools (unchanged)
        get_customer_info,
        get_customer_purchase_history,
        get_customer_recommendations,
        
        # EXISTING: Service tools (unchanged)
        schedule_service_appointment,
        get_available_service_times,
        send_service_instructions,
        generate_service_qr_code,
    ],
)