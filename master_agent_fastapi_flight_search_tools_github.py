#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  5 12:27:26 2025

@author: carousell
"""

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug  4 21:23:41 2025

@author: carousell
"""

# ✅ FULL WORKING FASTAPI + MASTER AGENT + FLIGHT SEARCH + DUMMY TOOLS (MERGED)

from fastapi import FastAPI
from pydantic import BaseModel
from langchain.chat_models import AzureChatOpenAI
from langchain.agents import Tool, initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from datetime import datetime
import requests
import re

app = FastAPI()

# ---------------- Azure OpenAI Setup ----------------
llm = AzureChatOpenAI(
    openai_api_version="-",
    azure_endpoint="-",
    deployment_name="-",
    openai_api_key="-",
    temperature=0.3,
)

# ---------------- City → IATA Mapping ----------------
city_to_airport = {
    "delhi": "DEL", "new delhi": "DEL", "mumbai": "BOM", "bangalore": "BLR",
    "san francisco": "SFO", "new york": "JFK", "california": "LAX",
    "london": "LHR", "tokyo": "NRT", "paris": "CDG", "chandigarh": "IXC",
    "enteebee": "EBB"
}

# ---------------- Parse Natural Language Query ----------------
def parse_query(query: str):
    query = query.lower()
    from_city = next((c for c in city_to_airport if f"from {c}" in query), None)
    to_city = next((c for c in city_to_airport if f"to {c}" in query), None)
    if not from_city or not to_city:
        return None

    full_matches = re.findall(
        r"((?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,\s*\d{4})?)",
        query, re.IGNORECASE
    )
    dates = []
    for date_str in full_matches:
        try:
            date = datetime.strptime(date_str.strip() + ("" if "," in date_str else " 2025"), "%B %d %Y")
            dates.append(date.strftime("%Y-%m-%d"))
        except: continue

    if not dates:
        return None

    return {
        "departure_id": city_to_airport[from_city],
        "arrival_id": city_to_airport[to_city],
        "outbound_date": dates[0],
        "return_date": dates[1] if len(dates) > 1 else None,
        "trip_type": "1" if len(dates) > 1 else "2"
    }

# ---------------- Flight Search Tool ----------------
SERPAPI_KEY = "-"
def search_flights(query: str):
    params = parse_query(query)
    if not params:
        return "❌ Could not parse your query. Try: 'Flights from Delhi to London on August 30 return Sept 10'."

    req = {
        "engine": "google_flights",
        "departure_id": params["departure_id"],
        "arrival_id": params["arrival_id"],
        "outbound_date": params["outbound_date"],
        "currency": "USD",
        "type": params["trip_type"],
        "api_key": SERPAPI_KEY
    }
    if params["return_date"]:
        req["return_date"] = params["return_date"]

    res = requests.get("https://serpapi.com/search", params=req)
    data = res.json()

    flights = data.get("best_flights") or data.get("other_flights") or []
    if not flights:
        return "❌ No flights found."

    out = f"✈️ Flights from {params['departure_id']} to {params['arrival_id']} on {params['outbound_date']}:\n\n"
    for f in flights[:3]:
        legs = f.get("flights", [])
        airline = legs[0].get("airline", "Unknown") if legs else "Unknown"
        price = f.get("price", "N/A")
        dur = f.get("total_duration", "N/A")
        out += f"• {airline} | ${price} | {dur} mins\n"
        for leg in legs:
            out += f"   - {leg['departure_airport']['name']} ({leg['departure_airport']['time']}) → {leg['arrival_airport']['name']} ({leg['arrival_airport']['time']})\n"
        out += "\n"
    return out

# ---------------- Dummy Tool Handlers ----------------
def dummy_tool(_: str) -> str:
    return "✅ Dummy response."

# ---------------- Tool Definitions ----------------
profile_tool = Tool(name="ProfileFetcher", func=dummy_tool, description="Fetch user profile.")
email_tool = Tool(name="EmailWriter", func=dummy_tool, description="Write email.")
meeting_tool = Tool(name="MeetingScheduler", func=dummy_tool, description="Schedule meetings.")
slack_tool = Tool(name="SlackNotifier", func=dummy_tool, description="Send Slack notifications.")
flight_tool = Tool(name="FlightSearcher", func=search_flights, description="Find flights using SerpAPI.")

# ---------------- LangChain Agent ----------------
tools = [profile_tool, email_tool, meeting_tool, slack_tool, flight_tool]
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent = initialize_agent(tools=tools, llm=llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, memory=memory, verbose=True)

# ---------------- Request Models ----------------
class AgentRequest(BaseModel):
    query: str

class FlightQuery(BaseModel):
    query: str

# ---------------- FastAPI Endpoints ----------------
@app.post("/agent")
def ask_agent(req: AgentRequest):
    try:
        response = agent.invoke({"input": req.query})
        return {"response": response["output"]}
    except Exception as e:
        return {"error": str(e)}

@app.post("/search-flights")
def search_flight_api(fq: FlightQuery):
    return {"result": search_flights(fq.query)}
