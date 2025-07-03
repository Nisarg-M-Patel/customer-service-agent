# debug_integration.py
"""Debug script to understand the integration setup"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from customer_service.config import Config
from customer_service.integrations.manager import IntegrationManager

def debug_integration_setup():
    """Debug what providers are actually being used."""
    
    print("🔍 Integration Debug")
    print("=" * 50)
    
    config = Config()
    print(f"INTEGRATION_MODE: {config.INTEGRATION_MODE}")
    print(f"SEARCH_PROVIDER: {config.SEARCH_PROVIDER}")
    
    # Initialize integration manager
    integration_manager = IntegrationManager(config)
    
    print(f"\nProviders initialized: {list(integration_manager._providers.keys())}")
    print(f"Search provider available: {integration_manager._search_provider is not None}")
    
    if integration_manager._search_provider:
        print(f"Search provider type: {type(integration_manager._search_provider).__name__}")
        print(f"Search index: {integration_manager._search_provider.index_name}")
    
    # Test search from different sources
    print("\n🔍 Testing searches:")
    
    # 1. Direct mock provider search
    mock_provider = integration_manager._providers.get("mock")
    if mock_provider:
        mock_results = mock_provider.search_products("tomato")
        print(f"Mock provider search for 'tomato': {len(mock_results)} results")
        if mock_results:
            print(f"   Sample: {mock_results[0].title} (ID: {mock_results[0].id})")
    
    # 2. Direct Elasticsearch search (if available)
    if integration_manager._search_provider:
        es_results = integration_manager._search_provider.search_products("tomato")
        print(f"Elasticsearch search for 'tomato': {len(es_results)} results")
        if es_results:
            print(f"   Sample: {es_results[0].title} (ID: {es_results[0].id})")
    
    # 3. Integration manager search (what the agent actually uses)
    final_results = integration_manager.search_products("tomato")
    print(f"Integration manager search for 'tomato': {len(final_results)} results")
    if final_results:
        print(f"   Sample: {final_results[0].title} (ID: {final_results[0].id})")
    
    print("\n📊 Product ID Analysis:")
    print("Mock IDs start with 'mock-'")
    print("Shopify IDs are usually long numbers")
    print("The IDs in your agent response suggest real Shopify products!")

if __name__ == "__main__":
    debug_integration_setup()