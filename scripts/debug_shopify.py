# debug_shopify.py
"""Debug Shopify provider configuration and connection"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from customer_service.config import Config

def debug_shopify_config():
    """Check if Shopify is properly configured."""
    
    print("🛍️ Shopify Configuration Debug")
    print("=" * 50)
    
    config = Config()
    
    # Check configuration values
    print("Configuration values:")
    print(f"INTEGRATION_MODE: {config.INTEGRATION_MODE}")
    print(f"SEARCH_PROVIDER: {config.SEARCH_PROVIDER}")
    
    # Check Shopify-specific settings
    shopify_url = getattr(config, 'SHOPIFY_SHOP_URL', None)
    shopify_token = getattr(config, 'SHOPIFY_ACCESS_TOKEN', None)
    
    print(f"SHOPIFY_SHOP_URL: {shopify_url}")
    print(f"SHOPIFY_ACCESS_TOKEN: {'***' + shopify_token[-4:] if shopify_token else None}")
    
    if not shopify_url or not shopify_token:
        print("\n❌ PROBLEM FOUND: Missing Shopify credentials!")
        print("You need to set these in your .env file:")
        print("SHOPIFY_SHOP_URL=your-store.myshopify.com")
        print("SHOPIFY_ACCESS_TOKEN=your_access_token")
        return False
    
    # Test Shopify connection
    print(f"\n🔌 Testing Shopify connection...")
    try:
        from customer_service.integrations.shopify.provider import ShopifyProvider
        
        shopify_provider = ShopifyProvider(shopify_url, shopify_token)
        
        # Test basic connection
        if shopify_provider.auth.test_connection():
            print("✅ Shopify connection successful!")
            
            # Test product fetch
            print("📦 Testing product fetch...")
            products = shopify_provider.search_products(limit=5)
            print(f"✅ Found {len(products)} products in Shopify")
            
            if products:
                sample = products[0]
                print(f"Sample product: {sample.title} (ID: {sample.id})")
                print(f"Price: ${sample.price}")
                print(f"Tags: {sample.tags[:3]}...")
                
            return True
        else:
            print("❌ Shopify connection failed!")
            print("Check your shop URL and access token")
            return False
            
    except ImportError:
        print("❌ Shopify provider not available (missing dependencies?)")
        return False
    except Exception as e:
        print(f"❌ Shopify test failed: {e}")
        return False

def debug_integration_manager_shopify():
    """Test how IntegrationManager handles Shopify."""
    
    print("\n🔗 Integration Manager Shopify Debug")
    print("=" * 50)
    
    try:
        from customer_service.integrations.manager import IntegrationManager
        
        config = Config()
        integration_manager = IntegrationManager(config)
        
        print("Available providers:")
        for name, provider in integration_manager._providers.items():
            print(f"  {name}: {type(provider).__name__}")
        
        # Check if Shopify provider was initialized
        if "shopify" in integration_manager._providers:
            print("✅ Shopify provider found in IntegrationManager")
            
            # Test direct Shopify search
            shopify_provider = integration_manager._providers["shopify"]
            products = shopify_provider.search_products("tomato", limit=3)
            print(f"Direct Shopify search for 'tomato': {len(products)} results")
            
            if products:
                for i, product in enumerate(products):
                    print(f"  {i+1}. {product.title} (ID: {product.id})")
        else:
            print("❌ Shopify provider NOT found in IntegrationManager")
            print("This explains why it's falling back to MockProvider!")
            
            # Check why Shopify wasn't initialized
            config = Config()
            shopify_url = getattr(config, 'SHOPIFY_SHOP_URL', None)
            
            if not shopify_url:
                print("Reason: SHOPIFY_SHOP_URL not configured")
            else:
                print("Reason: Unknown - check IntegrationManager initialization")
        
        # Test primary provider
        primary_provider = integration_manager._get_primary_provider()
        print(f"Primary provider: {type(primary_provider).__name__}")
        
    except Exception as e:
        print(f"❌ Integration manager debug failed: {e}")

def check_env_file():
    """Check .env file for Shopify settings."""
    
    print("\n📁 .env File Check")
    print("=" * 50)
    
    env_path = ".env"
    if os.path.exists(env_path):
        print("✅ .env file exists")
        
        with open(env_path, 'r') as f:
            content = f.read()
            
        shopify_lines = [line for line in content.split('\n') if 'SHOPIFY' in line]
        
        if shopify_lines:
            print("Shopify-related lines in .env:")
            for line in shopify_lines:
                if 'TOKEN' in line:
                    # Hide token value
                    parts = line.split('=')
                    if len(parts) > 1:
                        print(f"{parts[0]}=***{parts[1][-4:] if len(parts[1]) > 4 else '***'}")
                    else:
                        print(line)
                else:
                    print(line)
        else:
            print("❌ No Shopify configuration found in .env file!")
            print("Add these lines to your .env file:")
            print("SHOPIFY_SHOP_URL=your-store.myshopify.com")
            print("SHOPIFY_ACCESS_TOKEN=your_access_token")
    else:
        print("❌ .env file not found!")
        print("Create a .env file with your Shopify credentials")

if __name__ == "__main__":
    # Run all debug checks
    check_env_file()
    
    shopify_ok = debug_shopify_config()
    
    debug_integration_manager_shopify()
    
    print("\n🎯 Summary")
    print("=" * 50)
    if shopify_ok:
        print("✅ Shopify is configured and working")
        print("The issue is likely in IntegrationManager initialization")
    else:
        print("❌ Shopify configuration is the problem")
        print("Fix your .env file with proper Shopify credentials")