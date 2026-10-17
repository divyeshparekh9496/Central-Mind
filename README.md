# Central-Mind · Evidence-Ranked Research Assistant

Central-Mind combines web-grounded research with an astronomy learning companion. The root FastAPI app now has a **persistent retrieval-augmented generation (RAG) pipeline**, a trained **supervised evidence-ranking baseline**, and explicit source-freshness metadata.

**Best-aligned ML task: supervised evidence ranking.** Retrieve passages with BM25, optionally rerank them with a trained model, and give the generator traceable evidence. A transformer cross-encoder is supported as an optional neural reranker. Ranking relevance is separate from proving whether a claim is true.

## What is implemented

- Live web retrieval for research, and NASA/arXiv abstracts for the root tutoring endpoint.
- SQLite document storage, overlapping passage chunks, content hashes and timestamp-based expiry.
- BM25 candidate retrieval; optional bundled logistic learning-to-rank model or pretrained cross-encoder.
- Citation metadata bound to the exact extracted passage, including when another source fails to load.
- Fresh searches on every root research/tutoring request; no silently reused stale answer cache.
- No-current-evidence responses when retrieval fails or finds no matching passages.
- A reproducible SciFact training/evaluation pipeline with per-query metrics and data attribution.

The research generator currently uses **Google Gemini**. The astronomy tutor uses **Amazon Nova / Bedrock**. The included relevance model runs locally and does not require either provider's API key.

## ML results

On **300 held-out SciFact retrieval queries**, after training on **807 queries** and choosing regularization within the training split:

| Retrieval configuration | MRR@10 | nDCG@10 | Recall@5 |
| --- | ---: | ---: | ---: |
| **BM25 baseline — default** | **0.6340** | **0.6658** | **0.7226** |
| Trained logistic reranker | 0.6125 | 0.6530 | 0.7034 |

The trained model did not beat BM25 in this experiment, so the stronger measured baseline stays the default. The cross-encoder backend is optional and has not yet been benchmarked in this project. These are evidence-retrieval metrics, not factual-answer accuracy or proof of hallucination reduction.

[Architecture, experiment and limitations](docs/RAG_AND_ML.md) · [Evaluation JSON](docs/retrieval-evaluation.json) · [Per-query CSV](docs/retrieval-evaluation.csv) · [Trained model](models/evidence_ranker.json)

## Offline retrieval demo

Python 3.10+ recommended. Core passage storage, BM25 and JSON-model inference use Python's standard library. No cloud key is needed for these commands:

```bash
python -m ml.rag_cli ingest docs/RAG_AND_ML.md --title "Central-Mind RAG design"
python -m ml.rag_cli search "How is evidence kept current?"
# Explicitly enable the bundled trained reranker:
python -m ml.rag_cli --model models/evidence_ranker.json search "How is evidence kept current?"
```

The demo indexes a local document. It does not fetch current web information. Stored passages expire after 24 hours by default; re-ingest the source to refresh its contents.

## Run the root API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# Set GOOGLE_API_KEY and configure AWS credentials for cloud features as needed.
python main.py
```

The existing app includes cloud-dependent Nova and research services. A full live run needs their dependencies and provider configuration; offline retrieval does not. The `astrovoice/` directory is a separate astronomy app and does not yet share the root app's new RAG implementation.

| Endpoint | Behavior |
| --- | --- |
| `POST /research` | Live web search → indexed/ranked passages → Gemini answer with citation metadata |
| `POST /chat` | Live NASA/arXiv retrieval → indexed/ranked abstracts → Nova tutoring |
| `GET /rag/search?query=...` | Inspect previously indexed, unexpired evidence; no live fetch or generation |
| `GET /health` | Existing health endpoint |

Research response metadata includes `ranker`, `freshness_checked_at`, `freshness_policy` and `retrieval_status`. Each source retains its URL, retrieval time, content hash and evidence kind. A fetched page is not necessarily newly published; publication dates are not invented.

### Optional learned ranking

```bash
# Lightweight trained model; no model-download dependency at inference:
export RAG_MODEL_PATH=models/evidence_ranker.json
# Or a pretrained transformer cross-encoder:
pip install -r requirements-transformers.txt
export RAG_CROSS_ENCODER=cross-encoder/ms-marco-MiniLM-L6-v2
```

The cross-encoder takes precedence when configured and downloads weights on first use. Neither backend is a truth classifier. Optional model configuration errors are explicit, rather than silently reporting a learned model while running a lexical fallback.

## Train and verify

```bash
pip install -r requirements-ml.txt
python -m ml.download_scifact
python -m ml.train_ranker
python -m unittest discover -s tests -v
```

Raw SciFact data and the local SQLite index are git-ignored under `data/`. Training coefficients and evaluation reports are included. See the [dataset attribution and methodology](docs/RAG_AND_ML.md#reproduce) before reusing the data or metrics.

## Freshness and limits

The root research and tutoring flows refresh evidence **when asked**. Stored-only retrieval applies a configurable age limit. Failed live fetches do not authorize reuse of old indexed pages; explicitly identified live search snippets can be used when page extraction fails. If no usable matching evidence remains, the service abstains.

This is not continuous monitoring, and search indexes can lag. The original claim checker remains rule-based; confidence fields are uncalibrated heuristics. The retrieval experiment does not establish general-web accuracy, reliable contradiction detection, prompt-injection resistance, or production readiness. Cloud generation and the optional cross-encoder require separate live evaluation.

## References

- [Sentence Transformers: retrieve and rerank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)
- [Anthropic: contextual retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Microsoft: freshness-aware retrieval](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-configure-freshness)
- [SciFact data, paper and licensing](https://github.com/allenai/scifact)
- [BEIR benchmark](https://github.com/beir-cellar/beir)
