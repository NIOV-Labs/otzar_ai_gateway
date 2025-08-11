#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  8 16:23:37 2025

@author: carousell
"""

# ✅ FastAPI Multi-Agent Web Scraper with Azure OpenAI

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import AzureChatOpenAI
from bs4 import BeautifulSoup
import requests
import time
import re

# ------------------ FastAPI App ------------------
app = FastAPI()

# ------------------ Azure OpenAI Config ------------------
AZURE_OPENAI_KEY = ""
AZURE_OPENAI_ENDPOINT = ""
DEPLOYMENT_NAME = ""

llm = AzureChatOpenAI(
    openai_api_version="2024-12-01-preview",
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    deployment_name=DEPLOYMENT_NAME,
    openai_api_key=AZURE_OPENAI_KEY,
    temperature=0.3,
)

# ------------------ Web Scraper Tool ------------------
def web_scraper(query: str) -> str:
    """
    Simple HTML scraper using BeautifulSoup.
    Query format: "scrape https://example.com for all headlines"
    """
    match = re.search(r"scrape (https?://[^\s]+)", query)
    if not match:
        return "❌ Invalid query format."

    url = match.group(1)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; BusinessBot/1.0)"
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        time.sleep(1)  # politeness delay
        soup = BeautifulSoup(response.text, 'html.parser')
        titles = soup.find_all(['h1', 'h2', 'h3'])
        result = [f"- {t.get_text(strip=True)}" for t in titles if t.get_text(strip=True)]
        return "\n".join(result[:10]) if result else "❌ No headlines found."
    except Exception as e:
        return f"❌ Scraping error: {str(e)}"

# ------------------ Dummy Agent Tools ------------------
def dummy(_: str) -> str:
    return "✅ Dummy action completed."

scraper_tool = Tool(
    name="WebScraper",
    func=web_scraper,
    description="Scrapes a web page for content. Include full URL in query."
)
profile_tool = Tool(name="ProfileAgent", func=dummy, description="Fetch user profile")
email_tool = Tool(name="EmailAgent", func=dummy, description="Draft personalized email")

# ------------------ Master Agent ------------------
tools = [scraper_tool, profile_tool, email_tool]
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent = initialize_agent(tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, memory=memory, verbose=True)

# ------------------ API Input Model ------------------
class AgentRequest(BaseModel):
    query: str

# ------------------ Endpoint ------------------
@app.post("/agent")
def run_agent(req: AgentRequest):
    try:
        result = agent.invoke({"input": req.query})
        return {"result": result["output"]}
    except Exception as e:
        return {"error": str(e)}
