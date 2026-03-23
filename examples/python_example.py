"""Example usage of the Research Agent API in Python."""
import requests
import json


def research_query(query: str, depth: str = "standard"):
    """
    Query the research agent API.
    
    Args:
        query: Research query
        depth: Research depth (quick, standard, deep)
    """
    url = "http://localhost:8000/research"
    
    response = requests.post(
        url,
        json={
            "query": query,
            "depth": depth
        },
        timeout=60  # Research can take time
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API Error: {response.status_code} - {response.text}")


def print_research_result(result: dict):
    """Pretty print research results."""
    print("\n" + "="*80)
    print(f"QUERY: {result['query']}")
    print("="*80)
    print(f"\nRESPONSE:\n{result['response']}")
    print("\n" + "-"*80)
    print(f"Confidence Score: {result['confidence_score']:.2%}")
    print(f"Verified: {result['verification']['verified']}")
    print(f"Sources Checked: {result['verification']['total_sources']}")
    print(f"Supporting Sources: {result['verification']['supporting_sources']}")
    print("\nCITATIONS:")
    for citation in result['citations']:
        print(f"  [{citation['id']}] {citation['title']}")
        print(f"      {citation['url']}")
    print("="*80 + "\n")


if __name__ == "__main__":
    # Example queries
    queries = [
        "What are the latest developments in artificial intelligence?",
        "How does quantum computing work?",
        "What are the health benefits of meditation?"
    ]
    
    for query in queries:
        try:
            print(f"\n🔍 Researching: {query}")
            result = research_query(query, depth="standard")
            print_research_result(result)
        except Exception as e:
            print(f"❌ Error: {e}")

