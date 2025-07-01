# customer_service/integrations/elasticsearch/config_generator.py
"""LLM-based configuration generator for Elasticsearch search setup."""

import logging
import re
import json
import os
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai.types import HttpOptions
from ...database.models import StandardProduct
from ...config import Config

logger = logging.getLogger(__name__)

class SearchConfigGenerator(ABC):
    """Abstract base class for search configuration generators."""
    
    @abstractmethod
    def generate_config(self, sample_products: List[StandardProduct]) -> Dict:
        """Generate search configuration from sample products."""
        pass

class LLMConfigGenerator(SearchConfigGenerator):
    """Generates search configuration using LLM analysis of products."""
    
    def __init__(self, config: Config):
        self.config = config
        # Configure Gemini client for Vertex AI
        self.client = genai.Client(
            vertexai=True,
            project=config.CLOUD_PROJECT,
            location=config.CLOUD_LOCATION,
            http_options=HttpOptions(api_version="v1")
        )
        # Path to store the generated config
        self.config_file_path = Path(__file__).parent / "search_config.json"
    
    def generate_config(self, sample_products: List[StandardProduct]) -> Dict:
        """
        Analyze sample products with LLM to generate Elasticsearch config.
        
        Args:
            sample_products: List of up to 30 sample products
            
        Returns:
            Dictionary with search configuration
        """
        logger.info(f"Generating search config from {len(sample_products)} sample products")
        
        # Check if config already exists
        existing_config = self.load_config()
        if existing_config:
            logger.info("Using existing search config")
            return existing_config
        
        try:
            # Limit to 30 products max
            products_to_analyze = sample_products[:30]
            
            # Try category-based index name first
            index_name = self._generate_index_name(products_to_analyze)
            
            # Generate search config via LLM
            search_config = self._analyze_products_with_llm(products_to_analyze)
            
            # Combine results
            config = {
                "index_name": index_name,
                "business_type": search_config.get("business_type", "general"),
                "searchable_fields": search_config.get("searchable_fields", self._get_default_fields()),
                "synonym_groups": search_config.get("synonym_groups", []),
                "search_settings": search_config.get("search_settings", self._get_default_search_settings()),
                "domain_keywords": search_config.get("domain_keywords", [])
            }
            
            logger.info(f"Generated config for {config['business_type']} business")
            
            # Save config to JSON file
            self._save_config(config)
            
            return config
            
        except Exception as e:
            logger.error(f"Error generating config: {e}")
            return self._get_fallback_config()
    
    def _generate_index_name(self, products: List[StandardProduct]) -> str:
        """Generate index name from categories or LLM analysis."""
        
        # Extract Shopify categories
        all_categories = []
        for product in products:
            all_categories.extend(product.categories)
        
        if all_categories:
            # Find most common categories
            category_counts = {}
            for cat in all_categories:
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            # Get top categories
            top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Try to infer business type from categories
            business_type = self._categorize_business_from_categories([cat[0] for cat in top_categories])
            
            if business_type:
                return f"{self._clean_string(business_type)}_products"
        
        # Fallback to LLM analysis for business type
        try:
            business_type = self._llm_analyze_business_type(products)
            if business_type:
                return f"{self._clean_string(business_type)}_products"
        except Exception as e:
            logger.warning(f"LLM business type analysis failed: {e}")
        
        # Final fallback
        return "products"
    
    def _categorize_business_from_categories(self, categories: List[str]) -> Optional[str]:
        """Infer business type from Shopify categories."""
        categories_lower = [cat.lower() for cat in categories]
        
        # Garden center indicators
        garden_terms = ['garden', 'plant', 'seed', 'soil', 'fertilizer', 'flower', 'vegetable']
        if any(term in ' '.join(categories_lower) for term in garden_terms):
            return "garden"
        
        # Restaurant indicators  
        food_terms = ['food', 'menu', 'drink', 'beverage', 'appetizer', 'entree', 'dessert']
        if any(term in ' '.join(categories_lower) for term in food_terms):
            return "restaurant"
        
        # Electronics indicators
        tech_terms = ['electronics', 'computer', 'phone', 'tablet', 'audio', 'camera']
        if any(term in ' '.join(categories_lower) for term in tech_terms):
            return "electronics"
        
        # Clothing indicators
        clothing_terms = ['clothing', 'apparel', 'shirt', 'pants', 'dress', 'shoes']
        if any(term in ' '.join(categories_lower) for term in clothing_terms):
            return "clothing"
        
        return None
    
    def _llm_analyze_business_type(self, products: List[StandardProduct]) -> Optional[str]:
        """Use LLM to determine business type from products."""
        
        # Create sample for LLM
        product_sample = []
        for product in products[:5]:  # Just 5 for business type analysis
            product_sample.append({
                "title": product.title,
                "categories": product.categories,
                "tags": product.tags[:5]  # Limit tags
            })
        
        prompt = f"""
        Analyze these products and determine the business type in 1-2 words:
        
        Products: {json.dumps(product_sample, indent=2)}
        
        Respond with only the business type (examples: "garden", "restaurant", "electronics", "clothing", "books", "jewelry").
        Use simple, common terms. Max 2 words.
        """
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            business_type = response.text.strip().lower()
            
            # Clean and validate response
            business_type = self._clean_string(business_type)
            if len(business_type.split('_')) <= 2:  # Max 2 words
                return business_type
                
        except Exception as e:
            logger.error(f"LLM business type analysis failed: {e}")
        
        return None
    
    def _analyze_products_with_llm(self, products: List[StandardProduct]) -> Dict:
        """Use LLM to analyze products and generate search configuration."""
        
        # Prepare product data for LLM
        product_data = []
        for product in products:
            product_data.append({
                "title": product.title,
                "description": product.description[:200] if product.description else "",  # Truncate long descriptions
                "categories": product.categories,
                "tags": product.tags,
                "price": product.price
            })
        
        prompt = f"""
        Analyze these {len(products)} products and generate Elasticsearch search configuration.
        
        Products: {json.dumps(product_data, indent=2)}
        
        Generate a JSON response with:
        1. "business_type": What type of business this is (1-2 words)
        2. "searchable_fields": Which product fields should be searchable with boost weights (1.0-3.0)
        3. "synonym_groups": Arrays of synonymous terms customers might use (comma-separated)
        4. "domain_keywords": Key terms that describe this business domain
        5. "search_settings": Search behavior settings
        
        Example format:
        {{
            "business_type": "garden_center",
            "searchable_fields": {{
                "title": {{"weight": 3.0, "fuzzy": true}},
                "description": {{"weight": 1.5, "fuzzy": true}},
                "tags": {{"weight": 2.0, "fuzzy": false}},
                "categories": {{"weight": 1.8, "fuzzy": false}}
            }},
            "synonym_groups": [
                "fertilizer,plant food,nutrients,feed",
                "soil,dirt,potting mix,growing medium"
            ],
            "domain_keywords": ["gardening", "plants", "outdoor", "growing"],
            "search_settings": {{
                "fuzzy_distance": 2,
                "minimum_should_match": "75%",
                "boost_exact_matches": true
            }}
        }}
        
        Focus on:
        - Common misspellings and alternative terms customers use
        - Which fields are most important for finding products
        - Domain-specific terminology and synonyms
        
        Respond only with valid JSON.
        """
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            config_text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in config_text:
                config_text = config_text.split("```json")[1].split("```")[0]
            elif "```" in config_text:
                config_text = config_text.split("```")[1].split("```")[0]
            
            config = json.loads(config_text)
            logger.info("Successfully generated LLM search config")
            return config
            
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error parsing LLM response: {e}")
            return {}
    
    def _clean_string(self, text: str) -> str:
        """Clean string for index names and keys."""
        # Remove special characters, convert to lowercase, replace spaces with underscores
        cleaned = re.sub(r'[^a-zA-Z\s_]', '', text).lower().replace(' ', '_')
        # Limit length and remove extra underscores
        cleaned = re.sub(r'_+', '_', cleaned).strip('_')[:20]
        return cleaned
    
    def _get_default_fields(self) -> Dict:
        """Default searchable fields if LLM analysis fails."""
        return {
            "title": {"weight": 3.0, "fuzzy": True},
            "description": {"weight": 1.5, "fuzzy": True},
            "tags": {"weight": 2.0, "fuzzy": False},
            "categories": {"weight": 1.8, "fuzzy": False}
        }
    
    def _get_default_search_settings(self) -> Dict:
        """Default search settings."""
        return {
            "fuzzy_distance": 2,
            "minimum_should_match": "75%",
            "boost_exact_matches": True
        }
    
    def _get_fallback_config(self) -> Dict:
        """Fallback configuration if everything fails."""
        return {
            "index_name": "products",
            "business_type": "general",
            "searchable_fields": self._get_default_fields(),
            "synonym_groups": [],
            "search_settings": self._get_default_search_settings(),
            "domain_keywords": []
        }
    
    def load_config(self) -> Optional[Dict]:
        """Load existing search config from JSON file."""
        try:
            if self.config_file_path.exists():
                with open(self.config_file_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded existing search config: {config.get('business_type', 'unknown')}")
                return config
        except Exception as e:
            logger.error(f"Error loading search config: {e}")
        return None
    
    def _save_config(self, config: Dict):
        """Save generated config to JSON file."""
        try:
            # Ensure directory exists
            self.config_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save config with timestamp
            config_with_meta = {
                **config,
                "generated_at": str(datetime.now()),
                "product_count_analyzed": 30
            }
            
            with open(self.config_file_path, 'w') as f:
                json.dump(config_with_meta, f, indent=2)
                
            logger.info(f"Saved search config to {self.config_file_path}")
            
        except Exception as e:
            logger.error(f"Error saving search config: {e}")
    
    def config_exists(self) -> bool:
        """Check if search config file exists."""
        return self.config_file_path.exists()
    
    def regenerate_config(self, sample_products: List[StandardProduct]) -> Dict:
        """Force regeneration of config (ignores existing file)."""
        logger.info("Force regenerating search config...")
        return self.generate_config(sample_products)