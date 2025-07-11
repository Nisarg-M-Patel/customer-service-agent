# admin_api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from customer_service.integrations.manager import IntegrationManager
from customer_service.config import Config
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Customer Service Admin API")

app.add_middleware(
   CORSMiddleware,
   allow_origins=["*"],  # Allow all origins for testing
   allow_credentials=True,
   allow_methods=["*"],
   allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
   """Basic health check endpoint."""
   return {"status": "healthy", "service": "customer-service-admin-api"}

@app.post("/api/sync-products")
async def sync_products():
   """Sync products from provider to Elasticsearch."""
   try:
       integration_manager = IntegrationManager.get_instance()
       
       # Get products from source provider
       primary_provider = integration_manager._get_primary_provider()
       products = primary_provider.search_products()
       
       if not products:
           return {"status": "error", "message": "No products found in source provider"}
       
       # Ensure ES provider exists
       if not integration_manager._search_provider:
           from customer_service.integrations.elasticsearch.provider import ElasticsearchProvider
           config = Config()
           integration_manager._search_provider = ElasticsearchProvider(config)
       
       # Sync products to Elasticsearch
       es_provider = integration_manager._search_provider
       indexed_count = es_provider.bulk_index_products(products)
       
       return {
           "status": "success",
           "source_provider": type(primary_provider).__name__,
           "products_found": len(products),
           "products_indexed": indexed_count,
           "elasticsearch_index": es_provider.index_name
       }
       
   except Exception as e:
       raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-scenarios")
async def generate_scenarios():
    """Generate usage scenarios for products using LLM."""
    try:
        from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
        
        config = Config()
        integration_manager = IntegrationManager.get_instance()
        config_generator = LLMConfigGenerator(config)
        
        # Get products from source provider
        primary_provider = integration_manager._get_primary_provider()
        products = primary_provider.search_products()
        
        if not products:
            return {"status": "error", "message": "No products found in source provider"}
        
        # Generate usage scenarios
        usage_scenarios = config_generator.generate_usage_scenarios(products)
        
        if not usage_scenarios:
            return {"status": "error", "message": "Failed to generate usage scenarios"}
        
        # Save to Elasticsearch
        if integration_manager._search_provider:
            success = integration_manager._search_provider.save_usage_scenarios({
                "scenarios": usage_scenarios,
                "generated_at": str(datetime.now()),
                "product_count": len(usage_scenarios)
            })
            
            if success:
                return {
                    "status": "success",
                    "products_processed": len(products),
                    "scenarios_generated": len(usage_scenarios),
                    "sample_scenarios": dict(list(usage_scenarios.items())[:5])
                }
        
        return {"status": "error", "message": "Failed to save usage scenarios"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/debug-intent")
async def debug_intent(request: dict):
    """Debug what intent analysis produces for a query."""
    try:
        query = request.get("query")
        if not query:
            return {"status": "error", "message": "Query is required"}
        
        from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
        config = Config()
        config_generator = LLMConfigGenerator(config)
        
        # Analyze intent
        intent = config_generator.analyze_intent(query)
        problem_variations = config_generator.expand_problems(intent)
        
        return {
            "status": "success",
            "query": query,
            "detected_intent": {
                "primary_problem": intent.primary_problem,
                "context": intent.context,
                "symptoms": intent.symptoms,
                "urgency": intent.urgency
            },
            "problem_variations": [
                {
                    "problem": p.problem,
                    "confidence": p.confidence,
                    "category": p.category
                }
                for p in problem_variations
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search-test")
async def search_test(request: dict):
    """Test both keyword and intent search."""
    try:
        query = request.get("query")
        if not query:
            return {"status": "error", "message": "Query is required"}
        
        integration_manager = IntegrationManager.get_instance()
        
        # Test keyword search
        keyword_results = integration_manager.search_products(query=query)
        
        # Test intent search (if ES provider available)
        intent_results = []
        if integration_manager._search_provider:
            try:
                from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
                config_generator = LLMConfigGenerator(Config())
                
                # Get reverse dictionary
                reverse_dict = config_generator.load_reverse_dictionary()
                
                if reverse_dict:
                    # Analyze intent
                    intent = config_generator.analyze_intent(query)
                    
                    # Look up in reverse dictionary
                    if intent.primary_problem in reverse_dict:
                        product_ids = reverse_dict[intent.primary_problem]
                        for product_id in product_ids[:5]:  # Top 5
                            product = integration_manager.get_product_by_id(product_id)
                            if product:
                                intent_results.append({
                                    "product_id": product.id,
                                    "title": product.title,
                                    "price": product.price,
                                    "match_reason": f"Intent: {intent.primary_problem}"
                                })
                
            except Exception as e:
                logger.error(f"Intent search failed: {e}")
        
        return {
            "status": "success",
            "query": query,
            "keyword_results": [
                {
                    "product_id": p.id,
                    "title": p.title,
                    "price": p.price
                }
                for p in keyword_results[:5]
            ],
            "intent_results": intent_results,
            "keyword_count": len(keyword_results),
            "intent_count": len(intent_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/system-warmup")
async def system_warmup():
    """Complete system warmup: sync products, generate config, scenarios, and reverse dictionary."""
    try:
        config = Config()
        integration_manager = IntegrationManager.get_instance()
        
        # Step 1: Get fresh products from source
        print("Step 1: Fetching products from source provider...")
        primary_provider = integration_manager._get_primary_provider()
        products = primary_provider.search_products()
        
        if not products:
            return {
                "status": "error",
                "message": "No products found in source provider",
                "step": "product_fetch"
            }
        
        print(f"Found {len(products)} products from {type(primary_provider).__name__}")
        
        # Step 2: Force regenerate search config
        print("Step 2: Force regenerating search configuration...")
        from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
        config_generator = LLMConfigGenerator(config)
        
        # Force regenerate config (bypasses existence checks)
        search_config = config_generator.regenerate_config(products)
        
        if not search_config:
            return {
                "status": "error", 
                "message": "Failed to generate search configuration",
                "step": "config_generation"
            }
        
        print(f"Generated config for business type: {search_config.get('business_type')}")
        
        # Step 3: Initialize/recreate Elasticsearch provider with new config
        print("Step 3: Initializing Elasticsearch with new configuration...")
        try:
            from customer_service.integrations.elasticsearch.provider import ElasticsearchProvider
            
            # Create new ES provider (will use the new config)
            es_provider = ElasticsearchProvider(config)
            
            # Delete existing index to start fresh
            if es_provider.es.indices.exists(index=es_provider.index_name):
                es_provider.es.indices.delete(index=es_provider.index_name)
                print(f"Deleted existing index: {es_provider.index_name}")
            
            # Recreate index
            es_provider._create_index()
            print(f"Created fresh index: {es_provider.index_name}")
            
            # Update integration manager to use new ES provider
            integration_manager._search_provider = es_provider
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to initialize Elasticsearch: {str(e)}",
                "step": "elasticsearch_init"
            }
        
        # Step 4: Sync products to Elasticsearch
        print("Step 4: Syncing products to Elasticsearch...")
        indexed_count = es_provider.bulk_index_products(products)
        
        if indexed_count == 0:
            return {
                "status": "error",
                "message": "Failed to index any products",
                "step": "product_indexing"
            }
        
        print(f"Indexed {indexed_count} products")
        
        # Step 5: Generate and save usage scenarios
        print("Step 5: Generating usage scenarios...")
        usage_scenarios = config_generator.generate_usage_scenarios(products)
        
        if not usage_scenarios:
            return {
                "status": "error",
                "message": "Failed to generate usage scenarios",
                "step": "usage_scenarios"
            }
        
        print(f"Generated usage scenarios for {len(usage_scenarios)} products")
        
        # Step 6: Build and save reverse dictionary
        print("Step 6: Building reverse dictionary...")
        reverse_dict = config_generator._build_reverse_dictionary(usage_scenarios)
        config_generator._save_reverse_dictionary(reverse_dict)
        
        print(f"Built reverse dictionary with {len(reverse_dict)} problem keywords")
        
        print("Step 7: System warmup completed!")
        
        # Success response with detailed info
        return {
            "status": "success",
            "message": "System warmup completed successfully",
            "details": {
                "source_provider": type(primary_provider).__name__,
                "business_type": search_config.get("business_type"),
                "index_name": es_provider.index_name,
                "products_found": len(products),
                "products_indexed": indexed_count,
                "usage_scenarios_count": len(usage_scenarios),
                "reverse_dict_entries": len(reverse_dict),
                "synonym_groups": len(search_config.get("synonym_groups", [])),
                "domain_keywords": search_config.get("domain_keywords", [])
            }
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            "step": "unknown"
        }
    
if __name__ == "__main__":
   import uvicorn
   uvicorn.run(app, host="0.0.0.0", port=8001)