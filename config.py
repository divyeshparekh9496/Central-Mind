"""Configuration settings for the research agent."""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration."""
    # Google Gemini API Key (free tier available)
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    
    # Legacy support for Anthropic (optional)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    
    # Gemini model configuration
    GEMINI_MODEL = "models/gemini-flash-latest"  # Free tier, fast
    MAX_TOKENS = 4096
    TEMPERATURE = 0.3  # Lower temperature for more precise outputs
    
    # Research agent settings
    MAX_SEARCH_RESULTS = 5
    MIN_SOURCE_COUNT = 3  # Minimum sources to verify information
    VERIFICATION_THRESHOLD = 0.7  # Confidence threshold for fact verification
    
    # Semantic cache settings
    CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", 0.85))
    CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", 24))
    CACHE_MAX_ENTRIES = int(os.getenv("CACHE_MAX_ENTRIES", 1000))
    
    # Safeguard settings
    REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", 120))
    MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", 5))
    CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", 5))
    MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", 500))

