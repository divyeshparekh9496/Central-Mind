"""Persistent versioned passages with per-request retrieval and freshness checks."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from services.rag.retrieval import EvidenceRanker


def utcnow():
    return datetime.now(timezone.utc)


def chunk_text(text, size=180, overlap=35):
    if size < 1 or not 0 <= overlap < size:
        raise ValueError('Chunk overlap must be smaller than positive chunk size.')
    words = text.split()
    for start in range(0,len(words),size-overlap):
        yield ' '.join(words[start:start+size])
        if start+size >= len(words):
            break


class PassageStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('CREATE TABLE IF NOT EXISTS sources (url TEXT PRIMARY KEY, document TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def upsert(self, source):
        if not source.get('url') or not source.get('text', '').strip():
            raise ValueError('A source needs a URL and nonempty text.')
        item = dict(source)
        item['fetched_at'] = item.get('fetched_at') or utcnow().isoformat()
        parsed = datetime.fromisoformat(item['fetched_at'])
        if parsed.tzinfo is None:
            raise ValueError('fetched_at must include a timezone.')
        item['content_hash'] = hashlib.sha256(item['text'].encode()).hexdigest()
        # Whole-document replacement means changed pages cannot retain old chunks.
        with self.connect() as conn:
            conn.execute('INSERT OR REPLACE INTO sources VALUES (?,?)', (item['url'],json.dumps(item)))
        return item

    def passages(self, urls=None, max_age_hours=24, now=None):
        now = now or utcnow()
        cutoff = now-timedelta(hours=max_age_hours)
        allowed = set(urls) if urls is not None else None
        with self.connect() as conn:
            rows = conn.execute('SELECT document FROM sources').fetchall()
        output = []
        for (raw,) in rows:
            doc = json.loads(raw)
            if allowed is not None and doc['url'] not in allowed:
                continue
            fetched = datetime.fromisoformat(doc['fetched_at'])
            if fetched < cutoff or fetched > now+timedelta(minutes=5):
                continue
            for i,text in enumerate(chunk_text(doc['text'])):
                output.append(dict(doc, text=text, id=f"{doc['content_hash']}:{i}", chunk_index=i))
        return output


class RAGPipeline:
    def __init__(self, path='data/rag.sqlite3', model_path=None,
                 cross_encoder=None, max_age_hours=24):
        if max_age_hours <= 0:
            raise ValueError("max_age_hours must be positive")
        self.store = PassageStore(path)
        self.ranker = EvidenceRanker(model_path, cross_encoder)
        self.max_age_hours = max_age_hours

    def ingest(self, documents):
        return [self.store.upsert(document) for document in documents]

    def retrieve(self, query, urls=None, limit=6):
        passages = self.store.passages(urls=urls,max_age_hours=self.max_age_hours)
        ranked = self.ranker.rank(query,passages,limit=limit)
        # Citations and content travel together; failed fetches cannot shift IDs.
        return [dict(item,citation_id=i+1) for i,item in enumerate(ranked)]

    def refresh_and_retrieve(self, query, documents, limit=6):
        ingested = self.ingest(documents)
        # Only URLs actually refreshed on this request may supply online evidence.
        return self.retrieve(query,urls=[d['url'] for d in ingested],limit=limit)
