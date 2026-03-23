"""
Semantic cache powered by Nova Multimodal Embeddings.
Replaces the toy MD5-hash approach with real cosine similarity on Nova vectors.
"""
import hashlib
import json
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class SemanticCache:
    """
    Semantic cache using Nova Multimodal Embeddings for similarity.
    nova_service.embed_text() is injected to avoid circular imports.
    """

    def __init__(self, similarity_threshold: float = 0.88, ttl_hours: int = 24, max_entries: int = 500):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Dict[str, List[float]] = {}
        self.similarity_threshold = similarity_threshold
        self.ttl = timedelta(hours=ttl_hours)
        self.max_entries = max_entries
        self._embed_fn = None   # injected after init: cache.set_embed_fn(nova.embed_text)

    def set_embed_fn(self, fn):
        """Inject Nova embed_text coroutine."""
        self._embed_fn = fn

    # ------------------------------------------------------------------
    async def _embed(self, text: str) -> List[float]:
        if self._embed_fn:
            return await self._embed_fn(text)
        # Fallback: deterministic hash (demo mode)
        h = hashlib.sha256(text.lower().encode()).digest()
        vec = [((b / 255.0) - 0.5) * 2 for b in h]
        vec = (vec * 4)[:64]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        a_arr, b_arr = np.array(a), np.array(b)
        denom = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
        return float(np.dot(a_arr, b_arr) / denom) if denom else 0.0

    def _key(self, query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    def _expired(self, entry: Dict) -> bool:
        return datetime.now() - datetime.fromisoformat(entry["created_at"]) > self.ttl

    def _evict(self):
        expired = [k for k, v in self.cache.items() if self._expired(v)]
        for k in expired:
            self.cache.pop(k, None)
            self.embeddings.pop(k, None)
        if len(self.cache) > self.max_entries:
            oldest = sorted(self.cache.items(), key=lambda x: x[1]["created_at"])
            for k, _ in oldest[:len(self.cache) - self.max_entries]:
                self.cache.pop(k, None)
                self.embeddings.pop(k, None)

    # ------------------------------------------------------------------
    async def get(self, query: str) -> Optional[Dict[str, Any]]:
        self._evict()

        # Exact match
        exact = self._key(query)
        if exact in self.cache and not self._expired(self.cache[exact]):
            return {**self.cache[exact]["response"], "cache_hit": True, "cache_type": "exact"}

        # Semantic match via Nova embeddings
        q_emb = await self._embed(query)
        best, best_sim = None, 0.0
        for key, emb in self.embeddings.items():
            if key not in self.cache or self._expired(self.cache[key]):
                continue
            sim = self._cosine(q_emb, emb)
            if sim > best_sim and sim >= self.similarity_threshold:
                best_sim, best = sim, self.cache[key]

        if best:
            return {**best["response"], "cache_hit": True, "cache_type": "semantic", "similarity": best_sim}
        return None

    async def set(self, query: str, response: Dict[str, Any]):
        self._evict()
        key = self._key(query)
        emb = await self._embed(query)
        self.cache[key] = {
            "query": query,
            "response": response,
            "created_at": datetime.now().isoformat(),
        }
        self.embeddings[key] = emb

    def get_stats(self) -> Dict[str, Any]:
        return {"entries": len(self.cache), "max_entries": self.max_entries}
