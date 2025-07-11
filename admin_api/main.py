# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from customer_service.integrations.manager import IntegrationManager
from customer_service.config import Config
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Customer Service API")

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
   return {"status": "healthy", "service": "customer-service-api"}

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
       
       # Ensure ES provider exists (creates index with vector fields if needed)
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
        
        # Get products from Elasticsearch
        if not integration_manager._search_provider:
            return {"status": "error", "message": "No Elasticsearch provider available"}
        
        products = integration_manager._search_provider.search_products()
        
        if not products:
            return {"status": "error", "message": "No products found in Elasticsearch"}
        
        # Generate usage scenarios
        usage_scenarios = config_generator.generate_usage_scenarios(products)
        
        if not usage_scenarios:
            return {"status": "error", "message": "Failed to generate usage scenarios"}
        
        return {
            "status": "success",
            "products_processed": len(products),
            "scenarios_generated": len(usage_scenarios),
            "sample_scenarios": dict(list(usage_scenarios.items())[:20])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-embeddings")
async def generate_embeddings():
    """Generate vector embeddings for products and update Elasticsearch."""
    try:
        config = Config()
        integration_manager = IntegrationManager.get_instance()
        
        if not integration_manager._search_provider:
            return {"status": "error", "message": "No Elasticsearch provider available"}
        
        es_provider = integration_manager._search_provider
        products = es_provider.search_products()
        
        if not products:
            return {"status": "error", "message": "No products found in Elasticsearch"}
        
        # Load usage scenarios
        from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
        config_generator = LLMConfigGenerator(config)
        usage_scenarios = config_generator.load_usage_scenarios()
        
        if not usage_scenarios:
            return {"status": "error", "message": "No usage scenarios found. Generate scenarios first."}
        
        # Update products with scenarios
        products_with_scenarios = []
        for product in products:
            if product.id in usage_scenarios:
                product.usage_scenarios = usage_scenarios[product.id]
                products_with_scenarios.append(product)
        
        # Bulk index with new method
        indexed_count = es_provider.bulk_index_products(products_with_scenarios)
        
        return {
            "status": "success",
            "products_processed": len(products_with_scenarios),
            "documents_indexed": indexed_count,
            "embedding_model": config.EMBEDDING_MODEL
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/debug-embeddings")
async def debug_embeddings():
    """Check if products and scenarios have embeddings."""
    try:
        config = Config()
        integration_manager = IntegrationManager.get_instance()
        
        if not integration_manager._search_provider:
            return {"status": "error", "message": "No Elasticsearch provider"}
        
        es_provider = integration_manager._search_provider
        
        # Check document counts by type
        product_count_query = {
            "query": {"term": {"type": "product"}},
            "size": 0
        }
        scenario_count_query = {
            "query": {"term": {"type": "scenario"}},
            "size": 0
        }
        
        product_response = es_provider.es.search(index=es_provider.index_name, body=product_count_query)
        scenario_response = es_provider.es.search(index=es_provider.index_name, body=scenario_count_query)
        
        product_count = product_response["hits"]["total"]["value"]
        scenario_count = scenario_response["hits"]["total"]["value"]
        
        # Get sample documents
        sample_product_query = {
            "query": {"term": {"type": "product"}},
            "size": 1,
            "_source": ["product_id", "title", "title_vector"]
        }
        sample_scenario_query = {
            "query": {"term": {"type": "scenario"}},
            "size": 1,
            "_source": ["product_id", "scenario_text", "scenario_vector"]
        }
        
        sample_product = es_provider.es.search(index=es_provider.index_name, body=sample_product_query)
        sample_scenario = es_provider.es.search(index=es_provider.index_name, body=sample_scenario_query)
        
        result = {
            "status": "success",
            "total_documents": product_count + scenario_count,
            "product_documents": product_count,
            "scenario_documents": scenario_count
        }
        
        # Check if sample documents have embeddings
        if sample_product["hits"]["hits"]:
            product_doc = sample_product["hits"]["hits"][0]["_source"]
            result["sample_product"] = {
                "id": product_doc.get("product_id"),
                "title": product_doc.get("title"),
                "has_title_vector": "title_vector" in product_doc and product_doc["title_vector"] is not None
            }
        
        if sample_scenario["hits"]["hits"]:
            scenario_doc = sample_scenario["hits"]["hits"][0]["_source"]
            result["sample_scenario"] = {
                "product_id": scenario_doc.get("product_id"),
                "scenario_text": scenario_doc.get("scenario_text"),
                "has_scenario_vector": "scenario_vector" in scenario_doc and scenario_doc["scenario_vector"] is not None,
                "vector_dimensions": len(scenario_doc["scenario_vector"]) if scenario_doc.get("scenario_vector") else 0
            }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search-intent")
async def search_intent(request: dict):
    """Search using existing intent analysis + vector search."""
    try:
        query = request.get("query")
        if not query:
            return {"status": "error", "message": "Query is required"}
        
        integration_manager = IntegrationManager.get_instance()
        
        if not integration_manager._search_provider:
            return {"status": "error", "message": "No Elasticsearch provider"}
        
        # Use your existing intent-based vector search
        matches = integration_manager._search_provider.search_by_intent_with_vectors(query)
        
        return {
            "status": "success",
            "query": query,
            "results": [
                {
                    "product_id": match.product_id,
                    "title": match.product_title,
                    "price": match.price,
                    "confidence": match.confidence,
                    "reasons": match.reasons
                }
                for match in matches
            ],
            "total_matches": len(matches)
        }
        
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
        
        # Delete existing config files to force regeneration
        if config_generator.config_file_path.exists():
            config_generator.config_file_path.unlink()
            print("Deleted existing search config")
        
        if config_generator.usage_scenarios_file_path.exists():
            config_generator.usage_scenarios_file_path.unlink()
            print("Deleted existing usage scenarios")
            
        if config_generator.reverse_dict_file_path.exists():
            config_generator.reverse_dict_file_path.unlink()
            print("Deleted existing reverse dictionary")
        
        # Generate new config (this will auto-generate scenarios and reverse dict)
        search_config = config_generator.generate_config(products)
        
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
        
        # Step 5: Verify usage scenarios were generated
        print("Step 5: Verifying usage scenarios...")
        usage_scenarios = config_generator.load_usage_scenarios()
        
        if not usage_scenarios:
            print("Usage scenarios missing, generating manually...")
            usage_scenarios = config_generator.generate_usage_scenarios(products)
            
            if usage_scenarios:
                config_generator._save_usage_scenarios(usage_scenarios)
                print(f"Generated usage scenarios for {len(usage_scenarios)} products")
            else:
                return {
                    "status": "error",
                    "message": "Failed to generate usage scenarios",
                    "step": "usage_scenarios"
                }
        else:
            print(f"Usage scenarios verified: {len(usage_scenarios)} products")
        
        # Step 6: Verify reverse dictionary was generated
        print("Step 6: Verifying reverse dictionary...")
        reverse_dict = config_generator.load_reverse_dictionary()
        
        if not reverse_dict:
            print("Reverse dictionary missing, generating...")
            reverse_dict = config_generator._build_reverse_dictionary(usage_scenarios)
            config_generator._save_reverse_dictionary(reverse_dict)
            print(f"Generated reverse dictionary with {len(reverse_dict)} problem keywords")
        else:
            print(f"Reverse dictionary verified: {len(reverse_dict)} problem keywords")
        
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
            },
            "files_generated": [
                str(config_generator.config_file_path),
                str(config_generator.usage_scenarios_file_path), 
                str(config_generator.reverse_dict_file_path)
            ]
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