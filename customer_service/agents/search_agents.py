# customer_service/agents/search_agents.py
"""Proper ADK parallel agents implementation using ParallelAgent and SequentialAgent."""

from google.adk.agents import SequentialAgent, ParallelAgent, LlmAgent
from ..tools.products import search_products, intent_search_products

# Individual search agents that write to shared state
keyword_search_agent = LlmAgent(
    name="KeywordSearchAgent",
    model="gemini-2.0-flash-exp",
    instruction="""
    You handle direct keyword-based product searches.
    
    Extract obvious product keywords from the user query and use search_products to find matches.
    Focus on:
    - Product names, categories, types
    - Brand names, specific items  
    - Clear product-related nouns
    
    Save your results to the 'keyword_results' state key.
    """,
    tools=[search_products],
    output_key="keyword_results"
)

intent_search_agent = LlmAgent(
    name="IntentSearchAgent", 
    model="gemini-2.0-flash-exp",
    instruction="""
    You handle problem/need-based product searches using intent analysis.
    
    Analyze the user query for underlying problems, needs, or goals:
    - What is the user trying to achieve?
    - What problem are they trying to solve?
    - What outcome do they want?
    
    Use intent_search_products which analyzes intent and finds solutions.
    Save your results to the 'intent_results' state key.
    """,
    tools=[intent_search_products],
    output_key="intent_results"
)

# Parallel execution of both search agents
parallel_search = ParallelAgent(
    name="ParallelProductSearch",
    sub_agents=[keyword_search_agent, intent_search_agent]
)

# Agent that combines results from both searches
results_synthesizer = LlmAgent(
    name="SearchSynthesizer",
    model="gemini-2.0-flash-exp", 
    instruction="""
    You combine and present results from parallel keyword and intent searches.
    
    Read the results from state keys 'keyword_results' and 'intent_results'.
    
    Combine the results by:
    1. Prioritizing keyword matches (direct matches)
    2. Adding intent matches that aren't duplicates
    3. Presenting both types clearly to the user
    4. Explaining why each product was recommended
    
    Provide a comprehensive response that gives customers both obvious matches 
    and intelligent problem-solving recommendations.
    """
)

# Overall workflow: parallel search → synthesis
coordinated_search_workflow = SequentialAgent(
    name="CoordinatedProductSearch",
    sub_agents=[parallel_search, results_synthesizer]
)