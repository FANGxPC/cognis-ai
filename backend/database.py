import aiosqlite
import json
import uuid
from typing import Any, Dict, List, Optional
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "prereq_sleuth.db"


async def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                email       TEXT UNIQUE NOT NULL,
                username    TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL REFERENCES users(id),
                query           TEXT,
                matched_node    TEXT,
                subject         TEXT DEFAULT 'linear_algebra',
                traversal_path  TEXT,
                traversal_index INTEGER DEFAULT 0,
                mastery         TEXT,
                asked_questions TEXT,
                root_cause_node TEXT,
                status          TEXT DEFAULT 'idle',
                practice_attempts TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

# --- Users ---

async def create_user(email: str, username: str, password_hash: str) -> str:
    user_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (id, email, username, password) VALUES (?, ?, ?, ?)",
            (user_id, email, username, password_hash)
        )
        await db.commit()
    return user_id

async def get_user_by_email(email: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_user_by_id(user_id: str) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

# --- Sessions ---

async def save_session(session: Dict[str, Any]):
    session_id = session['session_id']
    user_id = session['user_id']
    query = session.get('original_query')
    matched_node = session.get('matched_node')
    subject = session.get('subject', 'linear_algebra')
    traversal_path = json.dumps(session.get('traversal_path', []))
    traversal_index = session.get('traversal_index', 0)
    mastery = json.dumps(session.get('mastery', {}))
    asked_questions = json.dumps(session.get('asked_questions', {}))
    root_cause_node = session.get('root_cause_node')
    status = session.get('status', 'idle')
    practice_attempts = json.dumps(session.get('practice_attempts', {}))

    async with aiosqlite.connect(DB_PATH) as db:
        # Upsert
        await db.execute('''
            INSERT INTO sessions (
                id, user_id, query, matched_node, subject, traversal_path, 
                traversal_index, mastery, asked_questions, root_cause_node, status, practice_attempts, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                query=excluded.query,
                matched_node=excluded.matched_node,
                subject=excluded.subject,
                traversal_path=excluded.traversal_path,
                traversal_index=excluded.traversal_index,
                mastery=excluded.mastery,
                asked_questions=excluded.asked_questions,
                root_cause_node=excluded.root_cause_node,
                status=excluded.status,
                practice_attempts=excluded.practice_attempts,
                updated_at=CURRENT_TIMESTAMP
        ''', (session_id, user_id, query, matched_node, subject, traversal_path, traversal_index, mastery, asked_questions, root_cause_node, status, practice_attempts))
        await db.commit()

async def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        if not row:
            return None
            
        return {
            "session_id": row["id"],
            "user_id": row["user_id"],
            "original_query": row["query"],
            "matched_node": row["matched_node"],
            "subject": row["subject"],
            "traversal_path": json.loads(row["traversal_path"]) if row["traversal_path"] else [],
            "traversal_index": row["traversal_index"],
            "mastery": json.loads(row["mastery"]) if row["mastery"] else {},
            "asked_questions": json.loads(row["asked_questions"]) if row["asked_questions"] else {},
            "root_cause_node": row["root_cause_node"],
            "status": row["status"],
            "practice_attempts": json.loads(row["practice_attempts"]) if row["practice_attempts"] else {}
        }

async def list_user_sessions(user_id: str) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
        rows = await cursor.fetchall()
        
        sessions = []
        for row in rows:
            sessions.append({
                "session_id": row["id"],
                "query": row["query"],
                "matched_node": row["matched_node"],
                "subject": row["subject"],
                "status": row["status"],
                "root_cause": row["root_cause_node"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })
        return sessions
