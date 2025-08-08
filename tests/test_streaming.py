#!/usr/bin/env python3
"""
Simple test script to verify the streaming endpoint works correctly.
"""

import asyncio
import aiohttp
import json

async def test_streaming():
    """Test the streaming endpoint."""
    url = "http://localhost:8000/api/v1/tasks/stream"
    params = {"query": "What is the A2A protocol?"}
    
    print(f"Testing streaming endpoint: {url}")
    print(f"Query: {params['query']}")
    print("-" * 50)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            print(f"Status: {response.status}")
            print(f"Headers: {response.headers}")
            print("-" * 50)
            
            if response.status == 200:
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        try:
                            data = json.loads(data_str)
                            if data.get('token') == '[DONE]':
                                print("Stream completed.")
                                break
                            elif data.get('error'):
                                print(f"Error: {data['error']}")
                                break
                            else:
                                print(f"Token: {data.get('token', '')}", end='', flush=True)
                        except json.JSONDecodeError:
                            print(f"Invalid JSON: {data_str}")
            else:
                text = await response.text()
                print(f"Error response: {text}")

if __name__ == "__main__":
    asyncio.run(test_streaming())
