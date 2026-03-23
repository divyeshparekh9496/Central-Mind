"""Web search service for gathering information from multiple sources."""
import httpx
import asyncio
from typing import List, Dict, Optional
from urllib.parse import quote_plus
from tenacity import retry, stop_after_attempt, wait_exponential
import re


class WebSearchService:
    """Service for performing web searches and extracting information."""
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5)
    )
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Perform web search using DuckDuckGo (no API key required).
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of search results with title, url, and snippet
        """
        try:
            # Use DuckDuckGo HTML search (no API key needed)
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            
            async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
                response = await client.get(search_url)
                response.raise_for_status()
                
                # Parse HTML results
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'lxml')
                
                results = []
                result_elements = soup.find_all('div', class_='result', limit=max_results)
                
                for element in result_elements:
                    title_elem = element.find('a', class_='result__a')
                    snippet_elem = element.find('a', class_='result__snippet')
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get('href', '')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        # Fix relative URLs from DuckDuckGo
                        if url and not url.startswith('http'):
                            if url.startswith('//'):
                                url = 'https:' + url
                            else:
                                continue  # Skip invalid URLs
                        
                        if url and title:
                            results.append({
                                "title": title,
                                "url": url,
                                "snippet": snippet
                            })
                
                return results[:max_results]
                
        except Exception as e:
            print(f"Search error: {e}")
            # Fallback: return empty results
            return []
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3)
    )
    async def fetch_content(self, url: str) -> Optional[str]:
        """
        Fetch and extract text content from a URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Extracted text content or None
        """
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=self.headers) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Extract text
                text = soup.get_text()
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)
                
                # Limit content length
                return text[:5000] if text else None
                
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

