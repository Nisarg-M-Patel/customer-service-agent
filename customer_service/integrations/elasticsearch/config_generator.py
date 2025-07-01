# customer_service/integrations/elasticsearch/config_generator.py
"""LLM-based configuration generator for Elasticsearch search setup with automatic initialization."""

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
from ...database.models import StandardProduct, IntentResult, ProblemVariation
from ...config import Config

logger = logging.getLogger(__name__)

class SearchConfigGenerator(ABC):
    """Abstract base class for search configuration generators."""
    
    @abstractmethod
    def generate_config(self, sample_products: List[StandardProduct] = None) -> Dict:
        """Generate search configuration from sample products."""
        pass

class LLMConfigGenerator(SearchConfigGenerator):
    """Generates search configuration using LLM analysis of products with automatic initialization."""
    
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
        # Path to store usage scenarios
        self.usage_scenarios_file_path = Path(__file__).parent / "usage_scenarios.json"
    
    def generate_config(self, sample_products: List[StandardProduct] = None) -> Dict:
        """
        Analyze sample products with LLM to generate Elasticsearch config and usage scenarios.
        If no products provided, fetch them automatically.
        
        Args:
            sample_products: Optional list of products to analyze. If None, fetches automatically.
            
        Returns:
            Dictionary with search configuration
        """
        logger.info("Generating search config...")
        
        # Check if config already exists
        existing_config = self.load_config()
        if existing_config:
            logger.info("Using existing search config")
            # Also check if we need to generate usage scenarios
            if not self.usage_scenarios_exist():
                logger.info("Generating missing usage scenarios...")
                self._auto_generate_usage_scenarios()
            return existing_config
        
        # If no products provided, fetch them automatically
        if sample_products is None:
            logger.info("No products provided, fetching automatically...")
            sample_products = self._fetch_products_automatically()
        
        if not sample_products:
            logger.warning("No products available for config generation, using fallback")
            fallback_config = self._get_fallback_config()
            self._save_config(fallback_config)
            return fallback_config
        
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
            
            # Generate and save usage scenarios for all products
            logger.info("Generating usage scenarios for intent search...")
            self._generate_and_save_usage_scenarios(sample_products)
            
            return config
            
        except Exception as e:
            logger.error(f"Error generating config: {e}")
            fallback_config = self._get_fallback_config()
            self._save_config(fallback_config)
            return fallback_config
    
    def _fetch_products_automatically(self) -> List[StandardProduct]:
        """Automatically fetch products from available providers."""
        try:
            # Import here to avoid circular imports
            from ..mock.provider import MockProvider
            
            # Use mock provider as fallback - it's always available
            logger.info("Fetching products from mock provider for config generation...")
            mock_provider = MockProvider()
            products = mock_provider.search_products()
            
            if products:
                logger.info(f"Fetched {len(products)} products from mock provider")
                return products
            
            # Try to get from integration manager if available
            try:
                from ..manager import IntegrationManager
                temp_manager = IntegrationManager(self.config)
                primary_provider = temp_manager._get_primary_provider()
                products = primary_provider.search_products()
                
                if products:
                    logger.info(f"Fetched {len(products)} products from primary provider")
                    return products
                    
            except Exception as e:
                logger.warning(f"Could not fetch from primary provider: {e}")
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to auto-fetch products: {e}")
            return []
    
    def _auto_generate_usage_scenarios(self):
        """Auto-generate usage scenarios when config exists but scenarios don't."""
        try:
            products = self._fetch_products_automatically()
            if products:
                usage_scenarios_map = self.generate_usage_scenarios(products)
                if usage_scenarios_map:
                    self._save_usage_scenarios(usage_scenarios_map)
                    logger.info(f"Auto-generated usage scenarios for {len(usage_scenarios_map)} products")
                else:
                    logger.warning("Failed to generate usage scenarios")
            else:
                logger.warning("No products available for usage scenario generation")
        except Exception as e:
            logger.error(f"Auto usage scenario generation failed: {e}")
    
    def _generate_and_save_usage_scenarios(self, products: List[StandardProduct]):
        """Generate usage scenarios for products and save to file."""
        try:
            usage_scenarios_map = self.generate_usage_scenarios(products)
            if usage_scenarios_map:
                self._save_usage_scenarios(usage_scenarios_map)
                logger.info(f"Generated usage scenarios for {len(usage_scenarios_map)} products")
            else:
                logger.warning("Failed to generate usage scenarios")
        except Exception as e:
            logger.error(f"Failed to generate usage scenarios: {e}")
    
    def analyze_intent(self, user_query: str) -> IntentResult:
        """Analyze user query to extract intent and problems."""
        
        prompt = f"""
        Analyze this customer query for gardening problems and intent:
        
        Query: "{user_query}"
        
        Extract:
        1. Primary problem (single phrase like "weed_removal" or "plant_health_decline")
        2. Context (plant types, garden areas, etc.)
        3. Symptoms (visible issues mentioned)
        4. Urgency (low/medium/high based on language used)
        
        Respond with JSON:
        {{
            "primary_problem": "main_issue_identified",
            "context": ["relevant", "context", "terms"],
            "symptoms": ["symptoms", "mentioned"],
            "urgency": "medium"
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            
            result_text = response.text.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            intent_data = json.loads(result_text)
            
            return IntentResult(
                primary_problem=intent_data.get("primary_problem", "general_gardening"),
                context=intent_data.get("context", []),
                symptoms=intent_data.get("symptoms", []),
                urgency=intent_data.get("urgency", "medium")
            )
            
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}")
            # Fallback intent
            return IntentResult(
                primary_problem="general_gardening",
                context=[],
                symptoms=[],
                urgency="medium"
            )

    def expand_problems(self, intent: IntentResult) -> List[ProblemVariation]:
        """Expand primary problem into related problem variations."""
        
        prompt = f"""
        Given this gardening problem, generate 4-5 related problems that might be causing it:
        
        Primary Problem: {intent.primary_problem}
        Context: {', '.join(intent.context)}
        Symptoms: {', '.join(intent.symptoms)}
        
        Generate related problems with confidence scores (0.1-1.0):
        - Include the original problem with high confidence
        - Add broader categories and specific variations
        - Consider root causes and related issues
        
        Example format:
        [
            {{"problem": "nutrient_deficiency", "confidence": 0.9, "category": "feeding"}},
            {{"problem": "overwatering", "confidence": 0.7, "category": "watering"}},
            {{"problem": "soil_ph_imbalance", "confidence": 0.6, "category": "soil"}}
        ]
        
        Respond with only the JSON array.
        """
        
        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=prompt
            )
            
            result_text = response.text.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]
            
            problems_data = json.loads(result_text)
            
            return [
                ProblemVariation(
                    problem=p.get("problem", ""),
                    confidence=p.get("confidence", 0.5),
                    category=p.get("category", "general")
                )
                for p in problems_data
            ]
            
        except Exception as e:
            logger.error(f"Problem expansion failed: {e}")
            # Fallback to original problem
            return [ProblemVariation(
                problem=intent.primary_problem,
                confidence=1.0,
                category="general"
            )]

    def generate_usage_scenarios(self, products: List[StandardProduct]) -> Dict[str, List[str]]:
        """Generate usage scenarios for products using LLM analysis."""
        
        logger.info(f"Generating usage scenarios for {len(products)} products...")
        
        # Check if we have cached scenarios first
        existing_scenarios = self.load_usage_scenarios()
        if existing_scenarios:
            logger.info("Using existing usage scenarios")
            return existing_scenarios
        
        # Process products in batches to avoid token limits
        batch_size = 5
        all_usage_scenarios = {}
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            # Prepare batch data
            product_data = []
            for product in batch:
                product_data.append({
                    "id": product.id,
                    "title": product.title,
                    "description": product.description[:200] if product.description else "",
                    "tags": product.tags,
                    "categories": product.categories
                })
            
            prompt = f"""
            Analyze these garden products and generate 3-5 SHORT problem keywords each product solves.

            Products: {json.dumps(product_data, indent=2)}

            For each product, generate 3-5 SINGLE WORDS or SHORT PHRASES (max 2-3 words):
            - Use underscore format: "weed_removal", "nutrient_deficiency", "poor_drainage"
            - NO sentences, NO explanations, NO "addresses the problem of"
            - Think: what would someone type when searching for a solution?

            Examples:
            - Fertilizer: ["nutrient_deficiency", "yellowing_leaves", "poor_growth", "plant_feeding"]
            - Trowel: ["transplanting", "weed_removal", "small_digging", "garden_maintenance"]
            - Seeds: ["vegetable_growing", "food_production", "garden_starting"]

            Respond with JSON - ONLY short problem keywords:
            {{
                "product_id_1": ["keyword1", "keyword2", "keyword3"],
                "product_id_2": ["keyword1", "keyword2", "keyword3"]
            }}
            """
            
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=prompt
                )
                
                result_text = response.text.strip()
                
                # Extract JSON from response
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]
                
                batch_scenarios = json.loads(result_text)
                all_usage_scenarios.update(batch_scenarios)
                
                logger.info(f"Generated scenarios for batch {i//batch_size + 1}")
                
            except Exception as e:
                logger.error(f"Usage scenario generation failed for batch: {e}")
                # Add fallback scenarios for this batch
                for product in batch:
                    all_usage_scenarios[product.id] = ["general_gardening", "garden_maintenance"]
        
        return all_usage_scenarios
    
    def load_usage_scenarios(self) -> Optional[Dict[str, List[str]]]:
        """Load existing usage scenarios from JSON file."""
        try:
            if self.usage_scenarios_file_path.exists():
                with open(self.usage_scenarios_file_path, 'r') as f:
                    data = json.load(f)
                
                # Handle both old format (direct dict) and new format (with metadata)
                if "scenarios" in data:
                    scenarios = data["scenarios"]
                else:
                    scenarios = data
                    
                logger.info(f"Loaded existing usage scenarios for {len(scenarios)} products")
                return scenarios
        except Exception as e:
            logger.error(f"Error loading usage scenarios: {e}")
        return None
    
    def _save_usage_scenarios(self, scenarios: Dict[str, List[str]]):
        """Save usage scenarios to JSON file."""
        try:
            # Ensure directory exists
            self.usage_scenarios_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save scenarios with timestamp
            scenarios_with_meta = {
                "scenarios": scenarios,
                "generated_at": str(datetime.now()),
                "product_count": len(scenarios)
            }
            
            with open(self.usage_scenarios_file_path, 'w') as f:
                json.dump(scenarios_with_meta, f, indent=2)
                
            logger.info(f"Saved usage scenarios to {self.usage_scenarios_file_path}")
            
        except Exception as e:
            logger.error(f"Error saving usage scenarios: {e}")
    
    def usage_scenarios_exist(self) -> bool:
        """Check if usage scenarios file exists."""
        return self.usage_scenarios_file_path.exists()
    
    def _generate_index_name(self, products: List[StandardProduct]) -> str:
        """Generate index name from categories or LLM analysis."""
        
        # Extract categories
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
        """Infer business type from categories."""
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
    
    def regenerate_config(self, sample_products: List[StandardProduct] = None) -> Dict:
        """Force regeneration of config (ignores existing file)."""
        logger.info("Force regenerating search config...")
        # Delete existing files
        if self.config_file_path.exists():
            self.config_file_path.unlink()
        if self.usage_scenarios_file_path.exists():
            self.usage_scenarios_file_path.unlink()
        
        return self.generate_config(sample_products)