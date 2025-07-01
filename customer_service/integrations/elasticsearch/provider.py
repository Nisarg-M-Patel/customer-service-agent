# customer_service/integrations/elasticsearch/provider.py
"""Elasticsearch provider for advanced product search with intent analysis."""

import logging
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
from ...database.models import StandardProduct, IntentResult, ProblemVariation, ProductMatch
from ...config import Config
from .config_generator import LLMConfigGenerator

logger = logging.getLogger(__name__)

class ElasticsearchProvider:
    """Elasticsearch provider for enhanced product search capabilities with intent analysis."""
    
    def __init__(self, config: Config):
        self.config = config
        
        # Initialize Elasticsearch client
        self.es = Elasticsearch([config.ELASTICSEARCH_URL])
        
        # Load or generate search configuration
        config_generator = LLMConfigGenerator(config)
        self.search_config = config_generator.load_config()
        
        if not self.search_config:
            logger.info("No search config found, generating automatically...")
            self.search_config = config_generator.generate_config()  # Auto-fetch products
            
            if not self.search_config:
                raise ValueError("Failed to generate search configuration")
        
        self.index_name = self.search_config["index_name"]
        
        # Create index with configuration
        self._create_index()
        
        logger.info(f"Initialized Elasticsearch provider for {self.search_config['business_type']}")

    def _create_index(self):
        """Create Elasticsearch index with business-specific configuration including usage scenarios."""
        
        if self.es.indices.exists(index=self.index_name):
            logger.info(f"Index {self.index_name} already exists")
            return
        
        # Build synonym filter from generated config
        synonyms = self.search_config.get("synonym_groups", [])
        
        # Build field mappings from generated config
        searchable_fields = self.search_config.get("searchable_fields", {})
        field_mappings = {}
        
        for field_name, field_config in searchable_fields.items():
            field_mappings[field_name] = {
                "type": "text",
                "analyzer": "business_search_analyzer"
            }
            
            # Add keyword field for exact matching
            if field_name in ["tags", "categories"]:
                field_mappings[field_name]["fields"] = {
                    "keyword": {"type": "keyword"}
                }
        
        # Add usage scenarios field for intent search
        field_mappings["usage_scenarios"] = {
            "type": "text",
            "analyzer": "business_search_analyzer",
            "fields": {
                "keyword": {"type": "keyword"}
            }
        }
        
        # Index configuration
        index_config = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,  # For development
                "analysis": {
                    "filter": {
                        "business_synonym_filter": {
                            "type": "synonym",
                            "synonyms": synonyms
                        }
                    },
                    "analyzer": {
                        "business_search_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "business_synonym_filter"
                            ]
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "product_id": {"type": "keyword"},
                    "price": {"type": "float"},
                    "inventory_quantity": {"type": "integer"},
                    "availability": {"type": "boolean"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    **field_mappings
                }
            }
        }
        
        try:
            self.es.indices.create(index=self.index_name, body=index_config)
            logger.info(f"Created Elasticsearch index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise
    
    def index_product(self, product: StandardProduct):
        """Index a single product in Elasticsearch."""
        
        doc = {
            "product_id": product.id,
            "title": product.title,
            "description": product.description or "",
            "tags": " ".join(product.tags),
            "categories": " ".join(product.categories),
            "usage_scenarios": " ".join(product.usage_scenarios),
            "price": product.price,
            "inventory_quantity": product.inventory_quantity,
            "availability": product.availability,
            "created_at": product.created_at,
            "updated_at": product.updated_at
        }
        
        try:
            self.es.index(
                index=self.index_name,
                id=product.id,
                body=doc
            )
            logger.debug(f"Indexed product: {product.id}")
        except Exception as e:
            logger.error(f"Failed to index product {product.id}: {e}")
    
    def bulk_index_products(self, products: List[StandardProduct]):
        """Bulk index multiple products."""
        
        def generate_docs():
            for product in products:
                yield {
                    "_index": self.index_name,
                    "_id": product.id,
                    "_source": {
                        "product_id": product.id,
                        "title": product.title,
                        "description": product.description or "",
                        "tags": " ".join(product.tags),
                        "categories": " ".join(product.categories),
                        "usage_scenarios": " ".join(product.usage_scenarios),
                        "price": product.price,
                        "inventory_quantity": product.inventory_quantity,
                        "availability": product.availability,
                        "created_at": product.created_at,
                        "updated_at": product.updated_at
                    }
                }
        
        try:
            success_count, failed = helpers.bulk(self.es, generate_docs())
            logger.info(f"Bulk indexed {success_count} products, {len(failed)} failed")
            return success_count
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            return 0
    
    def search_products(self, query: str = None, category: str = None, 
                       price_min: float = None, price_max: float = None,
                       in_stock_only: bool = False, **filters) -> List[StandardProduct]:
        """Search products using generated configuration (keyword search)."""
        
        searchable_fields = self.search_config.get("searchable_fields", {})
        search_settings = self.search_config.get("search_settings", {})
        
        # Build search query
        search_body = {
            "query": {
                "bool": {
                    "must": [],
                    "filter": []
                }
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {"inventory_quantity": {"order": "desc"}}
            ],
            "size": self.config.MAX_SEARCH_RESULTS or 20
        }
        
        # Add text search if query provided
        if query:
            # Build multi-match query with field weights from config
            fields_with_weights = []
            for field_name, field_config in searchable_fields.items():
                weight = field_config.get("weight", 1.0)
                fields_with_weights.append(f"{field_name}^{weight}")
            
            search_body["query"]["bool"]["must"].append({
                "multi_match": {
                    "query": query,
                    "fields": fields_with_weights,
                    "type": "best_fields",
                    "fuzziness": "AUTO" if search_settings.get("fuzzy_distance", 2) > 0 else "0",
                    "minimum_should_match": search_settings.get("minimum_should_match", "60%")
                }
            })
        
        # Add filters
        if category:
            search_body["query"]["bool"]["filter"].append({
                "match": {"categories": category}
            })
        
        if price_min is not None or price_max is not None:
            price_range = {}
            if price_min is not None:
                price_range["gte"] = price_min
            if price_max is not None:
                price_range["lte"] = price_max
            
            search_body["query"]["bool"]["filter"].append({
                "range": {"price": price_range}
            })
        
        if in_stock_only:
            search_body["query"]["bool"]["filter"].append({
                "range": {"inventory_quantity": {"gt": 0}}
            })
        
        # If no query, match all
        if not search_body["query"]["bool"]["must"]:
            search_body["query"]["bool"]["must"].append({"match_all": {}})
        
        try:
            response = self.es.search(index=self.index_name, body=search_body)
            
            products = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                
                # Convert back to StandardProduct
                product = StandardProduct(
                    id=source["product_id"],
                    title=source["title"],
                    description=source["description"],
                    price=source["price"],
                    inventory_quantity=source["inventory_quantity"],
                    availability=source["availability"],
                    tags=source["tags"].split() if source["tags"] else [],
                    categories=source["categories"].split() if source["categories"] else [],
                    usage_scenarios=source.get("usage_scenarios", "").split() if source.get("usage_scenarios") else [],
                    images=[],  # Images not stored in ES
                    created_at=source["created_at"],
                    updated_at=source["updated_at"]
                )
                products.append(product)
            
            logger.info(f"Keyword search returned {len(products)} products for query: '{query}'")
            return products
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_by_intent(self, query: str, **kwargs) -> List[ProductMatch]:
        """Search products using intent analysis and problem matching."""
        
        try:
            # Initialize config generator for intent analysis
            config_generator = LLMConfigGenerator(self.config)
            
            # Step 1: Analyze user intent
            intent = config_generator.analyze_intent(query)
            logger.info(f"Analyzed intent: {intent.primary_problem}")
            
            # Step 2: Expand to related problems
            problem_variations = config_generator.expand_problems(intent)
            logger.info(f"Expanded to {len(problem_variations)} problem variations")
            
            # Step 3: Search for products that solve these problems
            all_matches = []
            
            for problem_var in problem_variations:
                # Search for products with matching usage scenarios
                search_body = {
                    "query": {
                        "bool": {
                            "should": [
                                # Exact match on usage scenarios
                                {
                                    "term": {
                                        "usage_scenarios.keyword": problem_var.problem
                                    }
                                },
                                # Fuzzy match on usage scenarios
                                {
                                    "match": {
                                        "usage_scenarios": {
                                            "query": problem_var.problem,
                                            "fuzziness": "AUTO"
                                        }
                                    }
                                }
                            ],
                            "filter": []
                        }
                    },
                    "size": 10,
                    "_source": ["product_id", "title", "price", "usage_scenarios", "availability"]
                }
                
                # Add availability filter if requested
                if kwargs.get("in_stock_only", False):
                    search_body["query"]["bool"]["filter"].append({
                        "range": {"inventory_quantity": {"gt": 0}}
                    })
                
                try:
                    response = self.es.search(index=self.index_name, body=search_body)
                    
                    for hit in response["hits"]["hits"]:
                        source = hit["_source"]
                        
                        # Calculate confidence score
                        base_confidence = problem_var.confidence
                        relevance_score = hit["_score"] / 10.0  # Normalize ES score
                        final_confidence = min(base_confidence * relevance_score, 1.0)
                        
                        match = ProductMatch(
                            product_id=source["product_id"],
                            product_title=source["title"],
                            confidence=final_confidence,
                            reasons=[f"Solves {problem_var.problem}"],
                            price=source.get("price", 0.0)
                        )
                        
                        all_matches.append(match)
                        
                except Exception as e:
                    logger.error(f"Search failed for problem {problem_var.problem}: {e}")
                    continue
            
            # Step 4: Aggregate and rank results
            return self._aggregate_matches(all_matches)
            
        except Exception as e:
            logger.error(f"Intent search failed: {e}")
            return []

    def _aggregate_matches(self, matches: List[ProductMatch]) -> List[ProductMatch]:
        """Aggregate multiple matches for same product and rank by confidence."""
        
        # Group matches by product_id
        product_matches = {}
        
        for match in matches:
            if match.product_id in product_matches:
                # Combine confidence scores and reasons
                existing = product_matches[match.product_id]
                existing.confidence = max(existing.confidence, match.confidence)
                existing.reasons.extend(match.reasons)
            else:
                product_matches[match.product_id] = match
        
        # Sort by confidence score (highest first)
        ranked_matches = sorted(
            product_matches.values(), 
            key=lambda x: x.confidence, 
            reverse=True
        )
        
        return ranked_matches[:10]  # Return top 10
    
    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get specific product by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index_name, id=product_id)
            source = response["_source"]
            
            return StandardProduct(
                id=source["product_id"],
                title=source["title"],
                description=source["description"],
                price=source["price"],
                inventory_quantity=source["inventory_quantity"],
                availability=source["availability"],
                tags=source["tags"].split() if source["tags"] else [],
                categories=source["categories"].split() if source["categories"] else [],
                usage_scenarios=source.get("usage_scenarios", "").split() if source.get("usage_scenarios") else [],
                images=[],
                created_at=source["created_at"],
                updated_at=source["updated_at"]
            )
            
        except Exception as e:
            logger.error(f"Failed to get product {product_id}: {e}")
            return None
    
    def check_inventory(self, product_id: str) -> Dict:
        """Check product inventory in Elasticsearch."""
        product = self.get_product_by_id(product_id)
        if not product:
            return {"available": False, "error": "Product not found"}
        
        return {
            "available": product.inventory_quantity > 0,
            "quantity": product.inventory_quantity,
            "product_name": product.title
        }
    
    def get_search_suggestions(self, query: str, size: int = 5) -> List[str]:
        """Get search suggestions/autocomplete."""
        try:
            # Simple completion based on product titles
            search_body = {
                "suggest": {
                    "title_suggest": {
                        "text": query,
                        "term": {
                            "field": "title",
                            "size": size
                        }
                    }
                }
            }
            
            response = self.es.search(index=self.index_name, body=search_body)
            suggestions = []
            
            for suggestion in response.get("suggest", {}).get("title_suggest", []):
                for option in suggestion.get("options", []):
                    suggestions.append(option["text"])
            
            return suggestions[:size]
            
        except Exception as e:
            logger.error(f"Failed to get suggestions: {e}")
            return []
    
    def sync_from_provider(self, source_provider):
        """Sync products from another provider (like Shopify) to Elasticsearch."""
        logger.info("Starting product sync to Elasticsearch...")
        
        try:
            # Get all products from source provider
            products = source_provider.search_products()  # Get all products
            
            if products:
                # Generate usage scenarios for all products before indexing
                logger.info("Generating usage scenarios for products...")
                config_generator = LLMConfigGenerator(self.config)
                usage_scenarios_map = config_generator.generate_usage_scenarios(products)
                
                # Save scenarios to file for persistence
                if usage_scenarios_map:
                    config_generator._save_usage_scenarios(usage_scenarios_map)
                    logger.info(f"Saved usage scenarios to file for {len(usage_scenarios_map)} products")
                
                # Update products with usage scenarios
                for product in products:
                    if product.id in usage_scenarios_map:
                        product.usage_scenarios = usage_scenarios_map[product.id]
                    else:
                        product.usage_scenarios = ["general_gardening"]
                
                # Index products with usage scenarios
                indexed_count = self.bulk_index_products(products)
                logger.info(f"Synced {indexed_count} products to Elasticsearch with usage scenarios")
                return indexed_count
            else:
                logger.warning("No products found to sync")
                return 0
                
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return 0
        
    def update_product_usage_scenarios(self, product_id: str, usage_scenarios: List[str]):
        """Update usage scenarios for a specific product."""
        
        try:
            self.es.update(
                index=self.index_name,
                id=product_id,
                body={
                    "doc": {
                        "usage_scenarios": " ".join(usage_scenarios)
                    }
                }
            )
            logger.info(f"Updated usage scenarios for product {product_id}")
            
        except Exception as e:
            logger.error(f"Failed to update usage scenarios for {product_id}: {e}")

    def bulk_update_usage_scenarios(self, usage_scenarios_map: Dict[str, List[str]]):

        """Bulk update usage scenarios for multiple products."""
        
        def generate_updates():
            for product_id, scenarios in usage_scenarios_map.items():
                yield {
                    "_op_type": "update",
                    "_index": self.index_name,
                    "_id": product_id,
                    "doc": {
                        "usage_scenarios": " ".join(scenarios)
                    }
                }
        
        try:
            success_count, failed = helpers.bulk(self.es, generate_updates())
            logger.info(f"Bulk updated usage scenarios: {success_count} success, {len(failed)} failed")
            return success_count
            
        except Exception as e:
            logger.error(f"Bulk usage scenario update failed: {e}")
            return 0
    
    
    def _ensure_usage_scenarios_exist(self):
        """Ensure usage scenarios exist, generate them if they don't."""
        try:
            config_generator = LLMConfigGenerator(self.config)
            
            if not config_generator.usage_scenarios_exist():
                logger.info("Usage scenarios don't exist, generating automatically...")
                
                # Get products from the primary provider
                from ..manager import IntegrationManager
                integration_manager = IntegrationManager(self.config)
                primary_provider = integration_manager._get_primary_provider()
                
                # Get all products
                products = primary_provider.search_products()
                
                if products:
                    # Generate usage scenarios
                    usage_scenarios_map = config_generator.generate_usage_scenarios(products)
                    
                    if usage_scenarios_map:
                        # Update existing products in Elasticsearch with usage scenarios
                        self.bulk_update_usage_scenarios(usage_scenarios_map)
                        logger.info(f"Auto-generated usage scenarios for {len(usage_scenarios_map)} products")
                    else:
                        logger.warning("Failed to generate usage scenarios")
                else:
                    logger.warning("No products found to generate usage scenarios")
                    
        except Exception as e:
            logger.error(f"Auto usage scenario generation failed: {e}")
            # Don't fail initialization, just log the error