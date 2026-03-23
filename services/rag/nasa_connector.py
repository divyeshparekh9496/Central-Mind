import httpx
from typing import List, Dict, Any
import os

class NasaConnector:
    """Connector for NASA Technical Reports and Image API."""
    
    def __init__(self):
        self.api_key = os.getenv("NASA_API_KEY", "DEMO_KEY")
        self.ntrs_base = "https://ntrs.nasa.gov/api/citations"
        self.image_base = "https://images-api.nasa.gov/search"
        
    async def search_technical_reports(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search NASA Technical Reports Server (NTRS)."""
        async with httpx.AsyncClient() as client:
            # Note: NTRS API might require specific headers or auth depending on usage
            response = await client.get(f"{self.ntrs_base}/search", params={"q": query, "page": {"size": limit}})
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            return []

    async def search_images(self, query: str) -> List[Dict[str, Any]]:
        """Search NASA's image and video library."""
        async with httpx.AsyncClient() as client:
            response = await client.get(self.image_base, params={"q": query, "media_type": "image"})
            if response.status_code == 200:
                return response.json().get("collection", {}).get("items", [])[:5]
            return []
