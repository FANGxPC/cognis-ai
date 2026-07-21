"""
main.py — FastAPI application entry point.

Endpoints:
  GET  /health       → health check
  GET  /graph        → full graph JSON with mastery state
  POST /match        → free-text query → best matching node
  POST /traverse     → backward traversal path from matched node
  GET  /question     → probe question for a node
  POST /answer       → score a student's answer
  GET  /diagnose     → diagnosis summary card
  GET  /remediate    → explanation + practice questions for root cause
  POST /retest       → re-serve question after remediation

"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph import load_graph, load_questions, ConceptGraph
from embeddings import node_cache
from diagnostic import DiagnosticEngine


# ---------------------------------------------------------------------------
# App lifespan: load data + build embedding cache at startup
# ---------------------------------------------------------------------------

_graph: ConceptGraph | None = None
_questions: dict[str, list[dict[str, Any]]] | None = None
_engine: DiagnosticEngine | None = None

# In-memory session store  {session_id: session_dict}
_sessions: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _questions, _engine

    print("[startup] Loading concept graph...")
    _graph = load_graph()
    print(f"[startup] Graph loaded: {len(_graph.nodes)} nodes, {len(_graph.edges)} edges")

    print("[startup] Loading question bank...")
    _questions = load_questions()
    print(f"[startup] Questions loaded for {len(_questions)} nodes")

    print("[startup] Building node embedding cache...")
    node_cache.build(_graph.nodes)
    print("[startup] Embedding cache ready.")

    _engine = DiagnosticEngine(_graph, _questions)
    print("[startup] Diagnostic engine initialized. Ready.")

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
    session_id: str
    node_id: str


class AnswerRequest(BaseModel):
    session_id: str
    node_id: str
    question_id: str
    answer: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_graph() -> ConceptGraph:
    if _graph is None:
        raise HTTPException(status_code=503, detail="Graph not loaded yet.")
    return _graph


def _require_questions() -> dict[str, list[dict]]:
    if _questions is None:
        raise HTTPException(status_code=503, detail="Questions not loaded yet.")
    return _questions


def _require_engine() -> DiagnosticEngine:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Diagnostic engine not initialized.")
    return _engine


def _require_session(session_id: str) -> dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return _sessions[session_id]


def _get_or_create_session(session_id: str | None) -> tuple[str, dict]:
    """Return (session_id, session_dict) — creating a new session if needed."""
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]
    sid = session_id or str(uuid.uuid4())
    session: dict[str, Any] = {
        "session_id": sid,
        "original_query": None,
        "matched_node": None,
        "traversal_path": [],
        "traversal_index": 0,       # which step of the path we're probing
        "mastery": {},               # {node_id: float}
        "asked_questions": {},       # {node_id: [question_id, ...]}
        "root_cause_node": None,
        "status": "idle",            # idle | matched | traversing | diagnosed | retesting | complete
    }
    _sessions[sid] = session
    return sid, session


# ---------------------------------------------------------------------------
# Routes: Core
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Verify the server is up and data is loaded."""
    graph = _require_graph()
    return {
        "status": "ok",
        "nodes": str(len(graph.nodes)),
        "edges": str(len(graph.edges)),
        "embeddings_ready": str(node_cache.is_built),
    }


@app.get("/graph", tags=["graph"])
def get_graph(session_id: str | None = Query(default=None)) -> dict[str, Any]:
    """
    Return the full concept graph (nodes + edges).
    If a session_id is given, mastery state from that session is overlaid.
    """
    graph = _require_graph()
    graph_dict = graph.to_dict()

    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        mastery = session.get("mastery", {})
        for node in graph_dict["nodes"]:
            node["mastery"] = mastery.get(node["id"], None)

    return graph_dict


@app.post("/match", response_model=MatchResponse, tags=["core"])
def match_query(req: MatchRequest) -> MatchResponse:
    """
    Embed the student's free-text query and find the best matching concept node.
    Creates or updates a session.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    if not node_cache.is_built:
        raise HTTPException(status_code=503, detail="Embedding cache not ready.")

    top_matches = node_cache.match_query(req.query, top_k=3)
    best = top_matches[0]

    graph = _require_graph()
    sid, session = _get_or_create_session(req.session_id)

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

@app.post("/traverse", tags=["core"])
def traverse(req: TraverseRequest) -> dict[str, Any]:
    """
    Build a backward traversal path from the matched node and
    initialize the probing session.
    """
    engine = _require_engine()
    session = _require_session(req.session_id)

    # Validate node
    graph = _require_graph()
    if req.node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{req.node_id}' not found.")

    try:
        result = engine.init_traversal(session, req.node_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/question", tags=["core"])
def get_question(
    node_id: str = Query(...),
    session_id: str = Query(...),
) -> dict[str, Any]:
    """
    Serve a probe question for the given node in the context of a session.
    """
    engine = _require_engine()
    session = _require_session(session_id)

    graph = _require_graph()
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
def submit_answer(req: AnswerRequest) -> dict[str, Any]:
    """
    Score a student's answer and advance the diagnostic traversal.
    """
    engine = _require_engine()
    session = _require_session(req.session_id)

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

    return result


@app.get("/diagnose", tags=["core"])
def get_diagnosis(session_id: str = Query(...)) -> dict[str, Any]:
    """
    Return the diagnostic summary card for a completed traversal.
    """
    engine = _require_engine()
    session = _require_session(session_id)

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
def get_remediation(node_id: str = Query(...)) -> dict[str, Any]:
    """
    Return explanation + practice questions for the root cause node.
    """
    engine = _require_engine()
    graph = _require_graph()

    if node_id not in graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    return engine.get_remediation(node_id)


@app.post("/retest", tags=["core"])
def retest(session_id: str = Query(...)) -> dict[str, Any]:
    """
    Re-serve a question for the root-cause node after remediation.
    """
    engine = _require_engine()
    session = _require_session(session_id)

    if session["status"] not in ("diagnosed", "retesting"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot retest. Session status is '{session['status']}'. "
                f"Complete diagnosis first."
            ),
        )

    return engine.prepare_retest(session)
