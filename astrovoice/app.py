import os
import sqlite3
import json
import asyncio
import base64
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from services.nova_service import NovaService
from services.rag.arxiv_connector import ArxivConnector
from services.rag.nasa_connector import NasaConnector
from services.learner_profile import LearnerProfile, init_learner_table

load_dotenv()

app = FastAPI(title="AstroVoice — Amazon Nova Powered")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
nova   = NovaService()
arxiv  = ArxivConnector()
nasa   = NasaConnector()

# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "AstroVoice-Nova-Ready", "db": DB_PATH, "v": "1.0.1"}


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
    """
    Nova 2 Lite adaptive teaching endpoint.
    1. Load learner profile to get difficulty level.
    2. Fetch RAG context from ArXiv + NASA.
    3. Call Nova 2 Lite with level-appropriate system prompt.
    4. Extract CHECK comprehension question from response.
    5. Return response body, CHECK question, sources, and learner state.
    """
    profile = LearnerProfile.load(request.session_id)
    profile.record_exchange()

    # Semantic cache check (exact match)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT response, confidence, sources FROM semantic_cache WHERE query = ?",
        (request.query.lower(),),
    )
    cached = c.fetchone()
    conn.close()

    if cached:
        profile.save()
        full_text = cached[0]
        check_q = _extract_check_question(full_text)
        return {
            "response": _strip_check_question(full_text),
            "check_question": check_q,
            "confidence": cached[1],
            "sources": json.loads(cached[2]),
            "cached": True,
            "learner": profile.to_dict(),
        }

    # RAG retrieval — ArXiv + NASA in parallel
    try:
        arxiv_results, nasa_results = await asyncio.gather(
            arxiv.search(request.query),
            nasa.search_technical_reports(request.query),
        )
        sources_list = arxiv_results + nasa_results
        source_context = ""
        for i, s in enumerate(sources_list[:6]):
            source_context += (
                f"\n[Source {i+1}]: {s.get('title','')}\n"
                f"  {s.get('summary', s.get('abstract', ''))[:300]}\n"
            )
    except Exception as e:
        print(f"[RAG] Error: {e}")
        source_context = ""
        sources_list = []

    # Nova 2 Lite reasoning with learner-level prompt
    full_response = await nova.invoke_nova_lite_chat(
        prompt=request.query,
        system_prompt="",  # baked into nova_service SYSTEM_TEMPLATE
        context=source_context,
        level=profile.level,
    )

    check_q = _extract_check_question(full_response)
    answer_body = _strip_check_question(full_response)

    # Confidence heuristic
    has_source = "[Source" in full_response or "[Verified" in full_response
    confidence = 0.95 if has_source else 0.6

    # Cache
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO semantic_cache (query, response, confidence, sources) VALUES (?, ?, ?, ?)",
            (request.query.lower(), full_response, confidence, json.dumps(sources_list[:5])),
        )
        conn.commit()
    finally:
        conn.close()

    # Extract the topic noun — last meaningful word (e.g. 'Jupiter' from 'Tell me about Jupiter')
    topic_words = [w for w in request.query.split() if len(w) > 3]
    topic = topic_words[-1].strip('?.,!').capitalize() if topic_words else request.query.split()[-1].capitalize()
    profile.add_topic(topic)
    profile.save()

    return {
        "response": answer_body,
        "check_question": check_q,
        "confidence": confidence,
        "sources": sources_list[:5],
        "cached": False,
        "learner": profile.to_dict(),
    }


@app.post("/answer")
async def answer(request: AnswerRequest):
    """
    Nova 2 Lite judges the learner's answer to a comprehension question.
    Updates the learner profile (correct answers → potential level-up).
    """
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
    # Simple heuristic: if Nova says "correct" / "great" → award point
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
    """
    Experimental low-latency S2S streaming.
    Streams audio chunks directly from Nova Sonic.
    """
    audio_bytes = base64.b64decode(request.audio)
    
    async def generate_chunks():
        async for chunk in nova.invoke_nova_sonic_s2s_stream(audio_bytes):
            if chunk:
                yield chunk

    return StreamingResponse(generate_chunks(), media_type="audio/mpeg")


@app.post("/voice")
async def voice(audio_data: VoiceRequest):
    """
    Nova 2 Sonic speech-to-speech endpoint.
    1. Decode incoming base64 audio.
    2. Transcribe with Nova Sonic → text.
    3. If transcript empty (demo/error) return guidance; else call /chat pipeline.
    4. Re-synthesize answer text → audio via Nova Sonic.
    Returns base64-encoded audio response.
    """
    try:
        audio_bytes = base64.b64decode(audio_data.audio)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio")

    # Step 1: STT via Nova Sonic
    transcript = await nova.nova_sonic_transcribe(audio_bytes)

    # Step 2: If no transcript (demo mode), use a placeholder instead of forcing JWST
    if not transcript:
        # Check if the user is likely speaking in demo mode (no credentials)
        if not nova._has_credentials:
            transcript = "Jupiter" # Default to Jupiter for testing if empty
            is_demo = True
        else:
            return {"error": "No transcript detected", "status": "idle"}
    else:
        is_demo = False

    # Step 3: Chat pipeline (reuse same logic)
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

    # Step 4: TTS via Nova Sonic → audio bytes
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
    """Nova Act agent for UI-workflow data (e.g. trajectory JSON)."""
    data = await nova.invoke_nova_act_workflow(request.task, request.query_context)
    return {"ui_logic": data}


# Serve built frontend
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=False)
