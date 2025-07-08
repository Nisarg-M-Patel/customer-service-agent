"""Product-related tools for the customer service agent."""

import logging
from typing import Optional
import json
from google.adk.tools import ToolContext
from google.genai import types
from ..integrations.manager import IntegrationManager

logger = logging.getLogger(__name__)

def get_product_recommendations(query: str, customer_id: str) -> dict:
    """
    Get product recommendations based on search query.
    
    Args:
        query: Search query for products customer is interested in
        customer_id: Customer ID for personalization
        
    Returns:
        Dictionary with product recommendations
    """
    logger.info(f"Getting recommendations for query: {query}, customer: {customer_id}")
    
    try:
        # Get singleton integration manager instance
        integration_manager = IntegrationManager.get_instance()
        
        # Search for products related to the query
        products = integration_manager.search_products(query=query)
        
        # Format recommendations
        recommendations = []
        for product in products[:5]:  # Top 5 recommendations
            recommendations.append({
                "product_id": product.id,
                "name": product.title,
                "description": product.description,
                "price": product.price,
                "availability": product.availability,
                "image": product.images[0] if product.images else None
            })
        
        return {"recommendations": recommendations}
        
    except Exception as e:
        logger.error(f"Error getting product recommendations: {e}")
        return {"recommendations": [], "error": str(e)}

def search_products(query: str, category: Optional[str]=None, tool_context : ToolContext = None) -> dict:
    """
    Search for products by query and optional category.
    
    Args:
        query: Search query
        category: Optional category filter
        
    Returns:
        Dictionary with search results
    """
    logger.info(f"Searching products: query='{query}', category='{category}'")
    
    try:
        # Get singleton integration manager instance
        integration_manager = IntegrationManager.get_instance()
        
        products = integration_manager.search_products(query=query, category=category)
        
        results = []
        for product in products:
            results.append({
                "product_id": product.id,
                "name": product.title,
                "description": product.description,
                "price": product.price,
                "sku": product.sku,
                "availability": product.availability,
                "tags": product.tags
            })
        
        result_data = {
            "results": results,
            "total": len(results),
            "query": query,
            "category": category
        }
        if tool_context:
            try:
                # Save search results as artifact
                artifact_content = json.dumps(result_data, indent=2)
                artifact_part = types.Part(text=artifact_content)
                version = tool_context.save_artifact("keyword_search_results.json", artifact_part)
                logger.info(f"Saved keyword search results as artifact version {version}")
                
                # Store artifact name in state for synthesizer
                tool_context.state["keyword_results_artifact"] = "keyword_search_results.json"
                
            except ValueError as e:
                logger.error(f"Error saving keyword search artifact: {e}")
            except Exception as e:
                logger.error(f"Unexpected error saving keyword search artifact: {e}")
        
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        return {"results": [], "error": str(e)}

def intent_search_products(query: str, tool_context : ToolContext = None) -> dict:

    """
    Search for products using intent analysis and two-tower approach.
    
    Args:
        query: User query expressing a problem or need
        
    Returns:
        Dictionary with intent-based product results
    """
    logger.info(f"Intent search for: {query}")
    
    try:
        # Get singleton integration manager instance
        integration_manager = IntegrationManager.get_instance()
        
        # Step 1: Extract primary intent from user query using LLM
        from ..integrations.elasticsearch.config_generator import LLMConfigGenerator
        from ..config import Config
        from ..database.models import IntentResult
        
        config = Config()
        config_generator = LLMConfigGenerator(config)
        
        # Load business context from existing config
        search_config = config_generator.load_config()
        business_type = search_config.get("business_type", "general") if search_config else "general"
        domain_context = search_config.get("domain_keywords", []) if search_config else []
        
        try:
            intent = config_generator.analyze_intent(query)
            logger.info(f"Extracted intent: {intent.primary_problem}")
        except Exception as e:
            logger.error(f"Intent extraction failed: {e}")
            # Fallback intent
            intent = IntentResult(
                primary_problem="general_need",
                context=[],
                symptoms=[],
                urgency="medium"
            )
        
        # Step 2: Look up solutions in reverse dictionary
        reverse_dict_results = []
        try:
            reverse_dict = config_generator.load_reverse_dictionary()
            if reverse_dict and intent.primary_problem in reverse_dict:
                reverse_dict_results = reverse_dict[intent.primary_problem]
                logger.info(f"Reverse dictionary found {len(reverse_dict_results)} products")
            else:
                logger.info(f"No reverse dictionary entry found for problem: {intent.primary_problem}")
        except Exception as e:
            logger.error(f"Reverse dictionary lookup failed: {e}")
        
        # Step 3: Generate additional solution keywords using LLM
        solution_keywords = []
        try:
            prompt = f"""
            Given this {business_type} customer problem, suggest 3-5 product category keywords that could help solve it.
            
            Business context: {business_type}
            Domain keywords: {', '.join(domain_context)}
            Problem: {intent.primary_problem}
            Context: {', '.join(intent.context)}
            Symptoms: {', '.join(intent.symptoms)}
            
            Think about what types of products in this business domain could address this problem.
            Consider the product categories that would be available in a {business_type} business.
            
            Respond with 3-5 simple product category keywords:
            ["keyword1", "keyword2", "keyword3"]
            
            Focus on product types, not specific brands or models.
            """
            
            response = config_generator.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            
            result_text = response.text.strip()
            
            # Extract JSON array from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            elif "[" in result_text and "]" in result_text:
                # Extract just the array part
                start = result_text.find("[")
                end = result_text.rfind("]") + 1
                result_text = result_text[start:end]
            
            import json
            keywords = json.loads(result_text)
            
            # Validate and clean keywords
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.strip():
                    solution_keywords.append(keyword.strip())
            
            solution_keywords = solution_keywords[:5]  # Max 5 keywords
            logger.info(f"Generated solution keywords: {solution_keywords}")
            
        except Exception as e:
            logger.error(f"Solution keyword generation failed: {e}")
            # Generic fallback - use domain keywords if available
            if domain_context:
                solution_keywords = domain_context[:3]
            else:
                solution_keywords = ["products", "supplies"]
        
        # Step 4: Search for products using solution keywords
        keyword_results = []
        for keyword in solution_keywords:
            keyword_products = integration_manager.search_products(query=keyword)
            for product in keyword_products:
                keyword_results.append({
                    "product_id": product.id,
                    "name": product.title,
                    "description": product.description,
                    "price": product.price,
                    "availability": product.availability,
                    "match_type": "solution_keyword",
                    "match_reason": f"Keyword: {keyword}"
                })
        
        # Step 5: Get product details for reverse dictionary results
        reverse_dict_formatted = []
        for product_id in reverse_dict_results:
            product = integration_manager.get_product_by_id(product_id)
            if product:
                reverse_dict_formatted.append({
                    "product_id": product.id,
                    "name": product.title,
                    "description": product.description,
                    "price": product.price,
                    "availability": product.availability,
                    "match_type": "usage_scenario",
                    "match_reason": f"Pre-computed solution for: {intent.primary_problem}"
                })
        
        # Step 6: Combine and deduplicate results
        all_results = reverse_dict_formatted + keyword_results
        
        # Deduplicate by product_id (prioritize reverse dict results)
        seen_ids = set()
        final_results = []
        
        for result in all_results:
            if result["product_id"] not in seen_ids:
                seen_ids.add(result["product_id"])
                final_results.append(result)
        
        final_result = {
            "results": final_results[:10],  # Top 10 results
            "total": len(final_results),
            "intent": {
                "primary_problem": intent.primary_problem,
                "context": intent.context,
                "urgency": intent.urgency
            },
            "business_context": {
                "business_type": business_type,
                "domain_keywords": domain_context
            },
            "reverse_dict_matches": len(reverse_dict_formatted),
            "keyword_matches": len(keyword_results),
            "solution_keywords_used": solution_keywords
        }

        if tool_context:
            try:
                # Save intent search results as artifact
                artifact_content = json.dumps(final_result, indent=2)
                artifact_part = types.Part(text=artifact_content)
                version = tool_context.save_artifact("intent_search_results.json", artifact_part)
                logger.info(f"Saved intent search results as artifact version {version}")
                
                # Store artifact name in state for synthesizer
                tool_context.state["intent_results_artifact"] = "intent_search_results.json"
                
            except ValueError as e:
                logger.error(f"Error saving intent search artifact: {e}")
            except Exception as e:
                logger.error(f"Unexpected error saving intent search artifact: {e}")
        
        return {
            "message": f"Found {len(final_results)} problem-solving suggestions",
            "total": len(final_results),
            "intent_detected": intent.primary_problem,
            "preview": final_results[:3] if final_results else []
        }
        
    except Exception as e:
        logger.error(f"Intent search failed: {e}")
        return {
            "results": [],
            "error": str(e),
            "intent": None
        }

def load_search_results_from_artifacts(tool_context: ToolContext) -> dict:
    """
    Load search results from artifacts for the synthesizer agent.
    Following the pseudocode pattern for loading artifacts.
    
    Args:
        tool_context: ToolContext for artifact and state access
        
    Returns:
        Combined search results from both keyword and intent searches
    """
    logger.info("Loading search results from artifacts")
    
    keyword_results = None
    intent_results = None
    
    # Load keyword search results artifact
    keyword_artifact_name = tool_context.state.get("keyword_results_artifact")
    if keyword_artifact_name:
        try:
            artifact_part = tool_context.load_artifact(keyword_artifact_name)
            if artifact_part and artifact_part.text:
                keyword_results = json.loads(artifact_part.text)
                logger.info("Loaded keyword search results from artifact")
            else:
                logger.warning(f"Could not load keyword artifact or artifact has no text: {keyword_artifact_name}")
        except ValueError as e:
            logger.error(f"Artifact service error loading keyword results: {e}")
        except Exception as e:
            logger.error(f"Error loading keyword artifact: {e}")
    else:
        logger.warning("Keyword results artifact name not found in state")
    
    # Load intent search results artifact
    intent_artifact_name = tool_context.state.get("intent_results_artifact")
    if intent_artifact_name:
        try:
            artifact_part = tool_context.load_artifact(intent_artifact_name)
            if artifact_part and artifact_part.text:
                intent_results = json.loads(artifact_part.text)
                logger.info("Loaded intent search results from artifact")
            else:
                logger.warning(f"Could not load intent artifact or artifact has no text: {intent_artifact_name}")
        except ValueError as e:
            logger.error(f"Artifact service error loading intent results: {e}")
        except Exception as e:
            logger.error(f"Error loading intent artifact: {e}")
    else:
        logger.warning("Intent results artifact name not found in state")
    
    return {
        "keyword_results": keyword_results,
        "intent_results": intent_results,
        "status": "success" if (keyword_results or intent_results) else "no_results"
    }

def get_product_details(product_id: str) -> dict:
    """
    Get detailed information about a specific product.
    
    Args:
        product_id: ID of the product
        
    Returns:
        Dictionary with product details
    """
    logger.info(f"Getting product details for: {product_id}")
    
    try:
        # Get singleton integration manager instance
        integration_manager = IntegrationManager.get_instance()
        
        product = integration_manager.get_product_by_id(product_id)
        
        if not product:
            return {"error": f"Product {product_id} not found"}
        
        return {
            "product_id": product.id,
            "name": product.title,
            "description": product.description,
            "price": product.price,
            "compare_at_price": product.compare_at_price,
            "sku": product.sku,
            "inventory_quantity": product.inventory_quantity,
            "availability": product.availability,
            "tags": product.tags,
            "categories": product.categories,
            "images": product.images
        }
        
    except Exception as e:
        logger.error(f"Error getting product details: {e}")
        return {"error": str(e)}