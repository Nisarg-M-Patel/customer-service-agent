# api/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from customer_service.integrations.manager import IntegrationManager
from customer_service.config import Config
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

app = FastAPI(title="Customer Service API")

# Add CORS for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/ready")
async def check_ready():
    """Check if agent is fully initialized and ready"""
    try:
        config = Config()
        integration_manager = IntegrationManager.get_instance()
        
        # Check if we have products in the system
        sample_products = integration_manager.search_products()
        
        if len(sample_products) > 0:
            return {
                "ready": True, 
                "product_count": len(sample_products),
                "search_provider": "elasticsearch" if integration_manager._search_provider else "standard"
            }
        else:
            return {"ready": False, "reason": "No products found"}
            
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"ready": False, "reason": str(e)}

@app.post("/api/initialize")
async def force_initialize():
    """Force re-initialization of the agent"""
    try:
        config = Config()
        
        # Force create new IntegrationManager instance
        # This triggers all your existing initialization logic
        integration_manager = IntegrationManager(config)
        
        # Test that it worked
        sample_products = integration_manager.search_products()
        
        return {
            "status": "initialized",
            "product_count": len(sample_products),
            "message": "Agent successfully initialized"
        }
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "service": "customer-service-api"}

# Add this single comprehensive debug endpoint to api/main.py
@app.get("/api/debug-comprehensive/{query}")
async def debug_comprehensive(query: str):
    """Comprehensive debug of the entire search pipeline"""
    
    try:
        integration_manager = IntegrationManager.get_instance()
        
        debug_data = {
            "query": query,
            "timestamp": str(datetime.now()),
            
            # 1. Integration Manager Status
            "integration_status": {
                "providers": list(integration_manager._providers.keys()) if hasattr(integration_manager, '_providers') else [],
                "has_search_provider": integration_manager._search_provider is not None,
                "search_provider_type": type(integration_manager._search_provider).__name__ if integration_manager._search_provider else None,
                "config_search_provider": integration_manager.config.SEARCH_PROVIDER,
            },
            
            # 2. Intent Analysis
            "intent_analysis": {},
            
            # 3. Elasticsearch Debug
            "elasticsearch_debug": {},
            
            # 4. Final Search Results
            "search_results": {
                "intent_results": [],
                "keyword_results": []
            },
            
            "errors": []
        }
        
        # Step 1: Intent Analysis
        try:
            from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
            from customer_service.config import Config
            import json
            
            config = Config()
            config_generator = LLMConfigGenerator(config)
            
            # Analyze intent
            intent = config_generator.analyze_intent(query)
            problem_variations = config_generator.expand_problems(intent)
            
            # Load usage scenarios
            with open('customer_service/integrations/elasticsearch/usage_scenarios.json') as f:
                data = json.load(f)
                scenarios = data.get('scenarios', data)
            
            # Find matching products
            matching_products = []
            for problem_var in problem_variations:
                for product_id, product_scenarios in scenarios.items():
                    if problem_var.problem in product_scenarios:
                        matching_products.append({
                            "product_id": product_id,
                            "problem": problem_var.problem,
                            "confidence": problem_var.confidence
                        })
            
            debug_data["intent_analysis"] = {
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
                    } for p in problem_variations
                ],
                "matching_products": matching_products,
                "total_scenarios": len(scenarios)
            }
            
        except Exception as e:
            debug_data["errors"].append(f"Intent analysis failed: {str(e)}")
        
        # Step 2: Elasticsearch Debug
        if integration_manager._search_provider:
            try:
                es_provider = integration_manager._search_provider
                
                # Test if expected products exist in ES
                expected_product_ids = [mp["product_id"] for mp in debug_data["intent_analysis"].get("matching_products", [])]
                products_in_es = []
                
                for pid in expected_product_ids[:5]:  # Limit to first 5
                    product = es_provider.get_product_by_id(pid)
                    if product:
                        products_in_es.append({
                            "id": pid,
                            "title": product.title,
                            "usage_scenarios": product.usage_scenarios
                        })
                    else:
                        products_in_es.append({"id": pid, "found": False})
                
                # Test direct ES search for primary problem
                primary_problem = debug_data["intent_analysis"]["detected_intent"]["primary_problem"]
                search_body = {
                    "query": {
                        "match": {
                            "usage_scenarios": primary_problem
                        }
                    },
                    "size": 10
                }
                
                response = es_provider.es.search(index=es_provider.index_name, body=search_body)
                es_direct_results = [
                    {
                        "id": hit["_source"]["product_id"],
                        "title": hit["_source"]["title"],
                        "usage_scenarios": hit["_source"]["usage_scenarios"],
                        "score": hit["_score"]
                    }
                    for hit in response["hits"]["hits"]
                ]
                
                debug_data["elasticsearch_debug"] = {
                    "index_name": es_provider.index_name,
                    "expected_products_in_es": products_in_es,
                    "direct_search_results": es_direct_results,
                    "search_query_used": search_body
                }
                
            except Exception as e:
                debug_data["errors"].append(f"Elasticsearch debug failed: {str(e)}")
        
        # Step 3: Test Actual Search Methods
        try:
            # Test intent search
            if integration_manager._search_provider and hasattr(integration_manager._search_provider, 'search_by_intent'):
                intent_matches = integration_manager._search_provider.search_by_intent(query)
                debug_data["search_results"]["intent_results"] = [
                    {
                        "product_id": match.product_id,
                        "product_title": match.product_title,
                        "confidence": match.confidence,
                        "reasons": match.reasons,
                        "price": match.price
                    }
                    for match in intent_matches
                ]
            
            # Test keyword search
            products = integration_manager.search_products(query=query)
            debug_data["search_results"]["keyword_results"] = [
                {"id": p.id, "title": p.title, "price": p.price} for p in products[:5]
            ]
            
        except Exception as e:
            debug_data["errors"].append(f"Search methods failed: {str(e)}")
        
        return debug_data
        
    except Exception as e:
        return {"error": f"Comprehensive debug failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)