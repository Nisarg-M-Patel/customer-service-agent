import os
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AgentModel(BaseModel):
    """Agent model settings."""
    name: str = Field(default="customer_service_agent")
    model: str = Field(default="gemini-2.0-flash-exp")

class Config(BaseSettings):
    """Configuration settings for the customer service agent."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GOOGLE_",
        case_sensitive=True,
        env_file_encoding='utf-8',
        extra='ignore'
    )
    
    agent_settings: AgentModel = Field(default=AgentModel())
    app_name: str = "customer_service_app"
    CLOUD_PROJECT: str = Field(default="my_project")
    CLOUD_LOCATION: str = Field(default="us-central1")
    GENAI_USE_VERTEXAI: str = Field(default="1")
    API_KEY: str | None = Field(default="")
    
    # Integration settings (will be used when we add real integrations)
    INTEGRATION_MODE: str = Field(default="mock")  # "mock" or "live"
    DATABASE_URL: str = Field(default="sqlite:///customer_service.db")