import os
import sqlite3
import json
import base64
import asyncio
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.responses import StreamingResponse
from services.nova_service import NovaService
from services.rag.arxiv_connector import ArxivConnector
from services.rag.nasa_connector import NasaConnector
from services.learner_profile import LearnerProfile, init_learner_table

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
import uvicorn
from config import Config
from services.research_agent import ResearchAgent
from services.rag.pipeline import utcnow
from services.safeguards import sanitize_query, RateLimiter, cleanup_cache_periodically

app = FastAPI(
    title="Deep Research Agent API",
    description="AI-powered research agent with hallucination reduction for apps and wearables",
    version="1.0.0"
)

# Enable CORS for apps and wearables
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for the web UI
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize research agent
research_agent = ResearchAgent()

# Initialize rate limiter
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

# AstroVoice Services
nova = NovaService()
arxiv = ArxivConnector()
nasa = NasaConnector()

# DB bootstrap
DB_PATH = "/tmp/astrovoice_v2.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS semantic_cache
        (query TEXT PRIMARY KEY, response TEXT, confidence REAL,
         sources TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    """)
    conn.commit()
    conn.close()

init_db()
init_learner_table()


# Request/Response Models
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default"

class VoiceRequest(BaseModel):
    audio: str          # base64-encoded audio bytes

class AnswerRequest(BaseModel):
    session_id: str
    question: str       # the CHECK: comprehension question Nova posed
    user_answer: str    # what the learner said / typed

class ActRequest(BaseModel):
    task: str
    query_context: str

class ResearchRequest(BaseModel):
    """Request model for research queries."""
    query: str = Field(..., description="Research query", min_length=3, max_length=Config.MAX_QUERY_LENGTH)
    depth: Literal["quick", "standard", "deep"] = Field(
        default="standard",
        description="Research depth: quick (3 sources), standard (5 sources), deep (8+ sources)"
    )
    
    @validator('query')
    def sanitize_query_input(cls, v):
        return sanitize_query(v, Config.MAX_QUERY_LENGTH)


class Citation(BaseModel):
    """Citation model."""
    id: int
    title: str
    url: str
    fetched_at: Optional[str] = None
    published: Optional[str] = None
    content_hash: Optional[str] = None
    evidence_kind: Optional[str] = None
    chunk_id: Optional[str] = None


class VerificationResult(BaseModel):
    """Verification result model."""
    overall_confidence: float
    supporting_sources: int
    total_sources: int
    verified: bool


class ResearchResponse(BaseModel):
    """Response model for research results."""
    query: str
    response: str
    citations: list[Citation]
    sources: list[dict]
    verification: VerificationResult
    confidence_score: float
    metadata: dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    model: str


@app.get("/")
async def root():
    """Serve the web UI."""
    return FileResponse('static/index.html')


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "model": Config.GEMINI_MODEL
    }


@app.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest, req: Request):
    """
    Perform deep research on a query.
    
    This endpoint:
    - Gathers information from multiple web sources
    - Uses Gemini to synthesize research
    - Verifies facts across sources to reduce hallucinations
    - Returns well-cited, verified information
    
    Args:
        request: Research request with query and depth
        req: FastAPI request object for rate limiting
        
    Returns:
        Research response with citations and verification
    """
    # Rate limiting
    client_ip = req.client.host if req.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    
    try:
        if not Config.GOOGLE_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="GOOGLE_API_KEY not configured. Please set it in your .env file."
            )
        
        # Apply timeout to prevent hanging requests
        result = await asyncio.wait_for(
            research_agent.research(request.query, request.depth),
            timeout=Config.REQUEST_TIMEOUT_SECONDS
        )
        
        # Format verification for response
        verification_result = VerificationResult(
            overall_confidence=result["verification"]["overall_confidence"],
            supporting_sources=sum(
                v.get("supporting_sources", 0) 
                for v in result["verification"].get("verifications", [])
            ),
            total_sources=result["metadata"]["sources_checked"],
            verified=result["verification"]["overall_confidence"] >= Config.VERIFICATION_THRESHOLD
        )
        
        return ResearchResponse(
            query=result["query"],
            response=result["response"],
            citations=[Citation(**c) for c in result["citations"]],
            sources=result["sources"],
            verification=verification_result,
            confidence_score=result["confidence_score"],
            metadata=result["metadata"]
        )
        
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail=f"Request timed out after {Config.REQUEST_TIMEOUT_SECONDS} seconds"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research error: {str(e)}")


@app.get("/research", response_model=ResearchResponse)
async def research_get(
    req: Request,
    query: str = Query(..., description="Research query", min_length=3, max_length=Config.MAX_QUERY_LENGTH),
    depth: Literal["quick", "standard", "deep"] = Query(
        default="standard",
        description="Research depth"
    )
):
    """
    GET endpoint for research (convenient for simple integrations).
    
    Same functionality as POST /research but using query parameters.
    """
    # Sanitize query parameter
    try:
        clean_query = sanitize_query(query, Config.MAX_QUERY_LENGTH)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    request = ResearchRequest(query=clean_query, depth=depth)
    return await research(request, req)


@app.get("/research/stream")
async def research_stream(
    req: Request,
    query: str = Query(..., description="Research query", min_length=3, max_length=Config.MAX_QUERY_LENGTH),
    depth: Literal["quick", "standard", "deep"] = Query(default="standard")
):
    """
    Stream research results (for real-time updates in apps/wearables).
    
    Note: This is a simplified streaming endpoint. For full streaming,
    consider using Server-Sent Events (SSE) or WebSockets.
    """
    # Rate limiting
    client_ip = req.client.host if req.client else "unknown"
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(429, "Rate limit exceeded")
    
    # Sanitize query
    try:
        clean_query = sanitize_query(query, Config.MAX_QUERY_LENGTH)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    from fastapi.responses import StreamingResponse
    import json
    
    async def generate():
        try:
            # Yield status updates
            yield f"data: {json.dumps({'status': 'searching', 'message': 'Gathering sources...'})}\n\n"
            
            result = await asyncio.wait_for(
                research_agent.research(clean_query, depth),
                timeout=Config.REQUEST_TIMEOUT_SECONDS
            )
            
            yield f"data: {json.dumps({'status': 'complete', 'result': result})}\n\n"
            
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'status': 'error', 'error': 'Request timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/rag/search")
async def search_indexed_evidence(query: str = Query(..., min_length=3, max_length=500)):
    """Inspect already indexed passages; this endpoint does not refresh the web."""
    passages = await asyncio.to_thread(research_agent.rag.retrieve, query)
    return {"query": query, "passages": passages,
            "ranker": research_agent.rag.ranker.name,
            "freshness_policy": "stored passages within configured TTL; no live refresh",
            "score_meaning": "relevance, not truth or publication recency"}


@app.get("/cache/stats")
async def cache_stats():
    """
    Get semantic cache statistics.
    
    Returns cache hit rates, entry counts, and configuration.
    Useful for monitoring cost savings.
    """
    stats = research_agent.semantic_cache.get_stats()
    return {
        "cache": stats,
        "config": {
            "similarity_threshold": Config.CACHE_SIMILARITY_THRESHOLD,
            "ttl_hours": Config.CACHE_TTL_HOURS,
            "max_entries": Config.CACHE_MAX_ENTRIES
        },
        "safeguards": {
            "request_timeout_seconds": Config.REQUEST_TIMEOUT_SECONDS,
            "max_concurrent_llm_calls": Config.MAX_CONCURRENT_LLM_CALLS,
            "circuit_breaker_threshold": Config.CIRCUIT_BREAKER_THRESHOLD,
            "refinement_circuit_open": research_agent.refinement_circuit_breaker.is_open()
        }
    }


@app.post("/cache/clear")
async def cache_clear():
    """Clear the semantic cache."""
    research_agent.semantic_cache.clear()
    return {"status": "cleared"}


@app.on_event("startup")
async def startup_event():
    """Initialize background tasks."""
    # Start cache cleanup task
    asyncio.create_task(
        cleanup_cache_periodically(research_agent.semantic_cache, interval_hours=1)
    )

# --- ASTROVOICE HELPERS & ENDPOINTS ---
def _extract_check_question(text: str) -> Optional[str]:
    """Pull out the 'CHECK: ...' question from Nova's response."""
    if "CHECK:" in text:
        parts = text.split("CHECK:", 1)
        return parts[1].strip()
    return None

def _strip_check_question(text: str) -> str:
    """Return the answer body without the trailing CHECK line."""
    if "CHECK:" in text:
        return text.split("CHECK:")[0].strip()
    return text

@app.get("/debug/bedrock")
async def debug_bedrock():
    """Directly test Bedrock connectivity from the backend."""
    return await nova.check_bedrock_connection()

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Retrieve learner profile for a session."""
    profile = LearnerProfile.load(session_id)
    return profile.to_dict()

@app.post("/chat")
async def chat(request: ChatRequest):
    """Nova 2 Lite adaptive teaching endpoint."""
    profile = LearnerProfile.load(request.session_id)
    profile.record_exchange()

    # Current source retrieval on every turn; do not reuse indefinitely cached
    # answers across dates or learner levels.
    retrieved_at = utcnow().isoformat()
    results = await asyncio.gather(
        arxiv.search(request.query), nasa.search_technical_reports(request.query),
        return_exceptions=True)
    documents = []
    for group in results:
        if not isinstance(group, list):
            continue
        for source in group:
            title = source.get("title", "")
            summary = source.get("summary") or source.get("abstract", "")
            url = source.get("url")
            if not url and str(source.get("id", "")).isdigit():
                url = f"https://ntrs.nasa.gov/citations/{source['id']}"
            if url and isinstance(title, str) and isinstance(summary, str) and summary.strip():
                documents.append({"title": title, "text": summary, "url": url,
                                  "fetched_at": retrieved_at, "published": source.get("published"),
                                  "evidence_kind": "live_api_abstract"})
    hits = await asyncio.to_thread(research_agent.rag.refresh_and_retrieve,
                                   request.query, documents, 6)
    sources_list = [{k:v for k,v in hit.items() if k != "text"} for hit in hits]
    source_context = "\n\n".join(
        f"[Source {i+1}]: {hit['title']}\nURL: {hit['url']}\n{hit['text']}"
        for i,hit in enumerate(hits))
    if hits:
        full_response = await nova.invoke_nova_lite_chat(
            prompt=request.query,
            system_prompt="",
            context=source_context,
            level=profile.level)
    else:
        full_response = "No usable current research sources were retrieved. Please retry or provide a source."
    check_q = _extract_check_question(full_response)
    answer_body = _strip_check_question(full_response)
    # Retain numeric API compatibility without presenting citation presence as
    # 95% factual accuracy. This is explicitly uncalibrated, not model confidence.
    confidence = 0.5 if hits else 0.0

    topic_words = [w for w in request.query.split() if len(w) > 3]
    topic = topic_words[-1].strip('?.,!').capitalize() if topic_words else request.query.split()[-1].capitalize()
    profile.add_topic(topic)
    profile.save()

    return {
        "response": answer_body,
        "check_question": check_q,
        "confidence": confidence,
        "sources": sources_list,
        "cached": False,
        "freshness_checked_at": retrieved_at,
        "freshness_policy": "live_refresh_every_request",
        "confidence_type": "uncalibrated_heuristic",
        "ranker": research_agent.rag.ranker.name,
        "learner": profile.to_dict(),
    }

@app.post("/answer")
async def answer(request: AnswerRequest):
    profile = LearnerProfile.load(request.session_id)
    judge_prompt = (
        f"Comprehension question: {request.question}\n"
        f"Learner answer: {request.user_answer}\n\n"
        "Judge the answer in 1-2 sentences: is it correct? "
        "Give brief constructive feedback. Do NOT add a CHECK question here."
    )
    feedback = await nova.invoke_nova_lite_chat(
        prompt=judge_prompt,
        system_prompt="You are a supportive space tutor. Be encouraging and precise.",
        level=profile.level,
    )
    is_correct = any(w in feedback.lower() for w in ["correct", "right", "exactly", "great", "well done", "yes"])
    if is_correct:
        profile.record_correct()
    profile.save()

    return {
        "correct": is_correct,
        "feedback": _strip_check_question(feedback),
        "learner": profile.to_dict(),
    }

@app.post("/voice_stream")
async def voice_stream(request: VoiceRequest):
    audio_bytes = base64.b64decode(request.audio)
    
    async def generate_chunks():
        async for chunk in nova.invoke_nova_sonic_s2s_stream(audio_bytes):
            if chunk:
                yield chunk

    return StreamingResponse(generate_chunks(), media_type="audio/mpeg")

@app.post("/voice")
async def voice(audio_data: VoiceRequest):
    try:
        audio_bytes = base64.b64decode(audio_data.audio)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio")

    transcript = await nova.nova_sonic_transcribe(audio_bytes)

    if not transcript:
        if not nova._has_credentials:
            transcript = "Jupiter"
            is_demo = True
        else:
            return {"error": "No transcript detected", "status": "idle"}
    else:
        is_demo = False

    profile = LearnerProfile.load("voice_session")
    profile.record_exchange()

    source_context = ""
    try:
        arxiv_results, nasa_results = await asyncio.gather(
            arxiv.search(transcript),
            nasa.search_technical_reports(transcript),
        )
        sources_list = arxiv_results + nasa_results
        for i, s in enumerate(sources_list[:4]):
            source_context += f"\n[Source {i+1}]: {s.get('title','')}\n  {s.get('summary','')[:200]}\n"
    except Exception:
        sources_list = []

    full_response = await nova.invoke_nova_lite_chat(
        prompt=transcript,
        system_prompt="",
        context=source_context,
        level=profile.level,
    )
    answer_body = _strip_check_question(full_response)
    check_q     = _extract_check_question(full_response)

    response_audio = await nova.invoke_nova_sonic_s2s(answer_body.encode("utf-8"))

    topic_words = [w for w in transcript.split() if len(w) > 3]
    topic = topic_words[-1].strip('?.,!').capitalize() if topic_words else transcript.split()[-1].capitalize()
    profile.add_topic(topic)
    profile.save()

    return {
        "transcript": transcript,
        "response": answer_body,
        "check_question": check_q,
        "audio_response": base64.b64encode(response_audio).decode("utf-8"),
        "is_demo": is_demo,
        "learner": profile.to_dict(),
    }

@app.post("/act")
async def act(request: ActRequest):
    data = await nova.invoke_nova_act_workflow(request.task, request.query_context)
    return {"ui_logic": data}

if os.path.exists("astrovoice/frontend/dist"):
    app.mount("/astrovoice", StaticFiles(directory="astrovoice/frontend/dist", html=True), name="astrovoice_ui")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=True
    )

