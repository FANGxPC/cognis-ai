"""
main.py — FastAPI application entry point.

Endpoints implemented by Day 1:
  GET  /health       → health check
  GET  /graph        → full graph JSON with mastery state
  POST /match        → free-text query → best matching node

Endpoints stubbed for later days:
  POST /traverse     → (Day 5) backward traversal path
  GET  /question     → (Day 5-6) probe question for a node
  POST /answer       → (Day 6) score a student's answer
  GET  /diagnose     → (Day 7) diagnosis summary card
  GET  /remediate    → (Day 7) remediation content
  POST /retest       → (Day 8) retest after remediation
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


# ---------------------------------------------------------------------------
# App lifespan: load data + build embedding cache at startup
# ---------------------------------------------------------------------------

_graph: ConceptGraph | None = None
_questions: dict[str, list[dict[str, Any]]] | None = None

# In-memory session store  {session_id: session_dict}
_sessions: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _questions

    print("[startup] Loading concept graph...")
    _graph = load_graph()
    print(f"[startup] Graph loaded: {len(_graph.nodes)} nodes, {len(_graph.edges)} edges")

    print("[startup] Loading question bank...")
    _questions = load_questions()
    print(f"[startup] Questions loaded for {len(_questions)} nodes")

    print("[startup] Building node embedding cache...")
    node_cache.build(_graph.nodes)
    print("[startup] Ready.")

    yield

    # Cleanup (nothing needed for in-memory state)
    print("[shutdown] Bye!")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Prereq Sleuth API",
    description="AI-powered prerequisite diagnosis for Linear Algebra concepts.",
    version="0.1.0",
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
# Helper
# ---------------------------------------------------------------------------

def _require_graph() -> ConceptGraph:
    if _graph is None:
        raise HTTPException(status_code=503, detail="Graph not loaded yet.")
    return _graph


def _require_questions() -> dict[str, list[dict]]:
    if _questions is None:
        raise HTTPException(status_code=503, detail="Questions not loaded yet.")
    return _questions


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
        "root_cause_node": None,
        "status": "idle",            # idle | traversing | diagnosed | remediating | complete
    }
    _sessions[sid] = session
    return sid, session


# ---------------------------------------------------------------------------
# Routes: Day 1
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
# Routes: Stubbed for future days (return 501 Not Implemented)
# ---------------------------------------------------------------------------

@app.post("/traverse", tags=["core"])
def traverse(req: TraverseRequest) -> dict[str, Any]:
    """[Day 5] Start backward traversal from a matched node."""
    raise HTTPException(status_code=501, detail="Not implemented yet — Day 5.")


@app.get("/question", tags=["core"])
def get_question(
    node_id: str = Query(...),
    session_id: str = Query(...),
) -> dict[str, Any]:
    """[Day 5-6] Serve a probe question for a given node."""
    raise HTTPException(status_code=501, detail="Not implemented yet — Day 5.")


@app.post("/answer", tags=["core"])
def submit_answer(req: AnswerRequest) -> dict[str, Any]:
    """[Day 6] Score a student answer and update mastery."""
    raise HTTPException(status_code=501, detail="Not implemented yet — Day 6.")


@app.get("/diagnose", tags=["core"])
def get_diagnosis(session_id: str = Query(...)) -> dict[str, Any]:
    """[Day 7] Return the diagnosis summary card."""
    raise HTTPException(status_code=501, detail="Not implemented yet — Day 7.")


@app.get("/remediate", tags=["core"])
def get_remediation(node_id: str = Query(...)) -> dict[str, Any]:
    """[Day 7] Return explanation + practice questions for the root cause node."""
    raise HTTPException(status_code=501, detail="Not implemented yet — Day 7.")


@app.post("/retest", tags=["core"])
def retest(session_id: str = Query(...)) -> dict[str, Any]:
    """[Day 8] Re-serve the original question after remediation passes."""
    raise HTTPException(status_code=501, detail="Not implemented yet — Day 8.")
