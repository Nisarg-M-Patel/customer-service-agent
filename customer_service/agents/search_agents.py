# customer_service/agents/search_agents.py
"""Efficient single-agent search implementation to avoid quota exhaustion."""

from google.adk.agents import LlmAgent
from ..tools.products import search_products, intent_search_products, load_search_results_from_artifacts

# Single agent that does everything - no parallel LLM calls
coordinated_search_workflow = LlmAgent(
    name="CoordinatedProductSearch",
    model="gemini-2.0-flash-exp",
    instruction="""
    You handle comprehensive product searches efficiently using multiple search approaches.
    
    For any product search request:
    1. First call search_products for direct keyword matches
    2. Then call intent_search_products for problem-solving recommendations  
    3. Finally call load_search_results_from_artifacts to get the complete results
    4. Combine both datasets and provide a comprehensive response
    
    Your response should:
    - Show direct product matches from keyword search
    - Include intelligent suggestions from intent analysis
    - Explain why each product was recommended
    - Provide clear product details (ID, name, price, availability)
    - Group results logically for easy scanning
    
    If no results found, explain clearly and suggest alternatives.
    You are the complete search solution.
    """,
    tools=[search_products, intent_search_products, load_search_results_from_artifacts]
)