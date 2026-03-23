# Deep Research Agent API

A sophisticated AI-powered research agent that uses Claude LLM with advanced hallucination reduction mechanisms. Designed for integration into apps and wearables via RESTful API.

## Features

- **Claude LLM Integration**: Uses Anthropic's Claude 3.5 Sonnet for high-quality research synthesis
- **Hallucination Reduction**: Multi-layered fact-checking system that:
  - Cross-references information across multiple sources
  - Verifies claims with confidence scoring
  - Requires source citations for all factual statements
  - Refines responses when confidence is low
- **Web Search Integration**: Automatically gathers information from multiple web sources
- **Source Verification**: Validates information against multiple sources before responding
- **RESTful API**: Easy integration for apps, wearables, and other services
- **CORS Enabled**: Ready for cross-origin requests from web and mobile apps

## Architecture

### Hallucination Reduction System

The system employs multiple strategies to minimize hallucinations:

1. **Multi-Source Verification**: Information is gathered from multiple independent sources
2. **Fact Extraction & Cross-Referencing**: Claims are extracted and verified across sources
3. **Confidence Scoring**: Each claim receives a confidence score based on source agreement
4. **Response Refinement**: Low-confidence responses are automatically refined
5. **Citation Requirements**: All factual claims must include source citations
6. **Structured Prompts**: Claude is instructed to only use information from provided sources

### Components

- `ResearchAgent`: Core agent that orchestrates research and verification
- `WebSearchService`: Gathers information from web sources
- `FactChecker`: Verifies claims and calculates confidence scores
- `FastAPI`: RESTful API server for easy integration

## Installation

1. **Clone or navigate to the project directory**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:
```bash
cp env.example .env
```

Edit `.env` and add your Anthropic API key:
```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Get your API key from: https://console.anthropic.com/

4. **Run the API server**:
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### POST /research

Perform deep research on a query.

**Request Body**:
```json
{
  "query": "What are the latest developments in quantum computing?",
  "depth": "standard"
}
```

**Parameters**:
- `query` (string, required): Research query
- `depth` (string, optional): Research depth
  - `"quick"`: 3 sources, faster response
  - `"standard"`: 5 sources (default)
  - `"deep"`: 8+ sources, most thorough

**Response**:
```json
{
  "query": "What are the latest developments in quantum computing?",
  "response": "Based on the provided sources...",
  "citations": [
    {
      "id": 1,
      "title": "Source Title",
      "url": "https://example.com"
    }
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
    "model": "claude-3-5-sonnet-20241022",
    "sources_checked": 5,
    "depth": "standard"
  }
}
```

### GET /research

Same as POST but using query parameters (convenient for simple integrations).

**Example**:
```
GET /research?query=quantum%20computing&depth=standard
```

### GET /research/stream

Stream research results for real-time updates (Server-Sent Events).

**Example**:
```
GET /research/stream?query=quantum%20computing&depth=standard
```

### GET /health

Health check endpoint.

## Usage Examples

### Python

```python
import requests

# POST request
response = requests.post(
    "http://localhost:8000/research",
    json={
        "query": "What is the current state of AI in healthcare?",
        "depth": "standard"
    }
)

result = response.json()
print(f"Response: {result['response']}")
print(f"Confidence: {result['confidence_score']}")
print(f"Citations: {len(result['citations'])}")
```

### JavaScript/TypeScript

```javascript
// Using fetch
const response = await fetch('http://localhost:8000/research', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: 'What are the benefits of exercise?',
    depth: 'standard'
  })
});

const result = await response.json();
console.log(result.response);
console.log(`Confidence: ${result.confidence_score}`);
```

### cURL

```bash
curl -X POST "http://localhost:8000/research" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is climate change?",
    "depth": "standard"
  }'
```

### Wearable/App Integration

For wearables and mobile apps, use the GET endpoint for simplicity:

```javascript
// React Native / Mobile App Example
const researchQuery = async (query) => {
  const encodedQuery = encodeURIComponent(query);
  const response = await fetch(
    `http://your-api-server:8000/research?query=${encodedQuery}&depth=quick`
  );
  return await response.json();
};

// Usage
const result = await researchQuery("What is the weather today?");
```

## Hallucination Reduction Details

### How It Works

1. **Source Gathering**: The agent searches the web and gathers multiple independent sources
2. **Content Extraction**: Relevant content is extracted from each source
3. **Claude Synthesis**: Claude is given strict instructions to only use provided sources
4. **Claim Extraction**: The response is analyzed to extract factual claims
5. **Cross-Reference Verification**: Each claim is verified against all sources
6. **Confidence Calculation**: Confidence scores are calculated based on source agreement
7. **Refinement**: If confidence is low, the response is refined with stricter constraints

### Confidence Scoring

- **High Confidence (≥0.7)**: Information is well-supported by multiple sources
- **Medium Confidence (0.5-0.7)**: Information has some support but may need verification
- **Low Confidence (<0.5)**: Information is poorly supported or contradicted

### Best Practices

1. **Use appropriate depth**: 
   - Quick for simple queries
   - Standard for most use cases
   - Deep for critical research

2. **Check confidence scores**: Lower scores indicate less reliable information

3. **Review citations**: Always verify important information by checking source URLs

4. **Handle uncertainty**: The system explicitly states when information is unavailable or uncertain

## Configuration

Edit `config.py` to customize:

- `CLAUDE_MODEL`: Claude model version
- `MAX_TOKENS`: Maximum response length
- `TEMPERATURE`: Lower = more precise (default: 0.3)
- `MAX_SEARCH_RESULTS`: Number of sources to gather
- `MIN_SOURCE_COUNT`: Minimum sources for verification
- `VERIFICATION_THRESHOLD`: Confidence threshold (default: 0.7)

## Production Deployment

For production:

1. **Set CORS origins**: Update `main.py` to specify allowed origins
2. **Use environment variables**: Never commit `.env` file
3. **Add authentication**: Implement API keys or OAuth
4. **Rate limiting**: Add rate limiting middleware
5. **Monitoring**: Add logging and monitoring
6. **Error handling**: Enhance error messages for production

Example production setup with Docker:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Limitations

- Web search relies on DuckDuckGo (no API key required but may have rate limits)
- Some websites may block automated access
- Fact-checking is based on source agreement, not absolute truth
- Processing time increases with research depth

## Contributing

Contributions are welcome! Areas for improvement:

- Additional search engines
- Enhanced fact-checking algorithms
- Better source quality filtering
- Caching mechanisms
- WebSocket support for real-time streaming

## License

MIT License - feel free to use in your projects.

## Support

For issues or questions, please open an issue on the repository.

