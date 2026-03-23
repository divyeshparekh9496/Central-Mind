# Deep Research Agent - Technical Specification

## Product Overview

**Deep Research Agent** is an AI-powered research API with built-in hallucination reduction. It gathers information from multiple web sources, synthesizes responses using LLMs, and verifies facts through cross-referencing.

**Target Use Cases:**
- Mobile apps requiring factual research
- Wearable devices with voice queries
- Enterprise knowledge assistants
- Research automation tools

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │  Web UI  │  │Mobile App│  │ Wearable │  │   API    │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
└───────┼─────────────┼─────────────┼─────────────┼──────────────────┘
        │             │             │             │
        └─────────────┴──────┬──────┴─────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────────┐
│                      API GATEWAY (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │Rate Limiter │  │  Validator  │  │   Timeout   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────────┐
│                     CACHING LAYER                                   │
│  ┌──────────────────────────────────────────────┐                  │
│  │           Semantic Cache                      │                  │
│  │  • Exact match lookup                        │                  │
│  │  • Cosine similarity matching (0.85 threshold)│                  │
│  │  • TTL-based expiration (24h)                │                  │
│  └──────────────────────────────────────────────┘                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Cache Miss
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     RESEARCH AGENT CORE                             │
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │ Web Search  │───▶│   Content   │───▶│    LLM      │             │
│  │  (Parallel) │    │  Extractor  │    │  (Gemini)   │             │
│  └─────────────┘    └─────────────┘    └──────┬──────┘             │
│                                               │                     │
│                                               ▼                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │  Response   │◀───│    Fact     │◀───│    CoVe     │             │
│  │  Refinement │    │   Checker   │    │  Prompting  │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────────┐
│                     SAFEGUARDS LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Circuit    │  │  Semaphore   │  │    Retry     │              │
│  │   Breaker    │  │  (5 max)     │  │   w/Backoff  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Features

### 1. Hallucination Reduction System

| Technique | Description | Impact |
|-----------|-------------|--------|
| **Chain-of-Verification (CoVe)** | LLM drafts → verifies → checks → finalizes | 15-25% accuracy improvement |
| **Multi-Source Verification** | Cross-references claims across 3-8 sources | Reduces single-source bias |
| **Confidence Scoring** | 0-1 score based on source agreement | Quantifies reliability |
| **Automatic Refinement** | Re-generates if confidence < 0.7 | Improves low-quality responses |
| **Source Grounding** | LLM instructed to ONLY use provided sources | Prevents fabrication |

### 2. Semantic Caching

| Feature | Specification |
|---------|---------------|
| **Match Types** | Exact + Semantic similarity |
| **Similarity Threshold** | 0.85 (configurable) |
| **TTL** | 24 hours (configurable) |
| **Max Entries** | 1,000 (configurable) |
| **Cost Savings** | 50-90% on repeat/similar queries |
| **Latency Reduction** | <100ms for cache hits vs 2-10s for fresh |

### 3. Production Safeguards

| Safeguard | Implementation | Purpose |
|-----------|----------------|---------|
| **Request Timeout** | 120s max | Prevents hung requests |
| **Rate Limiting** | 10 req/min per IP | Prevents abuse |
| **Concurrent LLM Limit** | Semaphore (5 max) | Controls API costs |
| **Circuit Breaker** | Disables after 5 failures | Graceful degradation |
| **Input Validation** | Sanitize + length limits | Security |
| **Retry with Backoff** | 3 attempts, exponential delay | Handles transient failures |

---

## API Specification

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Health check |
| `POST` | `/research` | Perform research (JSON body) |
| `GET` | `/research` | Perform research (query params) |
| `GET` | `/research/stream` | SSE streaming results |
| `GET` | `/cache/stats` | Cache statistics |
| `POST` | `/cache/clear` | Clear cache |
| `GET` | `/docs` | Swagger UI |

### Request Format

```json
POST /research
{
  "query": "What are the latest developments in quantum computing?",
  "depth": "standard"
}
```

**Depth Options:**
- `quick` - 3 sources, fastest
- `standard` - 5 sources, balanced (default)
- `deep` - 8+ sources, most thorough

### Response Format

```json
{
  "query": "What are the latest developments in quantum computing?",
  "response": "Based on the provided sources, quantum computing has seen...",
  "citations": [
    {"id": 1, "title": "Source Title", "url": "https://..."}
  ],
  "sources": [...],
  "verification": {
    "overall_confidence": 0.85,
    "supporting_sources": 4,
    "total_sources": 5,
    "verified": true
  },
  "confidence_score": 0.85,
  "metadata": {
    "model": "gemini-2.5-flash",
    "sources_checked": 5,
    "depth": "standard",
    "cache_hit": false
  }
}
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastAPI | Async API server |
| **LLM** | Google Gemini 2.5 Flash | Response generation |
| **Web Search** | DuckDuckGo HTML | Source gathering (no API key) |
| **HTML Parsing** | BeautifulSoup + lxml | Content extraction |
| **HTTP Client** | httpx (async) | Web requests |
| **Validation** | Pydantic | Request/response models |
| **Retry Logic** | Tenacity | Exponential backoff |
| **Vector Math** | NumPy | Semantic similarity |

---

## Data Flow

```
1. REQUEST RECEIVED
   └─▶ Rate limit check
   └─▶ Input validation & sanitization
   └─▶ Timeout wrapper (120s)

2. CACHE CHECK
   └─▶ Exact key match?
   └─▶ Semantic similarity match (>0.85)?
   └─▶ Return cached response if hit

3. SOURCE GATHERING (Parallel)
   └─▶ Generate search query variations
   └─▶ Execute DuckDuckGo searches in parallel
   └─▶ Deduplicate results by URL
   └─▶ Fetch page content in parallel

4. LLM GENERATION (CoVe)
   └─▶ Build prompt with sources
   └─▶ Apply Chain-of-Verification instructions
   └─▶ Call Gemini with retry logic
   └─▶ Extract response

5. FACT VERIFICATION
   └─▶ Extract claims from response
   └─▶ Cross-reference each claim against sources
   └─▶ Calculate confidence scores
   └─▶ Identify low-confidence claims

6. REFINEMENT (if needed)
   └─▶ Check circuit breaker status
   └─▶ If confidence < 0.7, refine response
   └─▶ Re-verify refined response

7. CACHE & RETURN
   └─▶ Store in semantic cache
   └─▶ Return formatted response
```

---

## Configuration

### Environment Variables

```bash
# Required
GOOGLE_API_KEY=your_gemini_api_key

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Cache Settings
CACHE_SIMILARITY_THRESHOLD=0.85
CACHE_TTL_HOURS=24
CACHE_MAX_ENTRIES=1000

# Safeguards
REQUEST_TIMEOUT_SECONDS=120
MAX_CONCURRENT_LLM_CALLS=5
CIRCUIT_BREAKER_THRESHOLD=5
MAX_QUERY_LENGTH=500
```

---

## Performance Characteristics

| Metric | Value | Conditions |
|--------|-------|------------|
| **Cache Hit Latency** | <100ms | Exact or semantic match |
| **Fresh Query (Quick)** | 5-15s | 3 sources |
| **Fresh Query (Standard)** | 10-25s | 5 sources |
| **Fresh Query (Deep)** | 20-45s | 8+ sources |
| **Memory Usage** | ~50-200MB | Depends on cache size |
| **Concurrent Requests** | 5 LLM calls max | Configurable |

---

## File Structure

```
deep-research-agent/
├── main.py                 # FastAPI application
├── config.py               # Configuration settings
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables
├── env.example             # Example environment file
│
├── services/
│   ├── __init__.py
│   ├── research_agent.py   # Core research orchestrator
│   ├── web_search.py       # DuckDuckGo search service
│   ├── fact_checker.py     # Claim verification
│   ├── semantic_cache.py   # Caching layer
│   └── safeguards.py       # Circuit breaker, rate limiter
│
├── static/
│   └── index.html          # Web UI
│
├── examples/
│   ├── curl_examples.sh
│   ├── python_example.py
│   └── javascript_example.js
│
└── docs/
    └── SPEC_SHEET.md       # This document
```

---

## Deployment

### Local Development
```bash
pip install -r requirements.txt
cp env.example .env
# Add your GOOGLE_API_KEY to .env
python main.py
# Open http://localhost:8000
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Checklist
- [ ] Set specific CORS origins
- [ ] Add authentication (API keys/OAuth)
- [ ] Use Redis for distributed caching
- [ ] Add monitoring/logging (Prometheus, etc.)
- [ ] Set up rate limiting per user/API key
- [ ] Configure SSL/TLS

---

## Cost Analysis

### LLM API Costs (Gemini Free Tier)
- 15 requests/minute
- 1,500 requests/day
- 1M tokens/month

### With Semantic Caching
| Scenario | Without Cache | With Cache (50% hit rate) |
|----------|---------------|---------------------------|
| 1,000 queries/day | 1,000 API calls | 500 API calls |
| Monthly cost | Exceeds free tier | Within free tier |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Jan 2026 | Initial release with CoVe, caching, safeguards |

---

## License

MIT License - Free for commercial and personal use.
