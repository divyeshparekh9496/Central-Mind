"""Safeguards and utilities for robust operation."""
import re
import asyncio
from typing import Optional
from datetime import datetime, timedelta


class CircuitBreaker:
    """Circuit breaker to disable features after repeated failures."""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open (disabled)."""
        if self.state == "open":
            # Check if we should try again (half-open)
            if (self.last_failure_time and 
                datetime.now() - self.last_failure_time > timedelta(seconds=self.reset_timeout)):
                self.state = "half-open"
                return False
            return True
        return False
    
    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None
    
    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
    
    def should_allow_operation(self) -> bool:
        """Check if operation should be allowed."""
        return not self.is_open()


def sanitize_query(query: str, max_length: int = 500) -> str:
    """
    Sanitize user input query.
    
    Args:
        query: Raw user query
        max_length: Maximum allowed length
        
    Returns:
        Cleaned query string
    """
    if not query or not isinstance(query, str):
        return ""
    
    # Strip excessive whitespace
    query = re.sub(r'\s+', ' ', query.strip())
    
    # Remove potentially problematic characters but keep basic punctuation
    query = re.sub(r'[^\w\s\?\.\,\-\!\:\;\(\)\'\"]+', '', query)
    
    # Limit length
    query = query[:max_length]
    
    # Ensure minimum length
    if len(query.strip()) < 3:
        raise ValueError("Query too short (minimum 3 characters)")
    
    return query.strip()


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # ip -> list of timestamps
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for given identifier."""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > window_start
            ]
        else:
            self.requests[identifier] = []
        
        # Check limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Record request
        self.requests[identifier].append(now)
        return True


def create_llm_semaphore(max_concurrent: int) -> asyncio.Semaphore:
    """Create semaphore for limiting concurrent LLM calls."""
    return asyncio.Semaphore(max_concurrent)


async def cleanup_cache_periodically(cache, interval_hours: int = 1):
    """Background task to clean up cache periodically."""
    while True:
        try:
            await asyncio.sleep(interval_hours * 3600)
            # Trigger eviction
            cache._evict_old_entries()
        except Exception as e:
            print(f"Cache cleanup error: {e}")