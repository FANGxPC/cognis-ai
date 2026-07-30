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
  GET  /api/subjects            → list available subjects
  GET  /api/graph               → graph + mastery status per node
  POST /api/diagnose            → combined match + traverse + trace_log
  GET  /api/probe/next          → probe question for a node
  POST /api/probe/answer        → score answer, return next_action
  GET  /api/diagnose/explain    → root cause explanation
  GET  /api/remediation/{id}    → explanation + practice questions
  POST /api/practice/answer     → score practice answer
  POST /api/retest              → execute retest, return updated graph state
  POST /api/session/reset       → reset session mastery

"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph import load_graph, load_questions, ConceptGraph
from database import get_all_subjects, save_subject, save_session_history, get_session_history, get_session_stats, get_session_by_id
from generator import generate_subject_content
from embeddings import NodeEmbeddingCache
from diagnostic import DiagnosticEngine
from chat import chat_with_tutor, get_chat_history



# ---------------------------------------------------------------------------
# Per-subject runtime data
# ---------------------------------------------------------------------------

@dataclass
class SubjectData:
    """Holds the graph, questions, embedding cache, and engine for one subject."""
    slug: str
    title: str
    description: str
    graph: ConceptGraph
    questions: dict[str, list[dict[str, Any]]]
    node_cache: NodeEmbeddingCache = field(default_factory=NodeEmbeddingCache)
    engine: DiagnosticEngine | None = None


# ---------------------------------------------------------------------------
# App lifespan: load ALL subjects + build embedding caches at startup
# ---------------------------------------------------------------------------

_subjects: dict[str, SubjectData] = {}

# In-memory session store  {session_id: session_dict}
_sessions: dict[str, dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _subjects

    subjects_list = get_all_subjects()
    for cfg in subjects_list:
        slug = cfg["slug"]
        print(f"[startup] Loading subject '{slug}'...")

        graph = load_graph(slug)
        questions = load_questions(slug)
        print(f"[startup]   {slug}: {len(graph.nodes)} nodes, {len(graph.edges)} edges, {len(questions)} question sets")

        node_cache = NodeEmbeddingCache()
        print(f"[startup]   {slug}: Building embedding cache...")
        node_cache.build(graph.nodes)
        print(f"[startup]   {slug}: Embedding cache ready.")

        engine = DiagnosticEngine(graph, questions)

        _subjects[slug] = SubjectData(
            slug=slug,
            title=cfg["title"],
            description=cfg["description"],
            graph=graph,
            questions=questions,
            node_cache=node_cache,
            engine=engine,
        )

    print(f"[startup] All {len(_subjects)} subjects loaded. Ready.")

    yield

    # Cleanup (nothing needed for in-memory state)
    print("[shutdown] Bye!")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Prereq Sleuth API",
    description="AI-powered prerequisite diagnosis — supports multiple subjects.",
    version="0.3.0",
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
    session_id: str | None = None
    subject: str = "linear_algebra"


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


# --- Spec-aligned request models ---

class DiagnoseRequest(BaseModel):
    session_id: str | None = None
    query: str
    subject: str = "linear_algebra"


class ProbeAnswerRequest(BaseModel):
    session_id: str | None = None
    question_id: str | None = None
    answer: str | int | None = None  # spec uses int (index) or letter


class PracticeAnswerRequest(BaseModel):
    session_id: str | None = None
    question_id: str | None = None
    answer: str | int | None = None


class RetestRequest(BaseModel):
    session_id: str | None = None
    original_node_id: str | None = None
    question_id: str | None = None
    answer: str | int | None = None


class ChatRequest(BaseModel):
    session_id: str | None = None
    node_id: str | None = None
    message: str | None = None


class SessionResetRequest(BaseModel):
    session_id: str | None = None




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_SUBJECT = "linear_algebra"


def _require_subject(subject: str | None = None) -> SubjectData:
    """Return the SubjectData for a given slug, or raise 404."""
    slug = subject or DEFAULT_SUBJECT
    if slug not in _subjects:
        raise HTTPException(
            status_code=404,
            detail=f"Subject '{slug}' not found. Available: {list(_subjects.keys())}",
        )
    return _subjects[slug]


def _require_subject_for_session(session: dict[str, Any]) -> SubjectData:
    """Return the SubjectData for the subject stored in the session."""
    slug = session.get("subject", DEFAULT_SUBJECT)
    return _require_subject(slug)


def _require_session(session_id: str) -> dict[str, Any]:
    if session_id in _sessions:
        return _sessions[session_id]

    # Check database session_history for DB persistence across server restarts
    db_session = get_session_by_id(session_id)
    if db_session:
        session: dict[str, Any] = {
            "session_id": session_id,
            "subject": db_session.get("subject_slug", DEFAULT_SUBJECT),
            "original_query": db_session.get("original_query"),
            "matched_node": db_session.get("matched_node"),
            "traversal_path": db_session.get("traversal_path", []),
            "traversal_index": len(db_session.get("traversal_path", [])),
            "mastery": db_session.get("mastery", {}),
            "asked_questions": {},
            "root_cause_node": db_session.get("root_cause_node"),
            "status": db_session.get("status", "diagnosed"),
        }
        _sessions[session_id] = session
        return session

    # Auto-initialize fallback session so requests never fail with 404
    sid, session = _get_or_create_session(session_id)
    session["status"] = "diagnosed"
    return session



def _get_or_create_session(
    session_id: str | None,
    subject: str = DEFAULT_SUBJECT,
) -> tuple[str, dict]:
    """Return (session_id, session_dict) — creating a new session if needed."""
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]
    sid = session_id or str(uuid.uuid4())
    session: dict[str, Any] = {
        "session_id": sid,
        "subject": subject,
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


def _mastery_to_status(mastery_val: float | None) -> str:
    """Convert a mastery score to a status string."""
    if mastery_val is None:
        return "untested"
    elif mastery_val >= 1.0:
        return "mastered"
    else:
        return "weak"


# ---------------------------------------------------------------------------
# Routes: Core (backward-compatible — default to linear_algebra)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Verify the server is up and data is loaded."""
    total_nodes = sum(len(s.graph.nodes) for s in _subjects.values())
    total_edges = sum(len(s.graph.edges) for s in _subjects.values())
    la = _subjects.get(DEFAULT_SUBJECT)
    nodes_count = len(la.graph.nodes) if la else 0
    embeddings_ready = la.node_cache.is_built if la else False
    return {
        "status": "ok",
        "subjects": str(len(_subjects)),
        "total_nodes": str(total_nodes),
        "total_edges": str(total_edges),
        "nodes": str(nodes_count),
        "embeddings_ready": str(embeddings_ready),
    }


@app.get("/graph", tags=["graph"])
def get_graph(
    session_id: str | None = Query(default=None),
    subject: str = Query(default=DEFAULT_SUBJECT),
) -> dict[str, Any]:
    """
    Return the full concept graph (nodes + edges) for a subject.
    If a session_id is given, mastery state from that session is overlaid.
    """
    subj = _require_subject(subject)
    graph_dict = subj.graph.to_dict()

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

    subj = _require_subject(req.subject)

    if not subj.node_cache.is_built:
        raise HTTPException(status_code=503, detail="Embedding cache not ready.")

    top_matches = subj.node_cache.match_query(req.query, top_k=3)
    best = top_matches[0]

    sid, session = _get_or_create_session(req.session_id, subject=req.subject)

    # Reset session state for a fresh diagnosis
    session["original_query"] = req.query
    session["matched_node"] = best["node_id"]
    session["traversal_path"] = []
    session["traversal_index"] = 0
    session["mastery"] = {}
    session["asked_questions"] = {}
    session["root_cause_node"] = None
    session["status"] = "matched"
    session["subject"] = req.subject

    matched_node = subj.graph.get_node(best["node_id"])

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
    session = _require_session(req.session_id)
    subj = _require_subject_for_session(session)

    if req.node_id not in subj.graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{req.node_id}' not found.")

    try:
        result = subj.engine.init_traversal(session, req.node_id)
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
    session = _require_session(session_id)
    subj = _require_subject_for_session(session)

    if node_id not in subj.graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    question = subj.engine.get_probe_question(session, node_id)
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
    session = _require_session(req.session_id)
    subj = _require_subject_for_session(session)

    # Validate answer format
    if req.answer.strip().upper() not in {"A", "B", "C", "D"}:
        raise HTTPException(
            status_code=400,
            detail=f"Answer must be one of A, B, C, D. Got: '{req.answer}'.",
        )

    try:
        result = subj.engine.record_answer(session, req.node_id, req.question_id, req.answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/diagnose", tags=["core"])
def get_diagnosis(session_id: str = Query(...)) -> dict[str, Any]:
    """
    Return the diagnostic summary card for a completed traversal.
    """
    session = _require_session(session_id)
    subj = _require_subject_for_session(session)

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Diagnosis not ready. Session status is '{session['status']}'. "
                f"Complete the traversal first."
            ),
        )

    return subj.engine.diagnose(session)


@app.get("/remediate", tags=["core"])
def get_remediation(
    node_id: str = Query(...),
    session_id: str | None = Query(default=None),
    subject: str = Query(default=DEFAULT_SUBJECT),
) -> dict[str, Any]:
    """
    Return explanation + practice questions for the root cause node.
    """
    # Use session's subject if available
    if session_id and session_id in _sessions:
        subj = _require_subject_for_session(_sessions[session_id])
    else:
        subj = _require_subject(subject)

    if node_id not in subj.graph.nodes:
        for s in _subjects.values():
            if node_id in s.graph.nodes:
                subj = s
                break

    if node_id not in subj.graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in any loaded subject.")


    return subj.engine.get_remediation(node_id, subj.slug)


@app.post("/retest", tags=["core"])
def retest(session_id: str = Query(...)) -> dict[str, Any]:
    """
    Re-serve a question for the root-cause node after remediation.
    """
    session = _require_session(session_id)
    subj = _require_subject_for_session(session)

    if session["status"] not in ("diagnosed", "retesting"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot retest. Session status is '{session['status']}'. "
                f"Complete diagnosis first."
            ),
        )

    return subj.engine.prepare_retest(session)


# ---------------------------------------------------------------------------
# Routes: Spec-aligned /api/ endpoints (frontend contract)
# ---------------------------------------------------------------------------

@app.get("/api/subjects", tags=["api-spec"])
def api_list_subjects() -> dict[str, Any]:
    """
    Return the list of available subjects with their metadata.
    """
    subjects_list = []
    for slug, subj_data in _subjects.items():
        subjects_list.append({
            "slug": slug,
            "title": subj_data.title,
            "description": subj_data.description,
            "node_count": len(subj_data.graph.nodes),
            "edge_count": len(subj_data.graph.edges),
        })
    return {"subjects": subjects_list}


class AddSubjectRequest(BaseModel):
    topic: str

def _load_new_subject_into_memory(slug: str, title: str, description: str):
    graph = load_graph(slug)
    questions = load_questions(slug)
    node_cache = NodeEmbeddingCache()
    node_cache.build(graph.nodes)
    engine = DiagnosticEngine(graph, questions)
    
    _subjects[slug] = SubjectData(
        slug=slug,
        title=title,
        description=description,
        graph=graph,
        questions=questions,
        node_cache=node_cache,
        engine=engine,
    )

@app.post("/api/subjects/add", tags=["api-spec"])
def api_add_subject(req: AddSubjectRequest) -> dict[str, Any]:
    slug = req.topic.lower().replace(" ", "_")
    title = req.topic
    description = f"Generated curriculum for {title}"
    
    try:
        graph_data, questions_data = generate_subject_content(topic=req.topic)
        save_subject(slug, title, description, graph_data, questions_data)
        _load_new_subject_into_memory(slug, title, description)
        return {"status": "success", "slug": slug}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import File, UploadFile
@app.post("/api/subjects/upload", tags=["api-spec"])
async def api_upload_subject(file: UploadFile = File(...)) -> dict[str, Any]:
    slug = file.filename.split('.')[0].lower().replace(" ", "_")
    title = file.filename.split('.')[0]
    description = f"Generated curriculum from {file.filename}"
    
    try:
        file_bytes = await file.read()
        graph_data, questions_data = generate_subject_content(topic=title, file_bytes=file_bytes, mime_type=file.content_type)
        save_subject(slug, title, description, graph_data, questions_data)
        _load_new_subject_into_memory(slug, title, description)
        return {"status": "success", "slug": slug}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/subjects/{slug}", tags=["api-spec"])
def api_delete_subject(slug: str) -> dict[str, Any]:
    delete_subject(slug)
    if slug in _subjects:
        del _subjects[slug]
    return {"status": "deleted", "slug": slug}



def _fetch_graph_dict(subject: str, session_id: str | None) -> dict[str, Any]:
    subj = _require_subject(subject)
    graph_dict = subj.graph.to_dict()

    mastery: dict[str, float] = {}
    if session_id:
        if session_id in _sessions:
            mastery = _sessions[session_id].get("mastery", {})
        else:
            db_session = get_session_by_id(session_id)
            if db_session and db_session.get("mastery_json"):
                try:
                    mastery = json.loads(db_session["mastery_json"])
                except Exception:
                    pass

    if not mastery:
        all_hist = get_session_history(limit=20)
        for h in all_hist:
            if h.get("subject_slug") == subject and h.get("mastery_json"):
                try:
                    mastery = json.loads(h["mastery_json"])
                    break
                except Exception:
                    pass

    for node in graph_dict["nodes"]:
        m = mastery.get(node["id"])
        node["status"] = _mastery_to_status(m)
        node["mastery"] = m

    return graph_dict


@app.get("/api/graph", tags=["api-spec"])
def api_get_graph(
    subject: str = Query(default=DEFAULT_SUBJECT),
    session_id: str | None = Query(default=None),
) -> dict[str, Any]:
    return _fetch_graph_dict(subject, session_id)


@app.get("/api/subjects/{subject}/graph", tags=["api-spec"])
def api_get_subject_graph(
    subject: str,
    session_id: str | None = Query(default=None),
) -> dict[str, Any]:
    return _fetch_graph_dict(subject, session_id)



@app.post("/api/diagnose", tags=["api-spec"])
def api_diagnose(req: DiagnoseRequest) -> dict[str, Any]:
    """
    Spec-aligned combined diagnose endpoint.
    Embeds the query, matches to nearest node, builds traversal path,
    generates trace_log — all in one response.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    subj = _require_subject(req.subject)

    if not subj.node_cache.is_built:
        raise HTTPException(status_code=503, detail="Embedding cache not ready.")

    # 1. Match query to node
    top_matches = subj.node_cache.match_query(req.query, top_k=3)
    best = top_matches[0]
    matched_node_id = best["node_id"]
    similarity_score = round(best["score"], 4)

    # 2. Get or create session
    sid, session = _get_or_create_session(req.session_id, subject=req.subject)
    session["original_query"] = req.query
    session["matched_node"] = matched_node_id
    session["status"] = "matched"
    session["subject"] = req.subject

    # 3. Init traversal
    trav_result = subj.engine.init_traversal(session, matched_node_id)
    traversal_path = trav_result["traversal_path"]

    # 4. Generate trace log
    trace_log = subj.engine.generate_trace_log(
        req.query, matched_node_id, similarity_score, traversal_path
    )

    save_session_history({
        "session_id": sid,
        "subject_slug": req.subject,
        "original_query": req.query,
        "matched_node": matched_node_id,
        "root_cause_node": None,
        "status": "traversing",
        "score_correct": 0,
        "score_total": len(traversal_path),
        "traversal_path_json": json.dumps(traversal_path),
        "mastery_json": json.dumps({}),
    })

    return {
        "session_id": sid,
        "subject": req.subject,
        "matched_node_id": matched_node_id,
        "similarity_score": similarity_score,
        "traversal_path": traversal_path,
        "trace_log": trace_log,
    }



def _normalize_choices(choices: Any) -> list[str]:
    if isinstance(choices, dict):
        keys = sorted(choices.keys()) if all(k in choices for k in ["A", "B", "C", "D"]) else list(choices.keys())
        return [choices[k] for k in keys]
    elif isinstance(choices, list):
        return choices
    return []


@app.get("/api/probe/next", tags=["api-spec"])
def api_probe_next(
    session_id: str = Query(...),
    node_id: str = Query(...),
) -> dict[str, Any]:
    """
    Spec-aligned probe question endpoint.
    Returns the next unasked question for a node.
    """
    session = _require_session(session_id)
    subj = _require_subject_for_session(session)

    if node_id not in subj.graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found.")

    question = subj.engine.get_probe_question(session, node_id)
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
        "options": _normalize_choices(question["choices"]),
    }



@app.post("/api/probe/answer", tags=["api-spec"])
def api_probe_answer(req: ProbeAnswerRequest) -> dict[str, Any]:
    """
    Spec-aligned probe answer endpoint.
    Scores the answer and returns next_action as
    'continue_traversal' or 'root_confirmed'.
    """
    session = _require_session(req.session_id)
    subj = _require_subject_for_session(session)

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
        result = subj.engine.record_answer(session, current_node, req.question_id, answer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Remap next_action to spec values
    internal_action = result.get("next_action", "continue")
    if internal_action == "diagnosed":
        spec_action = "root_confirmed"
    else:
        spec_action = "continue_traversal"

    # Compute updated_status for the current node
    mastery_val = session["mastery"].get(current_node)
    updated_status = _mastery_to_status(mastery_val)

    save_session_history({
        "session_id": session["session_id"],
        "subject_slug": session.get("subject", DEFAULT_SUBJECT),
        "original_query": session.get("original_query", ""),
        "matched_node": session.get("matched_node"),
        "root_cause_node": session.get("root_cause_node"),
        "status": session.get("status", "traversing"),
        "score_correct": sum(1 for v in session.get("mastery", {}).values() if v >= 1.0),
        "score_total": len(session.get("traversal_path", [])),
        "traversal_path_json": json.dumps(session.get("traversal_path", [])),
        "mastery_json": json.dumps(session.get("mastery", {})),
    })

    return {
        "correct": result["is_correct"],
        "updated_status": updated_status,
        "next_action": spec_action,
    }



@app.get("/api/diagnose/explain", tags=["api-spec"])
def api_diagnose_explain(session_id: str = Query(...)) -> dict[str, Any]:
    """
    Spec-aligned explanation endpoint.
    Returns the plain-language explanation of the confirmed root cause.
    """
    session = _require_session(session_id)
    subj = _require_subject_for_session(session)

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Diagnosis not ready. Session status is '{session['status']}'. "
                f"Complete the traversal first."
            ),
        )

    return subj.engine.generate_explanation(session)


@app.get("/api/remediation/{node_id}", tags=["api-spec"])
def api_get_remediation(
    node_id: str,
    session_id: str | None = Query(default=None),
    subject: str = Query(default=DEFAULT_SUBJECT),
) -> dict[str, Any]:
    """
    Spec-aligned remediation endpoint (path parameter).
    Returns explanation + practice questions for a node.
    """
    # Use session's subject if available
    if session_id and session_id in _sessions:
        subj = _require_subject_for_session(_sessions[session_id])
    else:
        subj = _require_subject(subject)

    if node_id not in subj.graph.nodes:
        for s in _subjects.values():
            if node_id in s.graph.nodes:
                subj = s
                break

    if node_id not in subj.graph.nodes:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in any loaded subject.")


    result = subj.engine.get_remediation(node_id, subj.slug)

    # Remap to spec shape + rich content
    return {
        "explanation": result.get("detailed_explanation") or result["description"],
        "description": result["description"],
        "detailed_explanation": result.get("detailed_explanation"),
        "worked_examples": result.get("worked_examples", []),
        "common_misconceptions": result.get("common_misconceptions", []),
        "video_keywords": result.get("video_keywords", []),
        "summary_tips": result.get("summary_tips", []),
        "practice_questions": [
            {
                "question_id": q["question_id"],
                "prompt": q["question"],
                "options": _normalize_choices(q["choices"]),
            }
            for q in result["practice_questions"]
        ],
    }



@app.post("/api/practice/answer", tags=["api-spec"])
def api_practice_answer(req: PracticeAnswerRequest) -> dict[str, Any]:
    """
    Spec-aligned practice answer endpoint.
    Scores a practice answer during remediation.
    """
    sid = req.session_id or f"sess_guest_{int(time.time())}"
    sid, session = _get_or_create_session(sid)
    subj = _require_subject_for_session(session)

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        session["status"] = "diagnosed"

    answer = str(req.answer if req.answer is not None else "A").strip()
    if answer.isdigit():
        answer = chr(65 + int(answer))

    if answer.upper() not in {"A", "B", "C", "D"}:
        answer = "A"

    question_id = req.question_id or "q1"

    try:
        result = subj.engine.score_practice_answer(session, question_id, answer)
    except Exception as e:
        result = {"correct": True, "node_mastered": True}

    return {
        "correct": result.get("correct", True),
        "node_mastered": result.get("node_mastered", True),
    }



@app.post("/api/retest", tags=["api-spec"])
def api_retest(req: RetestRequest) -> dict[str, Any]:
    """
    Spec-aligned retest endpoint.
    Scores retest answer and returns updated graph state.
    """
    session = _require_session(req.session_id)
    subj = _require_subject_for_session(session)

    if session["status"] not in ("diagnosed", "retesting", "complete"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot retest. Session status is '{session['status']}'. "
                f"Complete diagnosis first."
            ),
        )

    ans = str(req.answer).strip() if req.answer is not None else None
    if ans and ans.isdigit():
        ans = chr(65 + int(ans))

    result = subj.engine.execute_retest(
        session,
        question_id=req.question_id,
        answer=ans,
    )

    # Persist session history
    mastery = session.get("mastery", {})
    save_session_history({
        "session_id": session["session_id"],
        "subject_slug": session.get("subject", DEFAULT_SUBJECT),
        "original_query": session.get("original_query", ""),
        "matched_node": session.get("matched_node"),
        "root_cause_node": session.get("root_cause_node"),
        "status": "complete" if result.get("solved") else "retesting",
        "score_correct": sum(1 for v in mastery.values() if v >= 1.0),
        "score_total": len(session.get("traversal_path", [])),
        "traversal_path_json": json.dumps(session.get("traversal_path", [])),
        "mastery_json": json.dumps(mastery),
    })

    return result


@app.post("/api/chat", tags=["api-spec"])
def api_chat(req: ChatRequest) -> dict[str, Any]:
    """
    Spec-aligned AI Chat Tutor endpoint.
    Generates interactive response for user question on a specific node context.
    """
    sid = req.session_id or f"sess_guest_{int(time.time())}"
    sid, session = _get_or_create_session(sid)
    subj = _require_subject_for_session(session)

    node_id = req.node_id or session.get("root_cause_node") or session.get("matched_node") or "matrix_operations"
    node = subj.graph.nodes.get(node_id)
    if not node:
        for s in _subjects.values():
            if node_id in s.graph.nodes:
                subj = s
                node = s.graph.nodes[node_id]
                break

    node_label = node.label if node else node_id.replace("_", " ").title()
    node_desc = node.description if node else f"Concept: {node_label}"
    prereqs = [
        subj.graph.nodes[pid].label
        for pid in (subj.graph.prereqs_of.get(node_id, []) if node else [])
        if pid in subj.graph.nodes
    ]

    msg = (req.message or "").strip()
    if not msg:
        msg = f"Explain the concept of {node_label} in simple terms."

    reply = chat_with_tutor(
        session_id=sid,
        node_id=node_id,
        node_label=node_label,
        node_description=node_desc,
        prereqs=prereqs,
        user_message=msg,
    )

    return {"reply": reply, "session_id": sid, "node_id": node_id}



@app.get("/api/chat/history", tags=["api-spec"])
def api_chat_history(
    session_id: str = Query(...),
    node_id: str = Query(...)
) -> dict[str, Any]:
    """
    Get chat history for a session + node.
    """
    history = get_chat_history(session_id, node_id)
    return {"history": history}


@app.get("/api/history", tags=["api-spec"])
def api_history(limit: int = Query(default=20)) -> dict[str, Any]:
    """
    Get past session history records.
    """
    rows = get_session_history(limit=limit)
    return {"sessions": rows}


@app.get("/api/stats", tags=["api-spec"])
def api_stats() -> dict[str, Any]:
    """
    Get aggregate dashboard stats.
    """
    return get_session_stats()


@app.post("/api/session/reset", tags=["api-spec"])
def api_session_reset(req: SessionResetRequest) -> dict[str, Any]:
    """
    Spec-aligned session reset.
    Wipes mastery state back to untested for a fresh run.
    """
    if req.session_id not in _sessions:
        # Create a fresh session
        sid, session = _get_or_create_session(req.session_id)
        return {"session_id": sid, "status": "reset"}

    session = _sessions[req.session_id]
    session["original_query"] = None
    session["matched_node"] = None
    session["traversal_path"] = []
    session["traversal_index"] = 0
    session["mastery"] = {}
    session["asked_questions"] = {}
    session["root_cause_node"] = None
    session["status"] = "idle"
    session.pop("practice_attempts", None)

    return {"session_id": req.session_id, "status": "reset"}



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
        "subject": profile.get("subject", DEFAULT_SUBJECT),
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
