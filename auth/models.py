from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime

class ShopifyInstallation(BaseModel):
    """Model for Shopify app installation data"""
    shop: str
    access_token: str
    business_id: str
    created_at: Optional[datetime] = None
    admin_api_url: Optional[str] = None
    agent_url: Optional[str] = None

class ProvisioningRequest(BaseModel):
    """Request model for manual provisioning"""
    business_id: str
    provider: str
    shop_url: str
    access_token: str
    provider_config: Dict[str, str] = {}

class ProvisioningResponse(BaseModel):
    """Response model for provisioning results"""
    status: str
    message: str
    business_id: Optional[str] = None
    admin_api_url: Optional[str] = None
    agent_url: Optional[str] = None
    error: Optional[str] = None

class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback"""
    status: str
    message: str
    business_id: str
    shop: Optional[str] = None

class HealthResponse(BaseModel):
    """Health check response"""
    status: str

class ServiceUrls(BaseModel):
    """Model for service URLs"""
    admin_api_url: str
    agent_url: str