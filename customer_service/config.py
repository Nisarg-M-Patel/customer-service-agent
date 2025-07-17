# customer_service/config.py
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
        env_prefix="",
        case_sensitive=True,
        env_file_encoding='utf-8',
        extra='ignore'
    )
    
    agent_settings: AgentModel = Field(default=AgentModel())
    app_name: str = "customer_service_app"
    CLOUD_PROJECT: str = Field(default="elite-coral-463917-b1", alias="GOOGLE_CLOUD_PROJECT")
    CLOUD_LOCATION: str = Field(default="us-central1", alias="GOOGLE_CLOUD_LOCATION") 
    GENAI_USE_VERTEXAI: str = Field(default="1", alias="GOOGLE_GENAI_USE_VERTEXAI")
    API_KEY: str | None = Field(default="", alias="GOOGLE_API_KEY")
        
    # Integration settings
    INTEGRATION_MODE: str = Field(default="mock")  # "mock", "elasticsearch", "shopify"
    DATABASE_URL: str = Field(default="sqlite:///customer_service.db")
    
    # Elasticsearch settings
    ELASTICSEARCH_URL: str = Field(default="http://34.63.210.51:9200")
    ELASTICSEARCH_USER: str | None = Field(default="elastic")
    ELASTICSEARCH_PASSWORD: str | None = Field(default="elastic-mvp-2024")
    ELASTICSEARCH_VERIFY_CERTS: bool = Field(default=True)
    BUSINESS_ID: str = Field(...)
    
    # Shopify settings (for syncing data to Elasticsearch)
    SHOPIFY_SHOP_URL: str | None = Field(default=None)
    SHOPIFY_ACCESS_TOKEN: str | None = Field(default=None)
    
    # Search configuration
    SEARCH_PROVIDER: str = Field(default="elasticsearch")  # "mock", "elasticsearch", "shopify"
    ENABLE_SEARCH_SUGGESTIONS: bool = Field(default=True)
    MAX_SEARCH_RESULTS: int = Field(default=20)

    # OpenAI settings
    OPENAI_API_KEY: str | None = Field(default=None)
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-large")
    EMBEDDING_DIMENSIONS: int = Field(default=1536)  # Reduced from 3072