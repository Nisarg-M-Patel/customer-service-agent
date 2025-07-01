# test_config_generator.py
"""Test script to verify LLM Config Generator works with your Shopify store."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from customer_service.config import Config
from customer_service.integrations.manager import IntegrationManager
from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator

def test_config_generation():
    """Test the LLM config generator with real Shopify products."""
    
    print("🧪 Testing LLM Config Generator...")
    
    # Initialize config and integration manager
    config = Config()
    integration_manager = IntegrationManager(config)
    
    # Get sample products from your current provider (mock or Shopify)
    print("\n📦 Fetching sample products...")
    sample_products = integration_manager.search_products()  # Gets all products
    
    if not sample_products:
        print("❌ No products found! Check your integration setup.")
        return
    
    print(f"✅ Found {len(sample_products)} products")
    
    # Show sample product data
    print("\n📋 Sample product preview:")
    for i, product in enumerate(sample_products[:3]):
        print(f"{i+1}. {product.title}")
        print(f"   Categories: {product.categories}")
        print(f"   Tags: {product.tags[:5]}...")  # First 5 tags
    
    # Initialize LLM config generator
    print("\n🤖 Initializing LLM Config Generator...")
    try:
        config_generator = LLMConfigGenerator(config)
        print("✅ LLM client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize LLM client: {e}")
        print("💡 Check your GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION settings")
        return
    
    # Check if config already exists
    if config_generator.config_exists():
        print("\n📄 Existing config found, loading...")
        existing_config = config_generator.load_config()
        
        if existing_config:  # Check if config was actually loaded
            print(f"✅ Loaded config for: {existing_config.get('business_type', 'unknown')}")
            print(f"   Index name: {existing_config.get('index_name')}")
            print(f"   Generated at: {existing_config.get('generated_at')}")
            
            # Ask if user wants to regenerate
            response = input("\n🔄 Regenerate config? (y/n): ").lower()
            if response != 'y':
                print("Using existing config")
                return
        else:
            print("⚠️ Config file exists but couldn't be loaded (empty/corrupted)")
            print("Will generate new config...")
    else:
        print("\n📄 No existing config found, will generate new one...")
    
    # Generate new config
    print("\n🎯 Generating search config with LLM...")
    try:
        search_config = config_generator.generate_config(sample_products)
        
        print("\n🎉 Config generated successfully!")
        print(f"   Business type: {search_config.get('business_type')}")
        print(f"   Index name: {search_config.get('index_name')}")
        print(f"   Searchable fields: {list(search_config.get('searchable_fields', {}).keys())}")
        print(f"   Synonym groups: {len(search_config.get('synonym_groups', []))}")
        
        # Show some synonyms
        synonyms = search_config.get('synonym_groups', [])
        if synonyms:
            print("\n🔗 Sample synonyms:")
            for i, synonym_group in enumerate(synonyms[:3]):
                print(f"   {i+1}. {synonym_group}")
        
        # Show field weights
        fields = search_config.get('searchable_fields', {})
        if fields:
            print("\n⚖️ Field weights:")
            for field, settings in fields.items():
                weight = settings.get('weight', 1.0)
                print(f"   {field}: {weight}x")
        
        print(f"\n💾 Config saved to: {config_generator.config_file_path}")
        
    except Exception as e:
        print(f"❌ Failed to generate config: {e}")
        print("💡 Check your Vertex AI setup and API permissions")
        return

def test_config_loading():
    """Test loading existing config."""
    
    print("\n🔍 Testing config loading...")
    
    config = Config()
    config_generator = LLMConfigGenerator(config)
    
    if config_generator.config_exists():
        config_data = config_generator.load_config()
        if config_data:
            print("✅ Config loaded successfully")
            print(f"   Business type: {config_data.get('business_type', 'unknown')}")
            print(f"   File exists at: {config_generator.config_file_path}")
        else:
            print("⚠️ Config file exists but is empty/corrupted")
            print(f"   File path: {config_generator.config_file_path}")
    else:
        print("ℹ️ No config file exists yet")

if __name__ == "__main__":
    print("🚀 LLM Config Generator Test")
    print("=" * 50)
    
    # Test config loading first
    test_config_loading()
    
    # Test config generation
    test_config_generation()
    
    print("\n✨ Test complete!")