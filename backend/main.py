"""
main.py — FastAPI application entry point.

Internal endpoints (used by existing tests):
  GET  /health       → health check
  GET  /graph        → full graph JSON with mastery state
  POST /match        → free-text query → best matching node
  POST /traverse     → backward traversal path from matched node
  GET  /question     → probe question for a node
  POST /answer       → score a student's answer
  GET  /diagnose     → diagnosis summary card
  GET  /remediate    → explanation + practice questions for root cause
  POST /retest       → re-serve question after remediation

Spec-aligned endpoints (frontend contract):
  GET  /api/graph                → graph + mastery status per node
  POST /api/diagnose             → combined match + traverse + trace_log
  GET  /api/probe/next           → probe question for a node
  POST /api/probe/answer         → score answer, return next_action
  GET  /api/diagnose/explain     → root cause explanation
  GET  /api/remediation/{id}     → explanation + practice questions
  POST /api/practice/answer      → score practice answer
  POST /api/retest               → execute retest, return updated graph state
  POST /api/session/reset        → reset session mastery

"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database
import auth
from graph import load_graph, load_questions, ConceptGraph
from embeddings import NodeEmbeddingCache
from diagnostic import DiagnosticEngine


# ---------------------------------------------------------------------------
# App lifespan: load data + build embedding cache at startup
# ---------------------------------------------------------------------------

_graphs: dict[str, ConceptGraph] = {}
_questions_db: dict[str, dict[str, list[dict[str, Any]]]] = {}
_engines: dict[str, DiagnosticEngine] = {}
_node_caches: dict[str, Any] = {}

from graph import SUBJECTS_CONFIG
from embeddings import NodeEmbeddingCache

# In-memory session store  {session_id: session_dict}
_sessions: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graphs, _questions_db, _engines, _node_caches

    print("[startup] Initializing database...")
    await database.init_db()
    print("[startup] Database initialized.")

    for subject_id, conf in SUBJECTS_CONFIG.items():
        print(f"[startup] Loading subject: {subject_id}...")
        _graphs[subject_id] = load_graph(subject_id)
        _questions_db[subject_id] = load_questions(subject_id)
        
        cache = NodeEmbeddingCache()
        cache.build(_graphs[subject_id].nodes)
        _node_caches[subject_id] = cache
        
        _engines[subject_id] = DiagnosticEngine(_graphs[subject_id], _questions_db[subject_id])
    
    print("[startup] All subjects loaded. Ready.")

    yield

    # Cleanup (nothing needed for in-memory state)
    print("[shutdown] Bye!")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Prereq Sleuth API",
    description="AI-powered prerequisite diagnosis for Linear Algebra concepts.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend on any port during dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class UserRegister(BaseModel):
    email: str
    username: str
    password: str


def _require_node_cache(subject_id: str = "linear_algebra") -> NodeEmbeddingCache:
    if subject_id not in _node_caches:
        raise HTTPException(status_code=404, detail=f"Subject {subject_id} not found.")
    return _node_caches[subject_id]

class UserLogin(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    user_id: str
    username: str
    token: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: str


class MatchRequest(BaseModel):
    query: str
    session_id: str | None = None  # If provided, associates match with session


class MatchResponse(BaseModel):
    session_id: str
    matched_node_id: str
    matched_node_label: str
    score: float
    top_matches: list[dict[str, Any]]


class TraverseRequest(BaseModel):
    subject: str = "linear_algebra"
    session_id: str
    node_id: str


class AnswerRequest(BaseModel):
    session_id: str
    node_id: str
    question_id: str
    answer: str

# ---------------------------------------------------------------------------
# Subjects endpoint
# ---------------------------------------------------------------------------

@app.get("/api/subjects")
async def list_subjects():
    subjects = []
    for sid, conf in SUBJECTS_CONFIG.items():
        subjects.append({
            "id": sid,
            "title": conf["title"],
            "description": conf["description"]
        })
    return {"subjects": subjects}

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=AuthResponse)
async def register(user: UserRegister):
    existing = await database.get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = auth.hash_password(user.password)
    user_id = await database.create_user(user.email, user.username, password_hash)
    
    token = auth.create_access_token({"sub": user_id, "email": user.email})
    return AuthResponse(user_id=user_id, username=user.username, token=token)

@app.post("/api/auth/login", response_model=AuthResponse)
async def login(user: UserLogin):
    db_user = await database.get_user_by_email(user.email)
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    if not auth.verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    token = auth.create_access_token({"sub": db_user["id"], "email": db_user["email"]})
    return AuthResponse(user_id=db_user["id"], username=db_user["username"], token=token)

@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(auth.get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        created_at=current_user["created_at"]
    )

# ---------------------------------------------------------------------------
# Internal endpoints (Legacy / for testing)
# ---------------------------------------------------------------------------



@app.get("/api/sessions")
async def list_sessions(current_user: dict = Depends(auth.get_current_user)):
    sessions = await database.list_user_sessions(current_user["id"])
    return sessions

@app.get("/api/sessions/{session_id}")
async def get_session_detail(session_id: str, current_user: dict = Depends(auth.get_current_user)):
    return await _require_session(session_id, current_user)

# --- Spec-aligned request models ---

class DiagnoseRequest(BaseModel):
    subject: str = "linear_algebra"
    session_id: str | None = None
    query: str


class ProbeAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str | int  # spec uses int (index) or letter


class PracticeAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str | int


class RetestRequest(BaseModel):
    session_id: str
    original_node_id: str | None = None


class SessionResetRequest(BaseModel):
    session_id: str

class ExplainRequest(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_graph(subject_id: str = "linear_algebra") -> ConceptGraph:
    if subject_id not in _graphs:
        raise HTTPException(status_code=404, detail=f"Subject {subject_id} not found.")
    return _graphs[subject_id]

def _require_questions(subject_id: str = "linear_algebra") -> dict[str, list[dict]]:
    if subject_id not in _questions_db:
        raise HTTPException(status_code=404, detail=f"Subject {subject_id} not found.")
    return _questions_db[subject_id]

def _require_engine(subject_id: str = "linear_algebra") -> DiagnosticEngine:
    if subject_id not in _engines:
        raise HTTPException(status_code=404, detail=f"Subject {subject_id} not found.")
    return _engines[subject_id]


async def _require_session(session_id: str, current_user: dict | None = None) -> dict[str, Any]:
    session = _sessions.get(session_id)
    if not session:
        session = await database.load_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
        _sessions[session_id] = session

    if current_user and session.get("user_id") and session["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this session")
    return session


async def _get_or_create_session(session_id: str | None, current_user: dict | None = None) -> tuple[str, dict]:
    """Return (session_id, session_dict) — creating a new session if needed."""
    if session_id:
        session = _sessions.get(session_id)
        if not session:
            session = await database.load_session(session_id)
        if session:
            if current_user and session.get("user_id") and session["user_id"] != current_user["id"]:
                raise HTTPException(status_code=403, detail="Not authorized to access this session")
            _sessions[session_id] = session
            return session_id, session

    sid = session_id or str(uuid.uuid4())
    session: dict[str, Any] = {
        "session_id": sid,
        "user_id": current_user["id"] if current_user else None,
        "original_query": None,
        "matched_node": None,
        "subject": "linear_algebra",
        "traversal_path": [],
        "traversal_index": 0,
        "mastery": {},
        "asked_questions": {},
        "root_cause_node": None,
        "status": "idle",
        "practice_attempts": {},
    }
    _sessions[sid] = session
    if current_user:
        await database.save_session(session)
    return sid, session


def _mastery_to_status(mastery_val: float | None) -> str:
    """Convert a mastery score to a status string."""
    if mastery_val is None:
        return "untested"
    elif mastery_val >= 1.0:
        return "mastered"
    else:
        return "weak"


# ---------------------------------------------------------------------------
# Routes: Core
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Verify the server is up and data is loaded."""
    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')
    return {
        "status": "ok",
        "nodes": str(len(graph.nodes)),
        "edges": str(len(graph.edges)),
        "embeddings_ready": str(_require_node_cache("linear_algebra").is_built),
    }


@app.get("/graph", tags=["graph"])
def get_graph(session_id: str | None = Query(default=None)) -> dict[str, Any]:
    """
    Return the full concept graph (nodes + edges).
    If a session_id is given, mastery state from that session is overlaid.
    """
    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')
    graph_dict = graph.to_dict()

    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        mastery = session.get("mastery", {})
        for node in graph_dict["nodes"]:
            node["mastery"] = mastery.get(node["id"], None)

    return graph_dict


@app.post("/match", response_model=MatchResponse, tags=["core"])
async def match_query(req: MatchRequest, current_user: dict = Depends(auth.get_current_user)) -> MatchResponse:
    """
    Embed the student's free-text query and find the best matching concept node.
    Creates or updates a session.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not _require_node_cache('linear_algebra').is_built:
        raise HTTPException(status_code=503, detail="Embedding cache not ready.")

    top_matches = _require_node_cache("linear_algebra").match_query(req.query, top_k=3)
    best = top_matches[0]

    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')
    sid, session = await _get_or_create_session(req.session_id, current_user)

    # Reset session state for a fresh diagnosis
    session["original_query"] = req.query
    session["matched_node"] = best["node_id"]
    session["traversal_path"] = []
    session["traversal_index"] = 0
    session["mastery"] = {}
    session["asked_questions"] = {}
    session["root_cause_node"] = None
    session["status"] = "matched"

    matched_node = graph.get_node(best["node_id"])
    await database.save_session(session)

    return MatchResponse(
        session_id=sid,
        matched_node_id=best["node_id"],
        matched_node_label=matched_node.label,
        score=round(best["score"], 4),
        top_matches=top_matches,
    )


# ---------------------------------------------------------------------------
# Routes: Diagnostic Flow
# ---------------------------------------------------------------------------

@app.post("/api/diagnose/explain", tags=["api-spec"])
async def api_diagnose_explain(req: ExplainRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Returns the final diagnostic explanation.
    Fails if the session hasn't completed diagnosis yet.
    """
    sid, session = await _get_or_create_session(req.session_id, current_user)
    if session["status"] != "diagnosed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate explanation before diagnosis is complete. Current status: {session['status']}",
        )

    engine = _require_engine(session.get("subject", "linear_algebra"))
    return engine.generate_explanation(session)


@app.post("/api/explain/ai", tags=["api-spec"])
async def api_explain_ai(req: ExplainRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Returns the AI-generated diagnostic explanation.
    """
    sid, session = await _get_or_create_session(req.session_id, current_user)
    if session["status"] != "diagnosed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate explanation before diagnosis is complete. Current status: {session['status']}",
        )

    engine = _require_engine(session.get("subject", "linear_algebra"))
    return await engine.generate_ai_explanation(session)

@app.post("/traverse", tags=["core"])
async def traverse(req: TraverseRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Build a backward traversal path from the matched node and
    initialize the probing session.
    """
    session = await _require_session(req.session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    # Validate node
    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')
    if req.node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{req.node_id}' not found.")

    try:
        result = engine.init_traversal(session, req.node_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await database.save_session(session)

    return result


@app.get("/question", tags=["core"])
async def get_question(
    node_id: str = Query(...),
    session_id: str = Query(...),
    current_user: dict = Depends(auth.get_current_user)
) -> dict[str, Any]:
    """
    Serve a probe question for the given node in the context of a session.
    """
    session = await _require_session(session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')
    if node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    question = engine.get_probe_question(session, node_id)
    if question is None:
        raise HTTPException(
            status_code=404,
            detail=f"No unasked questions remaining for node '{node_id}'.",
        )

    return {
        "session_id": session_id,
        **question,
    }


@app.post("/answer", tags=["core"])
async def submit_answer(req: AnswerRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Score a student's answer and advance the diagnostic traversal.
    """
    session = await _require_session(req.session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    # Validate answer format
    if req.answer.strip().upper() not in {"A", "B", "C", "D"}:
        raise HTTPException(
            status_code=400,
            detail=f"Answer must be one of A, B, C, D. Got: '{req.answer}'.",
        )

    try:
        result = engine.record_answer(session, req.node_id, req.question_id, req.answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await database.save_session(session)

    return result


@app.get("/diagnose", tags=["core"])
async def get_diagnosis(session_id: str = Query(...), current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Return the diagnostic summary card for a completed traversal.
    """
    session = await _require_session(session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Diagnosis not ready. Session status is '{session['status']}'. "
                f"Complete the traversal first."
            ),
        )

    return engine.diagnose(session)


@app.get("/remediate", tags=["core"])
async def get_remediation(node_id: str = Query(...)) -> dict[str, Any]:
    """
    Return explanation + practice questions for the root cause node.
    """
    engine = _require_engine("linear_algebra")

    graph = _require_graph("linear_algebra")

    if node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    return engine.get_remediation(node_id)


@app.post("/retest", tags=["core"])
async def retest(session_id: str = Query(...), current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Re-serve a question for the root-cause node after remediation.
    """
    session = await _require_session(session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    if session["status"] not in ("diagnosed", "retesting"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot retest. Session status is '{session['status']}'. "
                f"Complete diagnosis first."
            ),
        )

    return engine.prepare_retest(session)


# ---------------------------------------------------------------------------
# Routes: Spec-aligned /api/ endpoints (frontend contract)
# ---------------------------------------------------------------------------

@app.get("/api/graph", tags=["api-spec"])
def api_get_graph(
    session_id: str | None = Query(default=None),
    subject: str | None = Query(default=None),  # accepted but ignored (single-subject V1)
) -> dict[str, Any]:
    """
    Spec-aligned graph endpoint.
    Returns nodes with `status` field (untested/weak/mastered) instead of raw mastery float.
    """
    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')
    graph_dict = graph.to_dict()

    mastery: dict[str, float] = {}
    if session_id and session_id in _sessions:
        mastery = _sessions[session_id].get("mastery", {})

    for node in graph_dict["nodes"]:
        m = mastery.get(node["id"])
        node["status"] = _mastery_to_status(m)
        node["mastery"] = m

    return graph_dict


@app.post("/api/diagnose", tags=["api-spec"])
async def api_diagnose(req: DiagnoseRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Spec-aligned combined diagnose endpoint.
    Embeds the query, matches to nearest node, builds traversal path,
    generates trace_log — all in one response.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not _require_node_cache('linear_algebra').is_built:
        raise HTTPException(status_code=503, detail="Embedding cache not ready.")

    engine = _require_engine(req.subject if hasattr(req, 'subject') and req.subject else 'linear_algebra')
    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')

    # 1. Match query to node
    top_matches = _require_node_cache("linear_algebra").match_query(req.query, top_k=3)
    best = top_matches[0]
    matched_node_id = best["node_id"]
    similarity_score = round(best["score"], 4)

    # 2. Get or create session
    sid, session = await _get_or_create_session(req.session_id, current_user)
    session["original_query"] = req.query
    session["matched_node"] = matched_node_id
    session["status"] = "matched"

    # 3. Init traversal
    trav_result = engine.init_traversal(session, matched_node_id)
    traversal_path = trav_result["traversal_path"]

    # 4. Generate trace log
    trace_log = engine.generate_trace_log(
        req.query, matched_node_id, similarity_score, traversal_path
    )
    await database.save_session(session)

    return {
        "session_id": sid,
        "matched_node_id": matched_node_id,
        "similarity_score": similarity_score,
        "traversal_path": traversal_path,
        "trace_log": trace_log,
    }


@app.get("/api/probe/next", tags=["api-spec"])
async def api_probe_next(
    session_id: str = Query(...),
    node_id: str = Query(...),
    current_user: dict = Depends(auth.get_current_user)
) -> dict[str, Any]:
    """
    Spec-aligned probe question endpoint.
    Returns the next unasked question for a node.
    """
    session = await _require_session(session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))
    graph = _require_graph(session.get('subject', 'linear_algebra') if 'session' in locals() else 'linear_algebra')

    if node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    question = engine.get_probe_question(session, node_id)
    if question is None:
        raise HTTPException(
            status_code=404,
            detail=f"No unasked questions remaining for node '{node_id}'.",
        )

    # Remap field names to match spec
    return {
        "question_id": question["question_id"],
        "prompt": question["question"],
        "type": "mcq",
        "options": question["choices"],
    }


@app.post("/api/probe/answer", tags=["api-spec"])
async def api_probe_answer(req: ProbeAnswerRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Spec-aligned probe answer endpoint.
    Scores the answer and returns next_action as
    'continue_traversal' or 'root_confirmed'.
    """
    session = await _require_session(req.session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    # Normalize answer: accept int (index) or letter
    answer = str(req.answer).strip()
    if answer.isdigit():
        answer = chr(65 + int(answer))  # 0→A, 1→B, 2→C, 3→D

    if answer.upper() not in {"A", "B", "C", "D"}:
        raise HTTPException(
            status_code=400,
            detail=f"Answer must be A, B, C, D or 0-3. Got: '{req.answer}'.",
        )

    # Figure out which node we're currently probing
    path = session.get("traversal_path", [])
    idx = session.get("traversal_index", 0)
    if idx >= len(path):
        raise HTTPException(status_code=400, detail="Traversal already complete.")
    current_node = path[idx]

    try:
        result = engine.record_answer(session, current_node, req.question_id, answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Remap next_action to spec values
    internal_action = result.get("next_action", "continue")
    if internal_action == "diagnosed":
        spec_action = "root_confirmed"
    elif internal_action == "continue_node":
        spec_action = "continue_node"
    else:
        spec_action = "continue_traversal"

    # Compute updated_status for the current node
    mastery_val = session["mastery"].get(current_node)
    updated_status = _mastery_to_status(mastery_val)

    return {
        "correct": result["is_correct"],
        "updated_status": updated_status,
        "next_action": spec_action,
    }


@app.get("/api/diagnose/explain", tags=["api-spec"])
async def api_diagnose_explain(session_id: str = Query(...), current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Spec-aligned explanation endpoint.
    Returns the plain-language explanation of the confirmed root cause.
    """
    session = await _require_session(session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Diagnosis not ready. Session status is '{session['status']}'. "
                f"Complete the traversal first."
            ),
        )

    return engine.generate_explanation(session)


@app.get("/api/remediation/{node_id}", tags=["api-spec"])
def api_get_remediation(node_id: str) -> dict[str, Any]:
    """
    Spec-aligned remediation endpoint (path parameter).
    Returns explanation + practice questions for a node.
    """
    engine = _require_engine("linear_algebra")
    graph = _require_graph("linear_algebra")

    if node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    result = engine.get_remediation(node_id)

    # Remap to spec shape
    return {
        "explanation": result["description"],
        "practice_questions": [
            {
                "question_id": q["question_id"],
                "prompt": q["question"],
                "options": q["choices"],
            }
            for q in result["practice_questions"]
        ],
    }


@app.post("/api/practice/answer", tags=["api-spec"])
async def api_practice_answer(req: PracticeAnswerRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Spec-aligned practice answer endpoint.
    Scores a practice answer during remediation.
    """
    session = await _require_session(req.session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        raise HTTPException(
            status_code=400,
            detail="Must complete diagnosis before practicing.",
        )

    # Normalize answer
    answer = str(req.answer).strip()
    if answer.isdigit():
        answer = chr(65 + int(answer))

    if answer.upper() not in {"A", "B", "C", "D"}:
        raise HTTPException(
            status_code=400,
            detail=f"Answer must be A, B, C, D or 0-3. Got: '{req.answer}'.",
        )

    try:
        result = engine.score_practice_answer(session, req.question_id, answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "correct": result["correct"],
        "node_mastered": result["node_mastered"],
    }


@app.post("/api/retest", tags=["api-spec"])
async def api_retest(req: RetestRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Spec-aligned retest endpoint.
    Marks the root cause and traversal path as mastered.
    Returns {solved, updated_graph_state}.
    """
    session = await _require_session(req.session_id, current_user)
    engine = _require_engine(session.get('subject', 'linear_algebra'))

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot retest. Session status is '{session['status']}'. "
                f"Complete diagnosis first."
            ),
        )

    return engine.execute_retest(session)


@app.post("/api/session/reset", tags=["api-spec"])
async def api_session_reset(req: SessionResetRequest, current_user: dict = Depends(auth.get_current_user)) -> dict[str, Any]:
    """
    Spec-aligned session reset.
    Wipes mastery state back to untested for a fresh run.
    """
    sid, session = await _get_or_create_session(req.session_id, current_user)

    session["original_query"] = None
    session["matched_node"] = None
    session["traversal_path"] = []
    session["traversal_index"] = 0
    session["mastery"] = {}
    session["asked_questions"] = {}
    session["root_cause_node"] = None
    session["status"] = "idle"
    session.pop("practice_attempts", None)

    await database.save_session(session)
    return {"session_id": sid, "status": "reset"}


# ---------------------------------------------------------------------------
# Demo profile loader
# ---------------------------------------------------------------------------

_DEMO_PROFILES_FILE = Path(__file__).parent / "data" / "demo_profiles.json"


@app.get("/api/demo/profiles", tags=["api-spec"])
def api_demo_profiles() -> dict[str, Any]:
    """Return pre-seeded demo profiles for impressive demo runs."""
    if not _DEMO_PROFILES_FILE.exists():
        return {"profiles": []}
    with open(_DEMO_PROFILES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/demo/load", tags=["api-spec"])
def api_demo_load(profile_name: str = Query(...)) -> dict[str, Any]:
    """
    Load a pre-seeded demo profile into a new session.
    Returns the session_id that can be used to continue the demo.
    """
    if not _DEMO_PROFILES_FILE.exists():
        raise HTTPException(status_code=404, detail="No demo profiles found.")

    with open(_DEMO_PROFILES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    profiles = data.get("profiles", [])
    profile = next((p for p in profiles if p["name"] == profile_name), None)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found.")

    sid = str(uuid.uuid4())
    session = {
        "session_id": sid,
        "original_query": profile["query"],
        "matched_node": profile["matched_node"],
        "traversal_path": profile["traversal_path"],
        "traversal_index": len(profile.get("mastery", {})),
        "mastery": profile.get("mastery", {}),
        "asked_questions": profile.get("asked_questions", {}),
        "root_cause_node": profile.get("root_cause_node"),
        "status": profile.get("status", "diagnosed"),
    }
    _sessions[sid] = session

    return {"session_id": sid, "profile_name": profile_name, "status": session["status"]}
