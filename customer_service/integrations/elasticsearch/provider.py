# customer_service/integrations/elasticsearch/provider.py
"""Clean Elasticsearch provider - basic search, indexing, and config storage."""

import logging
from typing import List, Dict, Optional
from elasticsearch import Elasticsearch, helpers
from datetime import datetime

from ...database.models import StandardProduct
from ...config import Config

logger = logging.getLogger(__name__)

class ElasticsearchProvider:
    """Elasticsearch provider for basic product search, indexing, and config storage."""
    
    def __init__(self, config: Config):
        self.config = config
        
        # Initialize Elasticsearch client
        self.es = Elasticsearch(
            [config.ELASTICSEARCH_URL],
            basic_auth=(config.ELASTICSEARCH_USER, config.ELASTICSEARCH_PASSWORD)
        )
        
        # Load search configuration (lazy to avoid circular imports)
        self.search_config = None
        self.index_name = None
        self._initialize_search_config()
        
        # Create index if needed
        self._create_index()
        
        logger.info(f"Initialized Elasticsearch provider for {self.search_config['business_type']}")

    def _initialize_search_config(self):
        """Initialize search config with lazy loading to avoid circular imports."""
        self.index_name = f"store_{self.config.BUSINESS_ID}_products"
        # First try to load existing config
        self.search_config = self.load_search_config()
        
        if not self.search_config:
            logger.info("No search config found, using fallback for startup...")
            self.search_config = self._get_fallback_config()
        

    def _get_fallback_config(self):
        """Fallback configuration for startup."""
        return {
            "index_name": self.index_name,
            "business_type": "general", 
            "searchable_fields": {
                "title": {"weight": 3.0, "fuzzy": True},
                "description": {"weight": 1.5, "fuzzy": True},
                "tags": {"weight": 2.0, "fuzzy": False},
                "categories": {"weight": 1.8, "fuzzy": False}
            },
            "synonym_groups": [],
            "search_settings": {
                "fuzzy_distance": 2,
                "minimum_should_match": "75%",
                "boost_exact_matches": True
            },
            "domain_keywords": []
        }

    # ============= CONFIG STORAGE METHODS =============
    
    def save_config_document(self, config_name: str, data: dict) -> bool:
        """Save a config document to the same index as products."""
        try:
            doc = {
                "type": "config",
                "config_name": config_name,
                "business_id": self.config.BUSINESS_ID,
                "data": data,
                "updated_at": datetime.now().isoformat()
            }
            config_id = f"config_{self.config.BUSINESS_ID}_{config_name}"

            self.es.index(
                index=self.index_name,
                id=config_id,
                body=doc
            )
            
            logger.info(f"Saved config '{config_name}' to Elasticsearch")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config '{config_name}': {e}")
            return False

    def load_config_document(self, config_name: str) -> Optional[dict]:
        """Load a config document from Elasticsearch."""
        try:
            response = self.es.get(
                index=self.index_name,
                id=f"config_{config_name}"
            )
            
            config_data = response["_source"]["data"]
            logger.info(f"Loaded config '{config_name}' from Elasticsearch")
            return config_data
            
        except Exception as e:
            logger.debug(f"Config '{config_name}' not found in Elasticsearch: {e}")
            return None

    def config_exists(self, config_name: str) -> bool:
        """Check if a config document exists in Elasticsearch."""
        try:
            self.es.get(index=self.index_name, id=f"config_{config_name}")
            return True
        except:
            return False

    def list_configs(self) -> List[str]:
        """List all config documents in the index."""
        try:
            search_body = {
                "query": {"term": {"type": "config"}},
                "size": 100,
                "_source": ["config_name"]
            }
            
            response = self.es.search(index=self.index_name, body=search_body)
            
            configs = []
            for hit in response["hits"]["hits"]:
                configs.append(hit["_source"]["config_name"])
            
            return configs
            
        except Exception as e:
            logger.error(f"Failed to list configs: {e}")
            return []

    # ============= CONVENIENCE METHODS FOR SPECIFIC CONFIGS =============
    
    def save_search_config(self, config: dict) -> bool:
        """Save search configuration."""
        return self.save_config_document("search_config", config)

    def load_search_config(self) -> Optional[dict]:
        """Load search configuration."""
        return self.load_config_document("search_config")

    def save_usage_scenarios(self, scenarios: dict) -> bool:
        """Save usage scenarios."""
        return self.save_config_document("usage_scenarios", scenarios)

    def load_usage_scenarios(self) -> Optional[dict]:
        """Load usage scenarios."""
        return self.load_config_document("usage_scenarios")

    def save_reverse_dictionary(self, reverse_dict: dict) -> bool:
        """Save reverse dictionary."""
        return self.save_config_document("reverse_dictionary", reverse_dict)

    def load_reverse_dictionary(self) -> Optional[dict]:
        """Load reverse dictionary."""
        return self.load_config_document("reverse_dictionary")

    # ============= INDEX MANAGEMENT =============

    def _create_index(self):
        """Create Elasticsearch index with proper configuration."""
        
        if self.es.indices.exists(index=self.index_name):
            logger.info(f"Index {self.index_name} already exists")
            return
        
        # Build synonym filter from generated config
        synonyms = self.search_config.get("synonym_groups", [])
        
        # Index configuration
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
                    # Product fields
                    "type": {"type": "keyword"},  # NEW: distinguish products vs configs
                    "product_id": {"type": "keyword"},
                    "title": {"type": "text", "analyzer": "business_search_analyzer"},
                    "description": {"type": "text", "analyzer": "business_search_analyzer"},
                    "tags": {"type": "text", "analyzer": "business_search_analyzer"},
                    "categories": {"type": "text", "analyzer": "business_search_analyzer"},
                    "price": {"type": "float"},
                    "inventory_quantity": {"type": "integer"},
                    "availability": {"type": "boolean"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    
                    # Config fields
                    "config_name": {"type": "keyword"},
                    "data": {"type": "object", "enabled": False}  # Store config data as-is
                }
            }
        }
        
        try:
            self.es.indices.create(index=self.index_name, body=index_config)
            logger.info(f"Created Elasticsearch index: {self.index_name}")
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise

    # ============= PRODUCT SEARCH METHODS =============

    def search_products(self, query: str = None, category: str = None, 
                       price_min: float = None, price_max: float = None,
                       in_stock_only: bool = False, **filters) -> List[StandardProduct]:
        """Search products using keyword search."""
        
        searchable_fields = self.search_config.get("searchable_fields", {})
        search_settings = self.search_config.get("search_settings", {})
        
        # Build search query
        search_body = {
            "query": {
                "bool": {
                    "must": [],
                    "filter": [
                        {"term": {"type": "product"}}  # Only search products, not configs
                    ]
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
        
        # If no query, match all products
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
                    usage_scenarios=[],  # Not stored in basic ES
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

    def get_product_by_id(self, product_id: str) -> Optional[StandardProduct]:
        """Get specific product by ID from Elasticsearch."""
        try:
            response = self.es.get(index=self.index_name, id=product_id)
            source = response["_source"]
            
            # Make sure it's a product, not a config
            if source.get("type") != "product":
                return None
            
            return StandardProduct(
                id=source["product_id"],
                title=source["title"],
                description=source["description"],
                price=source["price"],
                inventory_quantity=source["inventory_quantity"],
                availability=source["availability"],
                tags=source["tags"].split() if source["tags"] else [],
                categories=source["categories"].split() if source["categories"] else [],
                usage_scenarios=[],
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

    # ============= PRODUCT INDEXING METHODS =============

    def index_product(self, product: StandardProduct):
        """Index a single product in Elasticsearch."""
        
        doc = {
            "type": "product",  # NEW: mark as product
            "product_id": product.id,
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
        """Bulk index products in Elasticsearch."""
        
        def generate_docs():
            for product in products:
                yield {
                    "_index": self.index_name,
                    "_id": product.id,
                    "_source": {
                        "type": "product",  # NEW: mark as product
                        "product_id": product.id,
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

    def sync_from_provider(self, source_provider):
        """Sync products from another provider to Elasticsearch."""
        logger.info("Starting product sync to Elasticsearch...")
        
        try:
            # Get all products from source provider
            products = source_provider.search_products()
            
            if products:
                # Index products
                indexed_count = self.bulk_index_products(products)
                logger.info(f"Synced {indexed_count} products to Elasticsearch")
                return indexed_count
            else:
                logger.warning("No products found to sync")
                return 0
                
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return 0

    def get_search_suggestions(self, query: str, size: int = 5) -> List[str]:
        """Get search suggestions based on query."""
        # Simple implementation - could be enhanced
        try:
            search_body = {
                "suggest": {
                    "product_suggest": {
                        "prefix": query,
                        "completion": {
                            "field": "title.suggest",
                            "size": size
                        }
                    }
                }
            }
            
            response = self.es.search(index=self.index_name, body=search_body)
            suggestions = []
            
            for suggestion in response.get("suggest", {}).get("product_suggest", []):
                for option in suggestion.get("options", []):
                    suggestions.append(option["text"])
            
            return suggestions[:size]
            
        except Exception as e:
            logger.error(f"Search suggestions failed: {e}")
            return []