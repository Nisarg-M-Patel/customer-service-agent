"""Data models for the customer service agent."""

from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field

class StandardProduct(BaseModel):
    """Universal product model that all integrations map to."""
    id: str
    title: str
    description: str
    price: float
    compare_at_price: Optional[float] = None
    sku: Optional[str] = None
    inventory_quantity: int = 0
    tags: List[str] = []
    categories: List[str] = []
    images: List[str] = []
    availability: bool = True
    created_at: datetime
    updated_at: datetime

class StandardCustomer(BaseModel):
    """Universal customer model that all integrations map to."""
    id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    purchase_history: List[Dict] = []
    loyalty_points: int = 0
    preferences: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

class StoreConfiguration(BaseModel):
    """Store configuration for integrations."""
    store_id: str
    store_name: str
    product_integration: str = "mock"  # "shopify", "woocommerce", etc.
    customer_integration: str = "mock"  # "salesforce", "hubspot", etc.
    integration_config: Dict[str, Any] = {}
    created_at: datetime