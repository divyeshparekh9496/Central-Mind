import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

class ArxivConnector:
    """Connector for arXiv Astrophysics publications."""
    
    def __init__(self):
        self.base_url = "https://export.arxiv.org/api/query"
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        params = {
            "search_query": f"all:{query} AND cat:astro-ph*",
            "start": 0,
            "max_results": max_results,
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            return self._parse_feed(response.text)
            
    def _parse_feed(self, xml_content: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = []
        
        for entry in root.findall('atom:entry', namespace):
            entries.append({
                "title": entry.find('atom:title', namespace).text.strip(),
                "summary": entry.find('atom:summary', namespace).text.strip(),
                "url": entry.find('atom:id', namespace).text,
                "authors": [a.find('atom:name', namespace).text for a in entry.findall('atom:author', namespace)],
                "published": entry.find('atom:published', namespace).text,
                "updated": entry.find('atom:updated', namespace).text if entry.find('atom:updated', namespace) is not None else None
            })
        return entries
