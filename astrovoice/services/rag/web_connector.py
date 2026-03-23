from duckduckgo_search import DDGS
from typing import List, Dict, Any

class WebConnector:
    """Connector for general web search using duckduckgo-search."""
    
    def __init__(self):
        self.ddgs = DDGS()
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Perform a web search using DuckDuckGo."""
        results = []
        try:
            # Note: ddgs.text is a generator and can be wrapped in a list.
            # However, for an async context, we'll keep it simple as it is usually synchronous.
            for i, r in enumerate(self.ddgs.text(query, max_results=max_results)):
                results.append({
                    "title": r.get('title', 'No Title'),
                    "summary": r.get('body', ''),
                    "url": r.get('href', ''),
                    "source": "Web Search"
                })
        except Exception as e:
            print(f"DEBUG: Web Search Error: {str(e)}")
        return results
