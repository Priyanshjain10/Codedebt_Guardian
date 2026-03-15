"""
Persistent Memory Bank - SQLite-backed storage for agent memory.
Replaces the in-memory MemoryBank with persistence across runs.

Benefits:
- Results survive restarts (no re-analyzing the same repo)
- Analysis history for the same repo over time
- Disk-based — no memory leaks on long-running processes
"""

import json
import sqlite3
import time
import logging
import os
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "codedebt_memory.db")


class PersistentMemoryBank:
    """
    SQLite-backed persistent memory bank.
    Drop-in replacement for MemoryBank with disk persistence.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._setup()
        self._hits = 0
        self._misses = 0
        logger.info(f"PersistentMemoryBank initialized at: {db_path}")

    def _setup(self):
        """Create tables if they don't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_url TEXT NOT NULL,
                branch TEXT NOT NULL,
                analyzed_at REAL NOT NULL,
                total_issues INTEGER,
                critical INTEGER,
                high INTEGER,
                summary TEXT
            )
        """)
        self._conn.commit()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value. Returns None if missing or expired."""
        now = time.time()
        row = self._conn.execute(
            "SELECT value, expires_at FROM memory WHERE key = ?", (key,)
        ).fetchone()

        if row is None:
            self._misses += 1
            return None

        value_str, expires_at = row
        if expires_at and now > expires_at:
            self._conn.execute("DELETE FROM memory WHERE key = ?", (key,))
            self._conn.commit()
            self._misses += 1
            logger.debug(f"Cache expired: {key}")
            return None

        self._hits += 1
        return json.loads(value_str)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Store a value with optional TTL."""
        now = time.time()
        expires_at = now + ttl_seconds if ttl_seconds else None
        value_str = json.dumps(value, default=str)

        self._conn.execute("""
            INSERT OR REPLACE INTO memory (key, value, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (key, value_str, now, expires_at))
        self._conn.commit()
        logger.debug(f"Persisted: {key} (TTL: {ttl_seconds}s)")

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM memory WHERE key = ?", (key,))
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM memory")
        self._conn.commit()

    def save_analysis_history(self, repo_url: str, branch: str, summary: Dict) -> None:
        """Save an analysis result to history."""
        self._conn.execute("""
            INSERT INTO analysis_history (repo_url, branch, analyzed_at, total_issues, critical, high, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            repo_url, branch, time.time(),
            summary.get("total_issues", 0),
            summary.get("critical", 0),
            summary.get("high", 0),
            json.dumps(summary, default=str),
        ))
        self._conn.commit()

    def get_analysis_history(self, repo_url: str, limit: int = 10) -> list:
        """Get past analysis results for a repo."""
        rows = self._conn.execute("""
            SELECT repo_url, branch, analyzed_at, total_issues, critical, high, summary
            FROM analysis_history
            WHERE repo_url = ?
            ORDER BY analyzed_at DESC
            LIMIT ?
        """, (repo_url, limit)).fetchall()

        return [
            {
                "repo_url": r[0],
                "branch": r[1],
                "analyzed_at": r[2],
                "total_issues": r[3],
                "critical": r[4],
                "high": r[5],
                "summary": json.loads(r[6]),
            }
            for r in rows
        ]

    def get_all_history(self, limit: int = 50) -> list:
        """Get all analysis history across all repos."""
        rows = self._conn.execute("""
            SELECT repo_url, branch, analyzed_at, total_issues, critical, high
            FROM analysis_history
            ORDER BY analyzed_at DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [
            {"repo_url": r[0], "branch": r[1], "analyzed_at": r[2],
             "total_issues": r[3], "critical": r[4], "high": r[5]}
            for r in rows
        ]

    def stats(self) -> Dict:
        total = self._hits + self._misses
        cached_rows = self._conn.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        history_rows = self._conn.execute("SELECT COUNT(*) FROM analysis_history").fetchone()[0]
        return {
            "total_keys": cached_rows,
            "analysis_history_count": history_rows,
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0,
            "db_path": self.db_path,
        }

    def __del__(self):
        try:
            self._conn.close()
        except Exception:
            pass
