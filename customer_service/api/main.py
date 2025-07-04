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
    """Force re-initialization of the agent with complete ES index recreation"""
    try:
        config = Config()
        
        # Step 1: Force delete existing ES index if it exists
        try:
            from elasticsearch import Elasticsearch
            es = Elasticsearch([config.ELASTICSEARCH_URL])
            index_name = "garden_products"
            
            if es.indices.exists(index=index_name):
                es.indices.delete(index=index_name)
                logger.info(f"Deleted existing ES index: {index_name}")
            else:
                logger.info(f"ES index {index_name} doesn't exist")
        except Exception as e:
            logger.warning(f"Could not delete ES index: {e}")
        
        # Step 2: Force create new IntegrationManager instance
        # This will create a new ES index WITH vector field mappings
        integration_manager = IntegrationManager(config)
        
        # Step 3: Test that vector fields were created
        vector_fields_created = False
        if integration_manager._search_provider:
            try:
                es_provider = integration_manager._search_provider
                
                # Check if the new index has vector fields
                mapping = es_provider.es.indices.get_mapping(index=es_provider.index_name)
                properties = mapping[es_provider.index_name]['mappings']['properties']
                
                vector_fields = {}
                for field_name, field_config in properties.items():
                    if field_config.get('type') == 'dense_vector':
                        vector_fields[field_name] = field_config.get('dims')
                
                vector_fields_created = len(vector_fields) > 0
                logger.info(f"Vector fields created: {vector_fields}")
                
            except Exception as e:
                logger.error(f"Could not check vector fields: {e}")
        
        # Step 4: Test that it worked
        sample_products = integration_manager.search_products()
        
        # Step 5: Test embedding generation
        embedding_test_success = False
        if integration_manager._search_provider and hasattr(integration_manager._search_provider, '_generate_embeddings'):
            try:
                test_embeddings = integration_manager._search_provider._generate_embeddings(["test text"])
                embedding_test_success = len(test_embeddings) > 0 and len(test_embeddings[0]) > 0
            except Exception as e:
                logger.error(f"Embedding test failed: {e}")
        
        return {
            "status": "initialized",
            "product_count": len(sample_products),
            "vector_fields_created": vector_fields_created,
            "embedding_test_success": embedding_test_success,
            "search_provider": type(integration_manager._search_provider).__name__ if integration_manager._search_provider else "None",
            "message": f"Agent successfully initialized with {'vector support' if vector_fields_created else 'basic support'}"
        }
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "service": "customer-service-api"}

@app.get("/api/debug-comprehensive/{query}")
async def debug_comprehensive(query: str):
    """Comprehensive debug of the entire search pipeline including vector search"""
    
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
                "es_version_support": "8.x" if hasattr(integration_manager._search_provider, '_generate_embeddings') else "7.x"
            },
            
            # 2. Intent Analysis
            "intent_analysis": {},
            
            # 3. Vector Search Debug
            "vector_search_debug": {},
            
            # 4. Elasticsearch Debug
            "elasticsearch_debug": {},
            
            # 5. Search Results Comparison
            "search_results": {
                "intent_results": [],
                "vector_intent_results": [],
                "keyword_results": []
            },
            
            "errors": []
        }
        
        # Step 1: Intent Analysis
        try:
            from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
            import json
            
            config = Config()
            config_generator = LLMConfigGenerator(config)
            
            # Analyze intent
            intent = config_generator.analyze_intent(query)
            problem_variations = config_generator.expand_problems(intent)
            
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
                "problem_texts_for_embedding": [p.problem for p in problem_variations]
            }
            
        except Exception as e:
            debug_data["errors"].append(f"Intent analysis failed: {str(e)}")
        
        # Step 2: Vector Search Debug
        if integration_manager._search_provider and hasattr(integration_manager._search_provider, '_generate_embeddings'):
            try:
                es_provider = integration_manager._search_provider
                
                # Test embedding generation
                test_texts = [intent.primary_problem] if 'intent_analysis' in debug_data and debug_data['intent_analysis'] else ["plant health issues"]
                test_embeddings = es_provider._generate_embeddings(test_texts)
                
                debug_data["vector_search_debug"] = {
                    "embeddings_available": True,
                    "embedding_model": "gemini-embedding-001",
                    "test_embedding_dimension": len(test_embeddings[0]) if test_embeddings else 0,
                    "test_embedding_success": len(test_embeddings) > 0,
                    "embedding_sample": test_embeddings[0][:5] if test_embeddings else None  # First 5 values
                }
                
                # Check if products have vector fields
                try:
                    # Sample a product to check for vector fields
                    sample_search = {
                        "query": {"match_all": {}},
                        "size": 1,
                        "_source": ["product_id", "title_vector", "description_vector", "usage_scenarios_vectors"]
                    }
                    
                    response = es_provider.es.search(index=es_provider.index_name, body=sample_search)
                    
                    if response["hits"]["hits"]:
                        sample_product = response["hits"]["hits"][0]["_source"]
                        debug_data["vector_search_debug"]["sample_product_vectors"] = {
                            "has_title_vector": "title_vector" in sample_product and sample_product["title_vector"] is not None,
                            "has_description_vector": "description_vector" in sample_product and sample_product["description_vector"] is not None,
                            "has_usage_scenarios_vectors": "usage_scenarios_vectors" in sample_product and sample_product["usage_scenarios_vectors"] is not None,
                            "usage_scenarios_vector_count": len(sample_product.get("usage_scenarios_vectors", [])) if sample_product.get("usage_scenarios_vectors") else 0
                        }
                    else:
                        debug_data["vector_search_debug"]["sample_product_vectors"] = {"no_products_found": True}
                        
                except Exception as e:
                    debug_data["errors"].append(f"Vector field check failed: {str(e)}")
                
            except Exception as e:
                debug_data["vector_search_debug"] = {
                    "embeddings_available": False,
                    "error": str(e)
                }
                debug_data["errors"].append(f"Vector search debug failed: {str(e)}")
        else:
            debug_data["vector_search_debug"] = {
                "embeddings_available": False,
                "reason": "No vector-capable search provider or old ES version"
            }
        
        # Step 3: Elasticsearch Debug
        if integration_manager._search_provider:
            try:
                es_provider = integration_manager._search_provider
                
                # Test index mapping
                try:
                    mapping = es_provider.es.indices.get_mapping(index=es_provider.index_name)
                    properties = mapping[es_provider.index_name]['mappings']['properties']
                    
                    vector_fields = {}
                    for field_name, field_config in properties.items():
                        if field_config.get('type') == 'dense_vector':
                            vector_fields[field_name] = {
                                "dims": field_config.get('dims'),
                                "similarity": field_config.get('similarity')
                            }
                    
                    debug_data["elasticsearch_debug"] = {
                        "index_name": es_provider.index_name,
                        "vector_fields_in_mapping": vector_fields,
                        "total_fields": len(properties),
                        "has_vector_support": len(vector_fields) > 0
                    }
                    
                except Exception as e:
                    debug_data["errors"].append(f"ES mapping check failed: {str(e)}")
                
            except Exception as e:
                debug_data["errors"].append(f"Elasticsearch debug failed: {str(e)}")
        
        # Step 4: Test Different Search Methods
        try:
            # Test keyword search
            keyword_products = integration_manager.search_products(query=query)
            debug_data["search_results"]["keyword_results"] = [
                {"id": p.id, "title": p.title, "price": p.price} for p in keyword_products[:5]
            ]
            
            # Test original intent search (if available)
            if integration_manager._search_provider and hasattr(integration_manager._search_provider, '_fallback_keyword_intent_search'):
                try:
                    from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
                    config_generator = LLMConfigGenerator(integration_manager.config)
                    intent = config_generator.analyze_intent(query)
                    problem_variations = config_generator.expand_problems(intent)
                    
                    intent_matches = integration_manager._search_provider._fallback_keyword_intent_search(query, problem_variations)
                    debug_data["search_results"]["intent_results"] = [
                        {
                            "product_id": match.product_id,
                            "product_title": match.product_title,
                            "confidence": match.confidence,
                            "reasons": match.reasons
                        }
                        for match in intent_matches[:5]
                    ]
                except Exception as e:
                    debug_data["errors"].append(f"Original intent search failed: {str(e)}")
            
            # Test new vector intent search (if available)
            if integration_manager._search_provider and hasattr(integration_manager._search_provider, 'search_by_intent_with_vectors'):
                try:
                    vector_intent_matches = integration_manager._search_provider.search_by_intent_with_vectors(query)
                    debug_data["search_results"]["vector_intent_results"] = [
                        {
                            "product_id": match.product_id,
                            "product_title": match.product_title,
                            "confidence": match.confidence,
                            "reasons": match.reasons,
                            "price": match.price
                        }
                        for match in vector_intent_matches[:5]
                    ]
                except Exception as e:
                    debug_data["errors"].append(f"Vector intent search failed: {str(e)}")
            
        except Exception as e:
            debug_data["errors"].append(f"Search methods test failed: {str(e)}")
        
        return debug_data
        
    except Exception as e:
        return {"error": f"Comprehensive debug failed: {str(e)}"}

@app.get("/api/test-vector-search/{query}")
async def test_vector_search(query: str):
    """Test vector search functionality specifically"""
    
    try:
        integration_manager = IntegrationManager.get_instance()
        
        if not integration_manager._search_provider:
            return {"error": "No search provider available"}
        
        if not hasattr(integration_manager._search_provider, 'search_by_intent_with_vectors'):
            return {"error": "Vector search not available - update to ES 8.x version"}
        
        # Test vector search
        vector_matches = integration_manager._search_provider.search_by_intent_with_vectors(query)
        
        # Test keyword fallback
        from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
        config_generator = LLMConfigGenerator(integration_manager.config)
        intent = config_generator.analyze_intent(query)
        problem_variations = config_generator.expand_problems(intent)
        
        keyword_matches = integration_manager._search_provider._fallback_keyword_intent_search(query, problem_variations)
        
        return {
            "query": query,
            "vector_search_results": [
                {
                    "product_id": match.product_id,
                    "product_title": match.product_title,
                    "confidence": match.confidence,
                    "reasons": match.reasons,
                    "price": match.price
                }
                for match in vector_matches
            ],
            "keyword_search_results": [
                {
                    "product_id": match.product_id,
                    "product_title": match.product_title,
                    "confidence": match.confidence,
                    "reasons": match.reasons,
                    "price": match.price
                }
                for match in keyword_matches
            ],
            "comparison": {
                "vector_count": len(vector_matches),
                "keyword_count": len(keyword_matches),
                "vector_better": len(vector_matches) > len(keyword_matches)
            }
        }
        
    except Exception as e:
        return {"error": f"Vector search test failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

@app.get("/api/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "service": "customer-service-api"}

@app.get("/api/debug-comprehensive/{query}")
async def debug_comprehensive(query: str):
    """Comprehensive debug of the entire search pipeline including vector search"""
    
    try:
        integration_manager = IntegrationManager.get_instance()
        
        debug_data = {
            "query": query,
            "timestamp": str(datetime.now()),
            "integration_status": {
                "providers": list(integration_manager._providers.keys()) if hasattr(integration_manager, '_providers') else [],
                "has_search_provider": integration_manager._search_provider is not None,
                "search_provider_type": type(integration_manager._search_provider).__name__ if integration_manager._search_provider else None,
                "config_search_provider": integration_manager.config.SEARCH_PROVIDER,
                "es_version_support": "8.x" if hasattr(integration_manager._search_provider, '_generate_embeddings') else "7.x"
            },
            "intent_analysis": {},
            "vector_search_debug": {},
            "elasticsearch_debug": {},
            "search_results": {
                "intent_results": [],
                "vector_intent_results": [],
                "keyword_results": []
            },
            "errors": []
        }
        
        # Step 1: Intent Analysis
        try:
            from customer_service.integrations.elasticsearch.config_generator import LLMConfigGenerator
            
            config = Config()
            config_generator = LLMConfigGenerator(config)
            intent = config_generator.analyze_intent(query)
            problem_variations = config_generator.expand_problems(intent)
            
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
                ]
            }
        except Exception as e:
            debug_data["errors"].append(f"Intent analysis failed: {str(e)}")
        
        # Step 2: Vector Search Debug
        try:
            if integration_manager._search_provider and hasattr(integration_manager._search_provider, '_generate_embeddings'):
                es_provider = integration_manager._search_provider
                test_embeddings = es_provider._generate_embeddings(["test"])
                
                debug_data["vector_search_debug"] = {
                    "embeddings_available": True,
                    "embedding_model": "gemini-embedding-001",
                    "test_embedding_dimension": len(test_embeddings[0]) if test_embeddings else 0,
                    "test_embedding_success": len(test_embeddings) > 0
                }
            else:
                debug_data["vector_search_debug"] = {
                    "embeddings_available": False,
                    "reason": "No vector support"
                }
        except Exception as e:
            debug_data["vector_search_debug"] = {"embeddings_available": False, "error": str(e)}
            debug_data["errors"].append(f"Vector search debug failed: {str(e)}")
        
        # Step 3: Elasticsearch Debug
        try:
            if integration_manager._search_provider:
                es_provider = integration_manager._search_provider
                mapping = es_provider.es.indices.get_mapping(index=es_provider.index_name)
                properties = mapping[es_provider.index_name]['mappings']['properties']
                
                vector_fields = {}
                for field_name, field_config in properties.items():
                    if field_config.get('type') == 'dense_vector':
                        vector_fields[field_name] = {"dims": field_config.get('dims')}
                
                debug_data["elasticsearch_debug"] = {
                    "index_name": es_provider.index_name,
                    "vector_fields_in_mapping": vector_fields,
                    "total_fields": len(properties),
                    "has_vector_support": len(vector_fields) > 0
                }
        except Exception as e:
            debug_data["errors"].append(f"ES debug failed: {str(e)}")
        
        # Step 4: Test Search Methods
        try:
            keyword_products = integration_manager.search_products(query=query)
            debug_data["search_results"]["keyword_results"] = [
                {"id": p.id, "title": p.title, "price": p.price} for p in keyword_products[:5]
            ]
            
            if integration_manager._search_provider and hasattr(integration_manager._search_provider, 'search_by_intent_with_vectors'):
                vector_matches = integration_manager._search_provider.search_by_intent_with_vectors(query)
                debug_data["search_results"]["vector_intent_results"] = [
                    {
                        "product_id": match.product_id,
                        "product_title": match.product_title,
                        "confidence": match.confidence,
                        "reasons": match.reasons,
                        "price": match.price
                    }
                    for match in vector_matches[:5]
                ]
        except Exception as e:
            debug_data["errors"].append(f"Search test failed: {str(e)}")
        
        return debug_data
        
    except Exception as e:
        return {"error": f"Debug failed: {str(e)}"}