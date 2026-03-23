"""Semantic caching service for reducing API costs and latency."""
import hashlib
import json
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio


class SemanticCache:
    """
    Semantic cache using simple embedding similarity.
    Uses a lightweight approach without external dependencies.
    For production, consider Redis Vector or GPTCache.
    """
    
    def __init__(self, similarity_threshold: float = 0.85, ttl_hours: int = 24, max_entries: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Dict[str, List[float]] = {}
        self.similarity_threshold = similarity_threshold
        self.ttl = timedelta(hours=ttl_hours)
        self.max_entries = max_entries
    
    def _simple_embedding(self, text: str) -> List[float]:
        """
        Generate a simple embedding using character/word statistics.
        For production, use sentence-transformers or OpenAI embeddings.
        """
        text = text.lower().strip()
        words = text.split()
        
        # Feature vector: word count, char count, unique words, avg word len, etc.
        features = [
            len(words),
            len(text),
            len(set(words)),
            sum(len(w) for w in words) / max(len(words), 1),
            text.count('?'),
            text.count(' '),
        ]
        
        # Add word hash features for semantic similarity
        word_hashes = []
        for word in words[:50]:  # First 50 words
            h = int(hashlib.md5(word.encode()).hexdigest()[:8], 16) / (16**8)
            word_hashes.append(h)
        
        # Pad or truncate to fixed size
        word_hashes = (word_hashes + [0] * 50)[:50]
        
        return features + word_hashes
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)
        
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _generate_key(self, query: str, depth: str) -> str:
        """Generate a cache key from query and depth."""
        normalized = f"{query.lower().strip()}:{depth}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is expired."""
        created = datetime.fromisoformat(entry["created_at"])
        return datetime.now() - created > self.ttl
    
    def _evict_old_entries(self):
        """Remove expired entries and enforce max size."""
        # Remove expired (limit iterations to prevent runaway)
        expired_keys = [k for k, v in list(self.cache.items())[:self.max_entries * 2] if self._is_expired(v)]
        for key in expired_keys[:100]:  # Max 100 evictions per call
            self.cache.pop(key, None)
            self.embeddings.pop(key, None)
        
        # Enforce max size (remove oldest)
        if len(self.cache) > self.max_entries:
            sorted_entries = sorted(
                list(self.cache.items())[:self.max_entries * 2],
                key=lambda x: x[1]["created_at"]
            )
            to_remove = min(len(self.cache) - self.max_entries, 100)  # Max 100 removals
            for key, _ in sorted_entries[:to_remove]:
                self.cache.pop(key, None)
                self.embeddings.pop(key, None)
    
    async def get(self, query: str, depth: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a query.
        Returns None if no similar query found or cache expired.
        """
        self._evict_old_entries()
        
        # First try exact match
        exact_key = self._generate_key(query, depth)
        if exact_key in self.cache and not self._is_expired(self.cache[exact_key]):
            entry = self.cache[exact_key]
            entry["hits"] = entry.get("hits", 0) + 1
            return {**entry["response"], "cache_hit": True, "cache_type": "exact"}
        
        # Try semantic similarity match
        query_embedding = self._simple_embedding(query)
        
        best_match = None
        best_similarity = 0.0
        
        for key, embedding in self.embeddings.items():
            if key not in self.cache:
                continue
            
            entry = self.cache[key]
            if self._is_expired(entry):
                continue
            
            # Only match same depth
            if entry.get("depth") != depth:
                continue
            
            similarity = self._cosine_similarity(query_embedding, embedding)
            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = entry
        
        if best_match:
            best_match["hits"] = best_match.get("hits", 0) + 1
            return {
                **best_match["response"],
                "cache_hit": True,
                "cache_type": "semantic",
                "similarity": best_similarity
            }
        
        return None
    
    async def set(self, query: str, depth: str, response: Dict[str, Any]):
        """Cache a response for a query."""
        self._evict_old_entries()
        
        key = self._generate_key(query, depth)
        embedding = self._simple_embedding(query)
        
        self.cache[key] = {
            "query": query,
            "depth": depth,
            "response": response,
            "created_at": datetime.now().isoformat(),
            "hits": 0
        }
        self.embeddings[key] = embedding
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_hits = sum(e.get("hits", 0) for e in self.cache.values())
        return {
            "entries": len(self.cache),
            "total_hits": total_hits,
            "max_entries": self.max_entries,
            "ttl_hours": self.ttl.total_seconds() / 3600
        }
    
    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()
        self.embeddings.clear()
