#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  1 17:42:55 2025

@author: Annie
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import requests
import re
from datetime import datetime

app = FastAPI()

# --- SerpAPI Key ---
SERPAPI_KEY = "Your_Key_Here"

# --- City to IATA Mapping ---
city_to_airport = {
    "delhi": "DEL", "new delhi": "DEL",
    "mumbai": "BOM", "bangalore": "BLR",
    "san francisco": "SFO", "new york": "JFK",
    "california": "LAX", "london": "LHR",
    "tokyo": "NRT", "paris": "CDG", "chandigarh": "IXC",
    "enteebee": "EBB"
}

# --- Input Model ---
class FlightQuery(BaseModel):
    query: str

# --- Date & IATA Parser ---
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
            if "," in date_str:
                date = datetime.strptime(date_str.strip(), "%B %d, %Y")
            else:
                date = datetime.strptime(date_str.strip() + " 2025", "%B %d %Y")
            dates.append(date.strftime("%Y-%m-%d"))
        except Exception:
            continue

    if not dates:
        return None

    return {
        "departure_id": city_to_airport[from_city],
        "arrival_id": city_to_airport[to_city],
        "outbound_date": dates[0],
        "return_date": dates[1] if len(dates) > 1 else None,
        "trip_type": "1" if len(dates) > 1 else "2"
    }

# --- Main Search Function ---
def search_flights(query: str):
    params = parse_query(query)
    if not params:
        return "❌ Could not parse your query. Example: 'Flights from Delhi to San Francisco on August 30 return September 10'."

    request_params = {
        "engine": "google_flights",
        "departure_id": params["departure_id"],
        "arrival_id": params["arrival_id"],
        "outbound_date": params["outbound_date"],
        "currency": "USD",
        "type": params["trip_type"],
        "api_key": SERPAPI_KEY
    }
    if params["return_date"]:
        request_params["return_date"] = params["return_date"]

    response = requests.get("https://serpapi.com/search", params=request_params)
    data = response.json()

    flights = data.get("best_flights") or data.get("other_flights") or []
    if not flights:
        return "❌ No flights found for your input."

    output = f"✈️ Flights from {params['departure_id']} to {params['arrival_id']} on {params['outbound_date']}\n\n"
    for flight in flights[:3]:
        legs = flight.get("flights", [])
        airline = legs[0].get("airline", "Unknown") if legs else "Unknown"
        price = flight.get("price", "N/A")
        duration = flight.get("total_duration", "N/A")

        output += f"• Airline: {airline} | Price: ${price} | Duration: {duration} mins\n"
        for leg in legs:
            dep = leg["departure_airport"]["name"]
            dep_time = leg["departure_airport"]["time"]
            arr = leg["arrival_airport"]["name"]
            arr_time = leg["arrival_airport"]["time"]
            output += f"   - {dep} ({dep_time}) → {arr} ({arr_time})\n"
        output += "\n"

    return output

# --- FastAPI Endpoint ---
@app.post("/search-flights")
def search_flight_api(fq: FlightQuery):
    return {"result": search_flights(fq.query)}
