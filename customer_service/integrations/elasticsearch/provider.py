# customer_service/integrations/elasticsearch/provider.py
"""Elasticsearch provider with vector embeddings support for ES 8.x"""

import logging
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch, helpers
from datetime import datetime
import asyncio
from google import genai
from google.genai.types import HttpOptions
import openai
from openai import OpenAI

from ...database.models import StandardProduct, IntentResult, ProblemVariation, ProductMatch
from ...config import Config
from .config_generator import LLMConfigGenerator

logger = logging.getLogger(__name__)

class ElasticsearchProvider:
    """Elasticsearch provider with vector embeddings for enhanced product search."""
    
    def __init__(self, config: Config):
        self.config = config
        
        # Initialize Elasticsearch client for ES 8.x
        self.es = Elasticsearch([config.ELASTICSEARCH_URL])
        
        # Initialize Gemini client for embeddings
        self.embedding_client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Load or generate search configuration
        config_generator = LLMConfigGenerator(config)
        self.search_config = config_generator.load_config()
        
        if not self.search_config:
            logger.info("No search config found, generating automatically...")
            self.search_config = config_generator.generate_config()
            
            if not self.search_config:
                raise ValueError("Failed to generate search configuration")
        
        self.index_name = self.search_config["index_name"]
        
        # Create index with vector field configuration
        self._create_index_with_vectors()
        
        logger.info(f"Initialized Elasticsearch provider with vector support for {self.search_config['business_type']}")

    def _create_index_with_vectors(self):
        """Create Elasticsearch index with vector field configuration for ES 8.x."""
        
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
        
        # Add vector fields for semantic search
        field_mappings["title_vector"] = {
            "type": "dense_vector",
            "dims": self.config.EMBEDDING_DIMENSIONS,  
            "index": True,
            "similarity": "cosine"
        }
        
        field_mappings["description_vector"] = {
            "type": "dense_vector", 
            "dims": self.config.EMBEDDING_DIMENSIONS,  
            "index": True,
            "similarity": "cosine"
        }
        
        field_mappings["usage_scenarios_vectors"] = {
            "type": "dense_vector",
            "dims": self.config.EMBEDDING_DIMENSIONS,  
            "index": True,
            "similarity": "cosine"
        }
        
        # Index configuration for ES 8.x
        index_config = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
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
                    # Common fields
                    "product_id": {"type": "keyword"},
                    "type": {"type": "keyword"},  # "product" or "scenario"
                    
                    # Product fields
                    "title": {"type": "text", "analyzer": "business_search_analyzer"},
                    "description": {"type": "text", "analyzer": "business_search_analyzer"},
                    "tags": {"type": "text", "analyzer": "business_search_analyzer"},
                    "categories": {"type": "text", "analyzer": "business_search_analyzer"},
                    "price": {"type": "float"},
                    "inventory_quantity": {"type": "integer"},
                    "availability": {"type": "boolean"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    
                    # Scenario fields
                    "scenario_text": {"type": "keyword"},
                    "scenario_vector": {
                        "type": "dense_vector",
                        "dims": self.config.EMBEDDING_DIMENSIONS,
                        "index": True,
                        "similarity": "cosine"
                    }
                }
            }
        }
        
        try:
            self.es.indices.create(index=self.index_name, body=index_config)
            logger.info(f"Created Elasticsearch index with vector support: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI text-embedding-3-large."""
        if not texts:
            return []
        
        try:
            response = self.embedding_client.embeddings.create(
                model=self.config.EMBEDDING_MODEL,
                input=texts,
                dimensions=self.config.EMBEDDING_DIMENSIONS
            )
            
            embeddings = [embedding.embedding for embedding in response.data]
            
            logger.debug(f"Generated {len(embeddings)} embeddings with dimension {len(embeddings[0]) if embeddings else 0}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate OpenAI embeddings: {e}")
            return []

    def _generate_product_embeddings(self, product: StandardProduct) -> Dict:
        """Generate all embeddings for a product."""
        embeddings = {}
        
        try:
            # Prepare texts for embedding
            texts_to_embed = []
            field_names = []
            
            # Title
            if product.title:
                texts_to_embed.append(product.title)
                field_names.append("title")
            
            # Description 
            if product.description:
                texts_to_embed.append(product.description)
                field_names.append("description")
            
            # Individual usage scenarios
            usage_scenario_texts = []
            for scenario in product.usage_scenarios:
                if scenario.strip():
                    texts_to_embed.append(scenario)
                    field_names.append("usage_scenario")
                    usage_scenario_texts.append(scenario)
            
            # Generate embeddings for all texts at once
            if texts_to_embed:
                all_embeddings = self._generate_embeddings(texts_to_embed)
                
                if len(all_embeddings) == len(texts_to_embed):
                    # Map embeddings back to fields
                    title_idx = None
                    description_idx = None
                    usage_scenarios_vectors = []
                    
                    for i, field_name in enumerate(field_names):
                        if field_name == "title" and title_idx is None:
                            title_idx = i
                        elif field_name == "description" and description_idx is None:
                            description_idx = i
                        elif field_name == "usage_scenario":
                            usage_scenarios_vectors.append(all_embeddings[i])
                    
                    # Store embeddings
                    if title_idx is not None:
                        embeddings["title_vector"] = all_embeddings[title_idx]
                    
                    if description_idx is not None:
                        embeddings["description_vector"] = all_embeddings[description_idx]
                    
                    if usage_scenarios_vectors:
                        embeddings["usage_scenarios_vectors"] = usage_scenarios_vectors
                    
                    logger.debug(f"Generated embeddings for product {product.id}: title={title_idx is not None}, desc={description_idx is not None}, scenarios={len(usage_scenarios_vectors)}")
                else:
                    logger.warning(f"Embedding count mismatch for product {product.id}")
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for product {product.id}: {e}")
        
        return embeddings

    def index_product(self, product: StandardProduct):
        """Index a single product with embeddings in Elasticsearch."""
        
        # Generate embeddings
        embeddings = self._generate_product_embeddings(product)
        
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
            "updated_at": product.updated_at,
            **embeddings  # Add all generated embeddings
        }
        
        try:
            self.es.index(
                index=self.index_name,
                id=product.id,
                body=doc
            )
            logger.debug(f"Indexed product with embeddings: {product.id}")
        except Exception as e:
            logger.error(f"Failed to index product {product.id}: {e}")

    def bulk_index_products(self, products: List[StandardProduct]):
        """Index products and their usage scenarios as separate documents."""
        
        def generate_docs():
            for product in products:
                # Generate title embedding for product
                title_embedding = None
                if product.title:
                    try:
                        title_embeddings = self._generate_embeddings([product.title])
                        title_embedding = title_embeddings[0] if title_embeddings else None
                    except Exception as e:
                        logger.error(f"Failed to generate title embedding for {product.id}: {e}")
                
                # 1. Index main product document with title vector
                product_doc = {
                    "_index": self.index_name,
                    "_id": f"product_{product.id}",
                    "_source": {
                        "product_id": product.id,
                        "type": "product",
                        "title": product.title,
                        "description": product.description or "",
                        "tags": " ".join(product.tags),
                        "categories": " ".join(product.categories),
                        "price": product.price,
                        "inventory_quantity": product.inventory_quantity,
                        "availability": product.availability,
                        "created_at": product.created_at,
                        "updated_at": product.updated_at
                    }
                }
                
                # Add title vector if generated
                if title_embedding:
                    product_doc["_source"]["title_vector"] = title_embedding
                
                yield product_doc
                
                # 2. Index scenario documents
                if product.usage_scenarios:
                    try:
                        scenario_embeddings = self._generate_embeddings(product.usage_scenarios)
                        
                        for i, (scenario, embedding) in enumerate(zip(product.usage_scenarios, scenario_embeddings)):
                            yield {
                                "_index": self.index_name,
                                "_id": f"scenario_{product.id}_{i}",
                                "_source": {
                                    "product_id": product.id,
                                    "type": "scenario",
                                    "scenario_text": scenario,
                                    "scenario_vector": embedding
                                }
                            }
                    except Exception as e:
                        logger.error(f"Failed to generate scenario embeddings for product {product.id}: {e}")
                        continue
        
        try:
            success_count, failed = helpers.bulk(self.es, generate_docs())
            
            if failed:
                logger.error(f"Failed to index {len(failed)} documents")
                for failure in failed:
                    logger.error(f"Failed doc: {failure}")
            
            logger.info(f"Bulk indexed {success_count} documents, {len(failed)} failed")
            return success_count
            
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            return 0

    # Keep existing methods but add vector search capabilities
    def search_products(self, query: str = None, category: str = None, 
                       price_min: float = None, price_max: float = None,
                       in_stock_only: bool = False, **filters) -> List[StandardProduct]:
        """Search products using keyword search (unchanged for compatibility)."""
        
        searchable_fields = self.search_config.get("searchable_fields", {})
        search_settings = self.search_config.get("search_settings", {})
        
        # Build search query (existing logic)
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
        
        # Add filters (existing logic)
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

    # Continue with rest of the existing methods...
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

    def search_by_intent_with_vectors(self, query: str, **kwargs) -> List[ProductMatch]:
        """Search products using vector embeddings + intent analysis (updated for nested documents)."""
        
        try:
            # Step 1: Analyze user intent (keep existing logic)
            config_generator = LLMConfigGenerator(self.config)
            intent = config_generator.analyze_intent(query)
            problem_variations = config_generator.expand_problems(intent)
            
            logger.info(f"Intent analysis: {intent.primary_problem}, {len(problem_variations)} variations")
            
            # Step 2: Generate embeddings for problem variations
            problem_texts = [var.problem for var in problem_variations]
            problem_embeddings = self._generate_embeddings(problem_texts)
            
            if not problem_embeddings:
                logger.warning("Could not generate embeddings, falling back to keyword search")
                return self._fallback_keyword_intent_search(query, problem_variations, **kwargs)
            
            # Step 3: Search scenario documents using vector similarity
            all_matches = []
            
            for problem_var, embedding in zip(problem_variations, problem_embeddings):
                search_body = {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"type": "scenario"}},  # Only scenario documents
                                {
                                    "script_score": {
                                        "query": {"match_all": {}},
                                        "script": {
                                            "source": "cosineSimilarity(params.query_vector, 'scenario_vector') + 1.0",
                                            "params": {"query_vector": embedding}
                                        }
                                    }
                                }
                            ],
                            "filter": []
                        }
                    },
                    "size": 10,
                    "_source": ["product_id", "scenario_text"]
                }
                
                # Add availability filter if requested
                if kwargs.get("in_stock_only", False):
                    # Need to check product documents for inventory
                    search_body["query"]["bool"]["filter"].append({
                        "exists": {"field": "product_id"}  # Basic filter for now
                    })
                
                try:
                    response = self.es.search(index=self.index_name, body=search_body)
                    
                    # Process results
                    for hit in response["hits"]["hits"]:
                        source = hit["_source"]
                        score = hit["_score"]
                        
                        # Create ProductMatch
                        match = ProductMatch(
                            product_id=source["product_id"],
                            product_title="",  # Will fill this in next step
                            confidence=min(score / 2.0, 1.0) * problem_var.confidence,  # Normalize score
                            reasons=[f"scenario_match: {source['scenario_text']}"],
                            price=0.0  # Will fill this in next step
                        )
                        
                        all_matches.append(match)
                        
                except Exception as e:
                    logger.error(f"Vector search failed for problem {problem_var.problem}: {e}")
                    continue
            
            # Step 4: Group by product_id and get product details
            product_groups = {}
            for match in all_matches:
                if match.product_id not in product_groups:
                    product_groups[match.product_id] = []
                product_groups[match.product_id].append(match)
            
            # Step 5: Get product details and create final matches
            final_matches = []
            for product_id, matches in product_groups.items():
                # Get product details
                product_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"type": "product"}},
                                {"term": {"product_id": product_id}}
                            ]
                        }
                    },
                    "size": 1
                }
                
                try:
                    product_response = self.es.search(index=self.index_name, body=product_query)
                    
                    if product_response["hits"]["hits"]:
                        product_doc = product_response["hits"]["hits"][0]["_source"]
                        
                        # Use best confidence score from all scenario matches
                        best_confidence = max(m.confidence for m in matches)
                        all_reasons = []
                        for m in matches:
                            all_reasons.extend(m.reasons)
                        
                        final_match = ProductMatch(
                            product_id=product_id,
                            product_title=product_doc.get("title", ""),
                            confidence=best_confidence,
                            reasons=list(set(all_reasons))[:3],  # Unique reasons, max 3
                            price=product_doc.get("price", 0.0)
                        )
                        
                        final_matches.append(final_match)
                        
                except Exception as e:
                    logger.error(f"Failed to get product details for {product_id}: {e}")
                    continue
            
            # Step 6: Sort by confidence and return top results
            ranked_matches = sorted(final_matches, key=lambda x: x.confidence, reverse=True)
            logger.info(f"Vector search returned {len(ranked_matches)} matches")
            return ranked_matches[:10]
            
        except Exception as e:
            logger.error(f"Intent vector search failed: {e}")
            return self._fallback_keyword_intent_search(query, problem_variations, **kwargs)

    def _fallback_keyword_intent_search(self, query: str, problem_variations: List[ProblemVariation], **kwargs) -> List[ProductMatch]:
        """Fallback to keyword-based intent search if vector search fails."""
        logger.info("Using keyword fallback for intent search")
        
        all_matches = []
        
        for problem_var in problem_variations:
            # Search for products with matching usage scenarios (keyword)
            search_body = {
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"usage_scenarios.keyword": problem_var.problem}},
                            {"match": {"usage_scenarios": {"query": problem_var.problem, "fuzziness": "AUTO"}}}
                        ],
                        "filter": []
                    }
                },
                "size": 10,
                "_source": ["product_id", "title", "price", "usage_scenarios", "availability"]
            }
            
            if kwargs.get("in_stock_only", False):
                search_body["query"]["bool"]["filter"].append({
                    "range": {"inventory_quantity": {"gt": 0}}
                })
            
            try:
                response = self.es.search(index=self.index_name, body=search_body)
                
                for hit in response["hits"]["hits"]:
                    source = hit["_source"]
                    
                    confidence = problem_var.confidence * (hit["_score"] / 10.0)
                    
                    match = ProductMatch(
                        product_id=source["product_id"],
                        product_title=source["title"],
                        confidence=min(confidence, 1.0),
                        reasons=[f"keyword_match: {problem_var.problem}"],
                        price=source.get("price", 0.0)
                    )
                    
                    all_matches.append(match)
                    
            except Exception as e:
                logger.error(f"Keyword search failed for problem {problem_var.problem}: {e}")
                continue
        
        # Return top matches
        ranked_matches = sorted(all_matches, key=lambda x: x.confidence, reverse=True)
        return ranked_matches[:10]

    # Update the existing search_by_intent method to use vectors
    def search_by_intent(self, query: str, **kwargs) -> List[ProductMatch]:
        """Search products using intent analysis with vector embeddings (primary method)."""
        return self.search_by_intent_with_vectors(query, **kwargs)

    def sync_from_provider(self, source_provider):
        """Sync products from another provider to Elasticsearch with embeddings."""
        logger.info("Starting product sync to Elasticsearch with embeddings...")
        
        try:
            # Get all products from source provider
            products = source_provider.search_products()
            
            if products:
                # Generate usage scenarios if needed
                logger.info("Checking usage scenarios...")
                config_generator = LLMConfigGenerator(self.config)
                usage_scenarios_map = config_generator.load_usage_scenarios()
                
                if not usage_scenarios_map:
                    logger.info("Generating usage scenarios for products...")
                    usage_scenarios_map = config_generator.generate_usage_scenarios(products)
                    if usage_scenarios_map:
                        config_generator._save_usage_scenarios(usage_scenarios_map)
                
                # Update products with usage scenarios
                for product in products:
                    if usage_scenarios_map and product.id in usage_scenarios_map:
                        product.usage_scenarios = usage_scenarios_map[product.id]
                    else:
                        product.usage_scenarios = ["general_gardening"]
                
                # Index products with embeddings
                indexed_count = self.bulk_index_products(products)
                logger.info(f"Synced {indexed_count} products to Elasticsearch with embeddings")
                return indexed_count
            else:
                logger.warning("No products found to sync")
                return 0
                
        except Exception as e:
            logger.error(f"Sync with embeddings failed: {e}")
            return 0