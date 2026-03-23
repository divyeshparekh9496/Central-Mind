#!/usr/bin/env python3
"""
Demo script for the Deep Research Agent API.
Run this after starting the server to see example usage.
"""
import asyncio
import httpx
import json
from typing import Dict, Any


async def demo_research_api():
    """Demonstrate the research API with various queries."""
    
    base_url = "http://localhost:8000"
    
    # Test queries with different depths
    test_queries = [
        {"query": "What is quantum computing?", "depth": "quick"},
        {"query": "Latest developments in artificial intelligence", "depth": "standard"},
        {"query": "Climate change impact on agriculture", "depth": "deep"},
    ]
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        print("🔬 Deep Research Agent API Demo")
        print("=" * 50)
        
        # Check server health
        try:
            health = await client.get(f"{base_url}/health")
            print(f"✅ Server Status: {health.json()['status']}")
            print()
        except Exception as e:
            print(f"❌ Server not running: {e}")
            print("Please start the server first: python main.py")
            return
        
        # Test each query
        for i, test in enumerate(test_queries, 1):
            print(f"📝 Test {i}: {test['query'][:50]}...")
            print(f"   Depth: {test['depth']}")
            
            try:
                # Make research request
                response = await client.post(
                    f"{base_url}/research",
                    json=test,
                    timeout=120.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Display results
                    print(f"   ✅ Confidence: {result['confidence_score']:.2f}")
                    print(f"   📚 Sources: {len(result['citations'])}")
                    print(f"   🎯 Cache Hit: {result['metadata'].get('cache_hit', False)}")
                    print(f"   📄 Response: {result['response'][:100]}...")
                    print()
                    
                else:
                    print(f"   ❌ Error: {response.status_code}")
                    print(f"   Details: {response.text}")
                    print()
                    
            except Exception as e:
                print(f"   ❌ Request failed: {e}")
                print()
        
        # Test cache stats
        try:
            stats = await client.get(f"{base_url}/cache/stats")
            cache_data = stats.json()
            
            print("📊 Cache Statistics:")
            print(f"   Entries: {cache_data['cache']['entries']}")
            print(f"   Total Hits: {cache_data['cache']['total_hits']}")
            print(f"   Circuit Breaker: {'🔴 Open' if cache_data['safeguards']['refinement_circuit_open'] else '🟢 Closed'}")
            print()
            
        except Exception as e:
            print(f"❌ Failed to get stats: {e}")
        
        print("🎉 Demo completed!")
        print(f"🌐 Web UI available at: {base_url}")
        print(f"📖 API docs at: {base_url}/docs")


if __name__ == "__main__":
    asyncio.run(demo_research_api())