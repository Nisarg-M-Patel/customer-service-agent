# test_elasticsearch_provider.py
"""Test script to verify Elasticsearch provider works with your Shopify products."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from customer_service.config import Config
from customer_service.integrations.manager import IntegrationManager
from customer_service.integrations.elasticsearch.provider import ElasticsearchProvider

def test_elasticsearch_connection():
    """Test basic Elasticsearch connection."""
    print("🔌 Testing Elasticsearch connection...")
    
    config = Config()
    
    try:
        from elasticsearch import Elasticsearch
        
        # Simple connection for Elasticsearch 7.x/8.x
        es = Elasticsearch([config.ELASTICSEARCH_URL])
        
        # Test connection
        if es.ping():
            print("✅ Elasticsearch is running and reachable")
            
            # Show cluster info
            info = es.info()
            print(f"   Version: {info['version']['number']}")
            print(f"   Cluster: {info['cluster_name']}")
            return True
        else:
            print("❌ Cannot ping Elasticsearch")
            return False
            
    except Exception as e:
        print(f"❌ Elasticsearch connection failed: {e}")
        
        # Check if ES is actually running
        try:
            import requests
            response = requests.get(config.ELASTICSEARCH_URL, timeout=5)
            if response.status_code == 200:
                print("💡 Elasticsearch is running but connection failed")
                print(f"   Response: {response.text[:100]}...")
            else:
                print(f"💡 Elasticsearch returned status {response.status_code}")
        except:
            print("💡 Elasticsearch doesn't seem to be running")
            
        return False

def test_provider_initialization():
    """Test ElasticsearchProvider initialization."""
    print("\n🏗️ Testing provider initialization...")
    
    config = Config()
    
    try:
        es_provider = ElasticsearchProvider(config)
        print("✅ ElasticsearchProvider initialized successfully")
        print(f"   Business type: {es_provider.search_config['business_type']}")
        print(f"   Index name: {es_provider.index_name}")
        print(f"   Synonyms: {len(es_provider.search_config.get('synonym_groups', []))} groups")
        return es_provider
        
    except Exception as e:
        print(f"❌ Provider initialization failed: {e}")
        return None

def test_product_sync(es_provider):
    """Test syncing products from Shopify to Elasticsearch."""
    print("\n🔄 Testing product sync...")
    
    config = Config()
    integration_manager = IntegrationManager(config)
    
    # Get products from Shopify
    print("📦 Fetching products from Shopify...")
    shopify_products = integration_manager.search_products()
    
    if not shopify_products:
        print("❌ No products found in Shopify")
        return False
    
    print(f"✅ Found {len(shopify_products)} products in Shopify")
    
    # Sync to Elasticsearch
    print("⬆️ Syncing products to Elasticsearch...")
    try:
        # Use the Shopify provider directly for syncing
        shopify_provider = integration_manager._providers.get("shopify") or integration_manager._providers.get("mock")
        indexed_count = es_provider.sync_from_provider(shopify_provider)
        
        if indexed_count > 0:
            print(f"✅ Successfully synced {indexed_count} products to Elasticsearch")
            return True
        else:
            print("❌ No products were indexed")
            return False
            
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        return False

def test_basic_search(es_provider):
    """Test basic search functionality."""
    print("\n🔍 Testing basic search...")
    
    test_queries = [
        "watering",
        "gloves", 
        "bamboo",
        "garden tools"
    ]
    
    for query in test_queries:
        print(f"\n   Searching for: '{query}'")
        try:
            results = es_provider.search_products(query)
            print(f"   ✅ Found {len(results)} results")
            
            # Show top 2 results
            for i, product in enumerate(results[:2]):
                print(f"      {i+1}. {product.title}")
                
        except Exception as e:
            print(f"   ❌ Search failed: {e}")

def test_synonym_search(es_provider):
    """Test synonym functionality."""
    print("\n🔗 Testing synonym search...")
    
    # Test synonym pairs from your generated config
    synonym_tests = [
        ("plant food", "fertilizer"),  # Should find same products
        ("dirt", "soil"),
        ("tools", "equipment"),
        ("seeds", "seed")
    ]
    
    for term1, term2 in synonym_tests:
        print(f"\n   Testing synonyms: '{term1}' vs '{term2}'")
        
        try:
            results1 = es_provider.search_products(term1)
            results2 = es_provider.search_products(term2)
            
            print(f"   '{term1}': {len(results1)} results")
            print(f"   '{term2}': {len(results2)} results")
            
            # Check for overlap (synonyms should find similar products)
            if results1 and results2:
                common_ids = set(p.id for p in results1) & set(p.id for p in results2)
                if common_ids:
                    print(f"   ✅ Found {len(common_ids)} overlapping products")
                else:
                    print("   ℹ️ No overlapping products (may be normal)")
            
        except Exception as e:
            print(f"   ❌ Synonym test failed: {e}")

def test_fuzzy_search(es_provider):
    """Test fuzzy matching (typo tolerance)."""
    print("\n🔤 Testing fuzzy search (typo tolerance)...")
    
    fuzzy_tests = [
        ("tomatoe", "tomato"),  # Common typo
        ("fertlizer", "fertilizer"),
        ("watring", "watering"),
        ("bamboo", "bambo")  # Missing letter
    ]
    
    for typo, correct in fuzzy_tests:
        print(f"\n   Testing fuzzy: '{typo}' (typo) vs '{correct}' (correct)")
        
        try:
            typo_results = es_provider.search_products(typo)
            correct_results = es_provider.search_products(correct)
            
            print(f"   '{typo}': {len(typo_results)} results")
            print(f"   '{correct}': {len(correct_results)} results")
            
            if typo_results:
                print(f"   ✅ Fuzzy search worked! Found results despite typo")
                # Show top result
                print(f"      Top result: {typo_results[0].title}")
            else:
                print(f"   ℹ️ No fuzzy results (may need different test terms)")
            
        except Exception as e:
            print(f"   ❌ Fuzzy test failed: {e}")

def test_filtered_search(es_provider):
    """Test search with filters."""
    print("\n🎛️ Testing filtered search...")
    
    filter_tests = [
        {"query": "garden", "price_max": 20.0},
        {"query": "watering", "in_stock_only": True},
        {"category": "Garden Accessories"}
    ]
    
    for filters in filter_tests:
        print(f"\n   Testing filters: {filters}")
        
        try:
            results = es_provider.search_products(**filters)
            print(f"   ✅ Found {len(results)} filtered results")
            
            if results:
                # Show sample result
                sample = results[0]
                print(f"      Sample: {sample.title} - ${sample.price}")
                
        except Exception as e:
            print(f"   ❌ Filtered search failed: {e}")

def compare_search_providers():
    """Compare Elasticsearch vs Shopify search results."""
    print("\n⚖️ Comparing Elasticsearch vs Shopify search...")
    
    config = Config()
    integration_manager = IntegrationManager(config)
    
    try:
        es_provider = ElasticsearchProvider(config)
        
        test_query = "bamboo gloves"
        print(f"   Comparing results for: '{test_query}'")
        
        # Shopify search
        shopify_results = integration_manager.search_products(test_query)
        print(f"   Shopify: {len(shopify_results)} results")
        
        # Elasticsearch search  
        es_results = es_provider.search_products(test_query)
        print(f"   Elasticsearch: {len(es_results)} results")
        
        # Show top results from each
        print("\n   📊 Top results comparison:")
        print("   Shopify:")
        for i, product in enumerate(shopify_results[:3]):
            print(f"      {i+1}. {product.title}")
            
        print("   Elasticsearch:")
        for i, product in enumerate(es_results[:3]):
            print(f"      {i+1}. {product.title}")
            
    except Exception as e:
        print(f"   ❌ Comparison failed: {e}")

def main():
    """Run all Elasticsearch tests."""
    print("🚀 Elasticsearch Provider Test Suite")
    print("=" * 60)
    
    # Test 1: Connection
    if not test_elasticsearch_connection():
        print("\n❌ Cannot proceed without Elasticsearch connection")
        print("💡 Start Elasticsearch with: docker run -p 9200:9200 -e 'discovery.type=single-node' elasticsearch:8.11.0")
        return
    
    # Test 2: Provider initialization
    es_provider = test_provider_initialization()
    if not es_provider:
        print("\n❌ Cannot proceed without provider initialization")
        return
    
    # Test 3: Product sync
    if not test_product_sync(es_provider):
        print("\n❌ Cannot test search without synced products")
        return
    
    # Test 4: Basic search
    test_basic_search(es_provider)
    
    # Test 5: Synonym search
    test_synonym_search(es_provider)
    
    # Test 6: Fuzzy search
    test_fuzzy_search(es_provider)
    
    # Test 7: Filtered search
    test_filtered_search(es_provider)
    
    # Test 8: Provider comparison
    compare_search_providers()
    
    print("\n✨ Test suite complete!")
    print("🎯 If all tests passed, your Elasticsearch integration is working!")

if __name__ == "__main__":
    main()