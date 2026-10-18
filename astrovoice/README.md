> The primary kids’ Space Club is now served from the repository root. Run `python adventure_server.py` there. This directory contains the earlier React/cloud interface and does not yet share the new adventure quiz/BKT endpoints.

# 🚀 AstroVoice - Nova-Powered Space Assistant (Free Tier MVP)

A production-ready, voice-first astrophysics research assistant using Amazon Nova models and a single Docker container.

## 🏗️ Architecture
- **Voice**: Nova 2 Sonic (Speech-to-Speech)
- **Reasoning**: Nova 2 Lite (Fast research & fact-checking)
- **UI Workflows**: Nova Act 
- **Database**: SQLite (Semantic Cache + Vector Store)
- **Frontend**: React 19 + Three.js Solar System

## 🚀 Quickstart (Docker)

```bash
# Build the single container (Frontend + Backend)
docker build -t astrovoice .

# Run locally
docker run -p 80:8000 \
  -e AWS_ACCESS_KEY_ID=your_id \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  astrovoice
```

The UI will be accessible at `http://localhost:80` and the API at `http://localhost:80/chat`.

## 🛡️ Zero-Hallucination Pipeline
1. **Nova 2 Lite Draft**: Generates initial response from NASA/ArXiv.
2. **Deterministic Check**: Cross-references claims against source summaries in the SQLite store.
3. **Nova Act Refinement**: Polishes output and injects mathematical precision.
4. **Confidence Circuit Breaker**: Blocks any response with <85% verified alignment.

## 🆓 Free Deployment
- **Frontend**: Vercel/Netlify (Static)
- **Backend/Container**: Render.com (Connect GitHub -> Deploy Docker)
- **Cost**: $0.00/month on Free Tiers.
