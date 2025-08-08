# /tools/web_search.py

"""
Provides a tool for performing web searches.

This tool is a fundamental capability for any research-oriented agent.
It leverages the Google Search API via the `google-search-results` library.
"""

from typing import List
# from langchain_community.tools import DuckDuckGoSearchRun
from ddgs import DDGS
from langchain_core.tools import Tool

# It's best practice to load API keys from environment variables.
# This would be configured in a .env file and loaded in the main application entry point.
# For example:
# from dotenv import load_dotenv
# load_dotenv()

def search_duckduckgo(query: str, max_results: int = 5) -> list[str]:
    """
    Perform a DuckDuckGo web search using the ddgs package.

    Args:
        query: The search query.
        max_results: The maximum number of results to return.

    Returns:
        A list of search result strings. 
    """
    results = []

    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(f"{r['title']}\n{r['href']}\n{r['body']}")

    return results


def get_web_search_tool():
    """
    Returns a callable tool that can be used for web search.

    Returns:
        A function that takes a query and returns results.
    """
    # Using DuckDuckGoSearchRun as it doesn't require an API key by default,
    # making it easy for initial setup.
    # In a production environment, we might use a more powerful tool like
    # the GoogleSearchAPIWrapper.
    # search_tool = DuckDuckGoSearchRun()
    # search_tool.name = "web_search"
    # search_tool.description = (
    #     "A tool to search the internet for up-to-date information. "
    #     "Use this for any questions about current events, facts, or public data."
    # )
    # return search_tool

    def run(query: str):
        return "\n".join(search_duckduckgo(query))

    # Optionally wrap this in a class if you're integrating with LangChain tools
    return Tool(
        name="web_search",
        description="A tool to search the internet for up-to-date information. "
        "Use this for any questions about current events, facts, or public data.",
        func=run
    )   