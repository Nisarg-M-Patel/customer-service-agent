# debug_elasticsearch.py
"""Debug what's actually in the Elasticsearch index."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from elasticsearch import Elasticsearch
from customer_service.config import Config
import json

def debug_elasticsearch():
    """Debug the Elasticsearch index and data."""
    
    config = Config()
    es = Elasticsearch([config.ELASTICSEARCH_URL])
    index_name = "garden_products"
    
    print("🔍 Elasticsearch Debug")
    print("=" * 50)
    
    # 1. Check if index exists
    print(f"📋 Index '{index_name}' exists: {es.indices.exists(index=index_name)}")
    
    # 2. Get index stats
    try:
        stats = es.indices.stats(index=index_name)
        doc_count = stats['indices'][index_name]['total']['docs']['count']
        print(f"📊 Documents in index: {doc_count}")
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return
    
    # 3. Get index mapping
    print("\n🗺️ Index mapping:")
    try:
        mapping = es.indices.get_mapping(index=index_name)
        fields = mapping[index_name]['mappings']['properties'].keys()
        print(f"   Fields: {list(fields)}")
    except Exception as e:
        print(f"❌ Error getting mapping: {e}")
    
    # 4. Get a few sample documents
    print("\n📄 Sample documents:")
    try:
        search_body = {
            "query": {"match_all": {}},
            "size": 3
        }
        response = es.search(index=index_name, body=search_body)
        
        for i, hit in enumerate(response['hits']['hits']):
            source = hit['_source']
            print(f"\n   Document {i+1}:")
            print(f"      ID: {source.get('product_id')}")
            print(f"      Title: {source.get('title')}")
            print(f"      Tags: {source.get('tags', 'None')}")
            print(f"      Categories: {source.get('categories', 'None')}")
            print(f"      Description: {source.get('description', 'None')[:100]}...")
            
    except Exception as e:
        print(f"❌ Error getting documents: {e}")
    
    # 5. Test a simple search
    print("\n🔍 Testing simple search:")
    test_terms = ["bamboo", "garden", "watering", "gloves"]
    
    for term in test_terms:
        try:
            # Simple match query
            search_body = {
                "query": {
                    "multi_match": {
                        "query": term,
                        "fields": ["title", "description", "tags", "categories"]
                    }
                },
                "size": 1
            }
            
            response = es.search(index=index_name, body=search_body)
            hit_count = response['hits']['total']['value']
            print(f"   '{term}': {hit_count} results")
            
            if hit_count > 0:
                top_result = response['hits']['hits'][0]['_source']
                print(f"      Top result: {top_result.get('title')}")
                
        except Exception as e:
            print(f"   ❌ Search for '{term}' failed: {e}")
    
    # 6. Test analyzer
    print("\n🔧 Testing analyzer:")
    try:
        analyze_body = {
            "analyzer": "business_search_analyzer",
            "text": "bamboo gloves"
        }
        
        response = es.indices.analyze(index=index_name, body=analyze_body)
        tokens = [token['token'] for token in response['tokens']]
        print(f"   'bamboo gloves' analyzes to: {tokens}")
        
    except Exception as e:
        print(f"❌ Analyzer test failed: {e}")
    
    # 7. Check if data is actually there with direct field search
    print("\n🎯 Testing direct field searches:")
    for field in ["title", "tags", "categories"]:
        try:
            search_body = {
                "query": {
                    "exists": {
                        "field": field
                    }
                },
                "size": 1
            }
            
            response = es.search(index=index_name, body=search_body)
            count = response['hits']['total']['value']
            print(f"   Documents with '{field}': {count}")
            
            if count > 0:
                sample_value = response['hits']['hits'][0]['_source'].get(field)
                print(f"      Sample {field}: {sample_value}")
                
        except Exception as e:
            print(f"   ❌ Field check for '{field}' failed: {e}")

if __name__ == "__main__":
    debug_elasticsearch()