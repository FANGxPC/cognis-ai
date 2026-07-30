import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "prereqs.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                slug TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                graph_json TEXT,
                questions_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS remediation_cache (
                key TEXT PRIMARY KEY,
                content_json TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                subject_slug TEXT NOT NULL,
                original_query TEXT,
                matched_node TEXT,
                root_cause_node TEXT,
                status TEXT,
                score_correct INTEGER DEFAULT 0,
                score_total INTEGER DEFAULT 0,
                traversal_path_json TEXT,
                mastery_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

def save_session_history(data: dict):
    """Persist or update a session in session_history table."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO session_history (
                session_id, subject_slug, original_query, matched_node,
                root_cause_node, status, score_correct, score_total,
                traversal_path_json, mastery_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(session_id) DO UPDATE SET
                subject_slug=excluded.subject_slug,
                original_query=excluded.original_query,
                matched_node=excluded.matched_node,
                root_cause_node=excluded.root_cause_node,
                status=excluded.status,
                score_correct=excluded.score_correct,
                score_total=excluded.score_total,
                traversal_path_json=excluded.traversal_path_json,
                mastery_json=excluded.mastery_json
            """,
            (
                data.get("session_id"),
                data.get("subject_slug", "linear_algebra"),
                data.get("original_query", ""),
                data.get("matched_node"),
                data.get("root_cause_node"),
                data.get("status", "complete"),
                data.get("score_correct", 0),
                data.get("score_total", 0),
                data.get("traversal_path_json", "[]"),
                data.get("mastery_json", "{}"),
            )
        )
        conn.commit()

def get_session_history(limit: int = 50) -> list[dict]:
    """Retrieve recent session history records."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM session_history ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        results = []
        for row in cursor.fetchall():
            d = dict(row)
            d["traversal_path"] = json.loads(d.get("traversal_path_json") or "[]")
            d["mastery"] = json.loads(d.get("mastery_json") or "{}")
            results.append(d)
        return results

def get_session_by_id(session_id: str) -> dict | None:
    """Retrieve a single session by session_id from session_history."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM session_history WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            d["traversal_path"] = json.loads(d.get("traversal_path_json") or "[]")
            d["mastery"] = json.loads(d.get("mastery_json") or "{}")
            return d
        return None

def get_session_stats() -> dict:

    """Calculate aggregate dashboard statistics."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        total_sessions = conn.execute("SELECT COUNT(*) FROM session_history").fetchone()[0]
        completed_sessions = conn.execute("SELECT COUNT(*) FROM session_history WHERE status = 'complete'").fetchone()[0]
        unique_concepts = conn.execute("SELECT COUNT(DISTINCT matched_node) FROM session_history WHERE matched_node IS NOT NULL").fetchone()[0]
        root_causes = conn.execute("SELECT COUNT(DISTINCT root_cause_node) FROM session_history WHERE root_cause_node IS NOT NULL").fetchone()[0]
        
        mastery_rate = round((completed_sessions / total_sessions * 100), 1) if total_sessions > 0 else 100.0

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "unique_concepts": unique_concepts,
            "root_causes_found": root_causes,
            "mastery_rate": mastery_rate,
        }


def save_remediation_cache(key: str, content: dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO remediation_cache (key, content_json) VALUES (?, ?)",
            (key, json.dumps(content))
        )
        conn.commit()

def get_remediation_cache(key: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT content_json FROM remediation_cache WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return None


def save_subject(slug: str, title: str, description: str, graph_data: dict, questions_data: dict):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO subjects (slug, title, description, graph_json, questions_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (slug, title, description, json.dumps(graph_data), json.dumps(questions_data))
        )
        conn.commit()

def get_all_subjects():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT slug, title, description FROM subjects")
        return [dict(row) for row in cursor.fetchall()]

def get_subject_graph(slug: str) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT graph_json FROM subjects WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return {"nodes": [], "edges": []}

def get_subject_questions(slug: str) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT questions_json FROM subjects WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return {}

def delete_subject(slug: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM subjects WHERE slug = ?", (slug,))
        conn.commit()

# Run init_db on import to ensure table exists
init_db()
