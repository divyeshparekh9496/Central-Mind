"""
LearnerProfile — persists per-session learning state in SQLite.
Tracks level progression and topics covered for adaptive Nova prompts.
"""
import sqlite3
import json
from typing import List, Dict, Any


DB_PATH = "/tmp/astrovoice_v2.db"

LEVELS = ["beginner", "intermediate", "expert"]
LEVEL_UP_THRESHOLD = 5   # correct answers before advancing level


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_learner_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learner_profiles (
            session_id   TEXT PRIMARY KEY,
            level        TEXT DEFAULT 'beginner',
            topics       TEXT DEFAULT '[]',
            correct      INTEGER DEFAULT 0,
            exchanges    INTEGER DEFAULT 0,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


class LearnerProfile:
    def __init__(
        self,
        session_id: str,
        level: str = "beginner",
        topics: List[str] = None,
        correct: int = 0,
        exchanges: int = 0,
    ):
        self.session_id = session_id
        self.level = level
        self.topics: List[str] = topics or []
        self.correct = correct
        self.exchanges = exchanges

    # ------------------------------------------------------------------
    def add_topic(self, topic: str):
        if topic and topic not in self.topics:
            self.topics.append(topic)

    def record_correct(self):
        self.correct += 1
        self._maybe_advance()

    def record_exchange(self):
        self.exchanges += 1

    def _maybe_advance(self):
        current_idx = LEVELS.index(self.level)
        if self.correct >= LEVEL_UP_THRESHOLD * (current_idx + 1) and current_idx < len(LEVELS) - 1:
            self.level = LEVELS[current_idx + 1]

    # ------------------------------------------------------------------
    def save(self):
        conn = _get_conn()
        conn.execute("""
            INSERT INTO learner_profiles (session_id, level, topics, correct, exchanges)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                level=excluded.level,
                topics=excluded.topics,
                correct=excluded.correct,
                exchanges=excluded.exchanges,
                updated_at=CURRENT_TIMESTAMP
        """, (self.session_id, self.level, json.dumps(self.topics), self.correct, self.exchanges))
        conn.commit()
        conn.close()

    @classmethod
    def load(cls, session_id: str) -> "LearnerProfile":
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM learner_profiles WHERE session_id = ?", (session_id,)
        ).fetchone()
        conn.close()
        if row:
            return cls(
                session_id=row["session_id"],
                level=row["level"],
                topics=json.loads(row["topics"]),
                correct=row["correct"],
                exchanges=row["exchanges"],
            )
        return cls(session_id=session_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "level": self.level,
            "topics_covered": self.topics,
            "correct_answers": self.correct,
            "total_exchanges": self.exchanges,
        }
