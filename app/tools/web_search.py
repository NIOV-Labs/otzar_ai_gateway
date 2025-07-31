# /tools/web_search.py

"""
Provides a tool for performing web searches.

This tool is a fundamental capability for any research-oriented agent.
It leverages the Google Search API via the `google-search-results` library.
"""

import os
from langchain_community.tools import DuckDuckGoSearchRun

# It's best practice to load API keys from environment variables.
# This would be configured in a .env file and loaded in the main application entry point.
# For example:
# from dotenv import load_dotenv
# load_dotenv()

def get_web_search_tool():
    """
    Factory function to create and configure the web search tool.

    Returns:
        A configured instance of the DuckDuckGoSearchRun tool.
    """
    # Using DuckDuckGoSearchRun as it doesn't require an API key by default,
    # making it easy for initial setup.
    # In a production environment, we might use a more powerful tool like
    # the GoogleSearchAPIWrapper.
    search_tool = DuckDuckGoSearchRun()
    search_tool.name = "web_search"
    search_tool.description = (
        "A tool to search the internet for up-to-date information. "
        "Use this for any questions about current events, facts, or public data."
    )
    return search_tool