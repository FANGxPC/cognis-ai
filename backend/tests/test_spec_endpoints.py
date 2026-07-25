"""
test_spec_endpoints.py — Tests for spec-aligned /api/ endpoints.

Run with:
    cd backend
    pytest tests/test_spec_endpoints.py -v

Tests:
  1. GET /api/graph returns nodes with status field
  2. POST /api/diagnose returns combined match+traverse+trace_log
  3. GET /api/probe/next returns spec-shaped question
  4. POST /api/probe/answer returns root_confirmed/continue_traversal
  5. GET /api/diagnose/explain returns explanation
  6. GET /api/remediation/{node_id} returns content
  7. POST /api/practice/answer scores and tracks mastery
  8. POST /api/retest returns solved + updated_graph_state
  9. POST /api/session/reset wipes session
 10. Full end-to-end flow through /api/ endpoints
 11. Demo profile endpoints
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Allow imports from backend root
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph import load_graph, load_questions, ConceptGraph
from diagnostic import DiagnosticEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def graph() -> ConceptGraph:
    return load_graph()


@pytest.fixture(scope="session")
def questions() -> dict:
    return load_questions()


@pytest.fixture(scope="session")
def engine(graph, questions) -> DiagnosticEngine:
    return DiagnosticEngine(graph, questions)


# ---------------------------------------------------------------------------
# 1. DiagnosticEngine: generate_trace_log
# ---------------------------------------------------------------------------

class TestTraceLog:
    def test_trace_log_contains_query(self, engine):
        log = engine.generate_trace_log(
            query="I don't get eigenvectors",
            matched_node_id="eigenvectors",
            similarity_score=0.91,
            traversal_path=["eigenvectors", "eigenvalues_intro", "matrix_rank"],
        )
        assert isinstance(log, list)
        assert len(log) > 5
        # Should mention the query
        assert any("eigenvectors" in line.lower() for line in log)
        # Should mention similarity
        assert any("0.91" in line for line in log)
        # Should mention traversal steps
        assert any("step" in line.lower() for line in log)

    def test_trace_log_single_node(self, engine):
        log = engine.generate_trace_log(
            query="vectors",
            matched_node_id="vectors_intro",
            similarity_score=0.85,
            traversal_path=["vectors_intro"],
        )
        assert isinstance(log, list)
        assert len(log) >= 5


# ---------------------------------------------------------------------------
# 2. DiagnosticEngine: generate_explanation
# ---------------------------------------------------------------------------

class TestExplanation:
    def test_explanation_with_root_cause(self, engine, questions):
        session = {
            "session_id": "explain-test",
            "original_query": "I don't understand eigenvectors",
            "matched_node": "eigenvectors",
            "traversal_path": ["eigenvectors", "eigenvalues_intro", "matrix_rank"],
            "traversal_index": 2,
            "mastery": {"eigenvectors": 0.0, "eigenvalues_intro": 1.0, "matrix_rank": 0.0},
            "asked_questions": {},
            "root_cause_node": "matrix_rank",
            "status": "diagnosed",
        }
        result = engine.generate_explanation(session)
        assert result["root_node_id"] == "matrix_rank"
        assert result["root_node_label"] == "Matrix Rank"
        assert len(result["explanation"]) > 20
        assert "Eigenvectors" in result["explanation"]
        assert "Matrix Rank" in result["explanation"]

    def test_explanation_no_root_cause(self, engine):
        session = {
            "session_id": "explain-clear",
            "original_query": "vectors",
            "matched_node": "vectors_intro",
            "traversal_path": ["vectors_intro"],
            "mastery": {"vectors_intro": 1.0},
            "root_cause_node": None,
            "status": "diagnosed",
        }
        result = engine.generate_explanation(session)
        assert result["root_node_id"] is None
        assert "Great job" in result["explanation"]


# ---------------------------------------------------------------------------
# 3. DiagnosticEngine: score_practice_answer
# ---------------------------------------------------------------------------

class TestPracticeAnswer:
    def test_correct_practice_answer(self, engine, questions):
        session = {
            "session_id": "practice-test",
            "root_cause_node": "matrix_rank",
            "mastery": {"matrix_rank": 0.0},
            "status": "diagnosed",
        }
        # Get a question for matrix_rank
        q = questions["matrix_rank"][0]
        result = engine.score_practice_answer(
            session, q["id"], q["correct_answer"]
        )
        assert result["correct"] is True
        assert result["node_mastered"] is True
        assert session["mastery"]["matrix_rank"] == 1.0

    def test_incorrect_practice_answer(self, engine, questions):
        session = {
            "session_id": "practice-wrong",
            "root_cause_node": "matrix_rank",
            "mastery": {"matrix_rank": 0.0},
            "status": "diagnosed",
        }
        q = questions["matrix_rank"][0]
        wrong = [c for c in "ABCD" if c != q["correct_answer"]][0]
        result = engine.score_practice_answer(session, q["id"], wrong)
        assert result["correct"] is False
        assert result["node_mastered"] is False

    def test_practice_no_root_cause_raises(self, engine):
        session = {"root_cause_node": None}
        with pytest.raises(ValueError, match="No root cause"):
            engine.score_practice_answer(session, "q_fake", "A")


# ---------------------------------------------------------------------------
# 4. DiagnosticEngine: execute_retest
# ---------------------------------------------------------------------------

class TestExecuteRetest:
    def test_retest_marks_path_mastered(self, engine):
        session = {
            "session_id": "retest-exec",
            "matched_node": "eigenvectors",
            "traversal_path": ["eigenvectors", "eigenvalues_intro", "matrix_rank"],
            "mastery": {"eigenvectors": 0.0, "eigenvalues_intro": 1.0, "matrix_rank": 0.0},
            "root_cause_node": "matrix_rank",
            "status": "diagnosed",
        }
        result = engine.execute_retest(session)
        assert result["solved"] is True
        assert len(result["updated_graph_state"]) >= 3
        # All nodes should be mastered
        for entry in result["updated_graph_state"]:
            assert entry["status"] == "mastered"
        assert session["status"] == "complete"

    def test_retest_no_root_cause(self, engine):
        session = {
            "session_id": "retest-clear",
            "matched_node": None,
            "traversal_path": [],
            "mastery": {},
            "root_cause_node": None,
            "status": "diagnosed",
        }
        result = engine.execute_retest(session)
        assert result["solved"] is True
        assert result["updated_graph_state"] == []


# ---------------------------------------------------------------------------
# 5. API Integration Tests — Spec-aligned endpoints
# ---------------------------------------------------------------------------

class TestSpecAPI:
    @pytest.fixture(scope="class")
    def client(self):
        """Test client fixture — skipped if API key not set."""
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set — skipping API integration tests")
        from fastapi.testclient import TestClient
        from main import app
        with TestClient(app) as c:
            yield c

    # --- GET /api/graph ---

    def test_api_graph_returns_status_field(self, client):
        resp = client.get("/api/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        for node in data["nodes"]:
            assert "status" in node
            assert node["status"] in ("untested", "weak", "mastered")

    def test_api_graph_accepts_subject_param(self, client):
        resp = client.get("/api/graph?subject=linear_algebra")
        assert resp.status_code == 200

    # --- POST /api/diagnose ---

    def test_api_diagnose_combined(self, client):
        resp = client.post("/api/diagnose", json={
            "query": "I don't get eigenvectors"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "matched_node_id" in data
        assert "similarity_score" in data
        assert "traversal_path" in data
        assert "trace_log" in data
        assert isinstance(data["traversal_path"], list)
        assert isinstance(data["trace_log"], list)
        assert len(data["trace_log"]) > 3
        assert data["similarity_score"] > 0.5

    def test_api_diagnose_empty_query(self, client):
        resp = client.post("/api/diagnose", json={"query": "   "})
        assert resp.status_code == 400

    # --- GET /api/probe/next ---

    def test_api_probe_next(self, client):
        # First create a session via diagnose
        resp = client.post("/api/diagnose", json={
            "query": "I don't get eigenvectors"
        })
        data = resp.json()
        sid = data["session_id"]
        first_node = data["traversal_path"][0]

        # Get probe question
        resp = client.get(f"/api/probe/next?session_id={sid}&node_id={first_node}")
        assert resp.status_code == 200
        q_data = resp.json()
        assert "question_id" in q_data
        assert "prompt" in q_data
        assert "type" in q_data
        assert q_data["type"] == "mcq"
        assert "options" in q_data

    # --- POST /api/probe/answer ---

    def test_api_probe_answer_correct_format(self, client):
        # Setup: diagnose + get question
        resp = client.post("/api/diagnose", json={
            "query": "I don't understand eigenvectors"
        })
        data = resp.json()
        sid = data["session_id"]
        first_node = data["traversal_path"][0]

        resp = client.get(f"/api/probe/next?session_id={sid}&node_id={first_node}")
        q_data = resp.json()

        # Answer with a letter
        resp = client.post("/api/probe/answer", json={
            "session_id": sid,
            "question_id": q_data["question_id"],
            "answer": "A",
        })
        assert resp.status_code == 200
        ans_data = resp.json()
        assert "correct" in ans_data
        assert "updated_status" in ans_data
        assert "next_action" in ans_data
        assert ans_data["next_action"] in ("continue_traversal", "root_confirmed")
        assert ans_data["updated_status"] in ("weak", "mastered")

    def test_api_probe_answer_accepts_int(self, client):
        """Spec allows answering with index (0, 1, 2, 3)."""
        resp = client.post("/api/diagnose", json={"query": "matrix rank"})
        data = resp.json()
        sid = data["session_id"]
        node = data["traversal_path"][0]

        resp = client.get(f"/api/probe/next?session_id={sid}&node_id={node}")
        q_data = resp.json()

        resp = client.post("/api/probe/answer", json={
            "session_id": sid,
            "question_id": q_data["question_id"],
            "answer": 1,  # integer index
        })
        assert resp.status_code == 200

    # --- GET /api/diagnose/explain ---

    def test_api_diagnose_explain_requires_diagnosis(self, client):
        resp = client.post("/api/diagnose", json={"query": "null space"})
        sid = resp.json()["session_id"]
        # Not diagnosed yet — should fail
        resp = client.get(f"/api/diagnose/explain?session_id={sid}")
        assert resp.status_code == 400

    # --- GET /api/remediation/{node_id} ---

    def test_api_remediation_path_param(self, client):
        resp = client.get("/api/remediation/matrix_rank")
        assert resp.status_code == 200
        data = resp.json()
        assert "explanation" in data
        assert "practice_questions" in data
        assert len(data["practice_questions"]) >= 3
        # Check spec field names
        for q in data["practice_questions"]:
            assert "question_id" in q
            assert "prompt" in q
            assert "options" in q

    def test_api_remediation_unknown_node(self, client):
        resp = client.get("/api/remediation/nonexistent_node")
        assert resp.status_code == 404

    # --- POST /api/practice/answer ---

    def test_api_practice_answer_requires_diagnosis(self, client):
        resp = client.post("/api/diagnose", json={"query": "test"})
        sid = resp.json()["session_id"]
        resp = client.post("/api/practice/answer", json={
            "session_id": sid,
            "question_id": "q_fake",
            "answer": "A",
        })
        # Session not diagnosed yet (it's "traversing")
        assert resp.status_code == 400

    # --- POST /api/retest ---

    def test_api_retest_requires_diagnosis(self, client):
        resp = client.post("/api/diagnose", json={"query": "test"})
        sid = resp.json()["session_id"]
        resp = client.post("/api/retest", json={
            "session_id": sid,
        })
        assert resp.status_code == 400

    # --- POST /api/session/reset ---

    def test_api_session_reset_existing(self, client):
        resp = client.post("/api/diagnose", json={"query": "eigenvectors"})
        sid = resp.json()["session_id"]

        resp = client.post("/api/session/reset", json={"session_id": sid})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reset"
        assert data["session_id"] == sid

    def test_api_session_reset_new(self, client):
        resp = client.post("/api/session/reset", json={"session_id": "brand-new"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reset"

    # --- Demo profiles ---

    def test_api_demo_profiles(self, client):
        resp = client.get("/api/demo/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert "profiles" in data
        assert len(data["profiles"]) >= 1

    def test_api_demo_load(self, client):
        resp = client.post("/api/demo/load?profile_name=eigenvectors_deep_dive")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["profile_name"] == "eigenvectors_deep_dive"
        assert data["status"] == "diagnosed"

    def test_api_demo_load_unknown(self, client):
        resp = client.post("/api/demo/load?profile_name=nonexistent")
        assert resp.status_code == 404

    # --- Full end-to-end flow ---

    def test_full_spec_flow(self, client):
        """
        Complete end-to-end flow through spec-aligned endpoints:
        diagnose → probe/next → probe/answer (fail target) →
        probe/next → probe/answer (fail prereq = root_confirmed) →
        diagnose/explain → remediation → practice/answer →
        retest → session/reset
        """
        # 1. Diagnose
        resp = client.post("/api/diagnose", json={
            "query": "I'm stuck on eigenvectors"
        })
        assert resp.status_code == 200
        diag = resp.json()
        sid = diag["session_id"]
        path = diag["traversal_path"]
        assert len(path) >= 2

        # 2. Probe the target node
        target = path[0]
        resp = client.get(f"/api/probe/next?session_id={sid}&node_id={target}")
        assert resp.status_code == 200
        q1 = resp.json()

        # 3. Answer wrong 1st time
        resp = client.post("/api/probe/answer", json={
            "session_id": sid,
            "question_id": q1["question_id"],
            "answer": "D",
        })
        a1 = resp.json()
        
        
        # Answer wrong 2nd time (target fails — expected, continues to prereqs)
        resp = client.get(f"/api/probe/next?session_id={sid}&node_id={target}")
        q1_2 = resp.json()
        resp = client.post("/api/probe/answer", json={
            "session_id": sid,
            "question_id": q1_2["question_id"],
            "answer": "D",
        })
        a1_2 = resp.json()
        assert a1_2["next_action"] in ("continue_traversal", "root_confirmed")

        # If we need to continue, probe the next node and fail it
        if a1_2["next_action"] == "continue_traversal":
            next_node = path[1]
            resp = client.get(f"/api/probe/next?session_id={sid}&node_id={next_node}")
            if resp.status_code == 200:
                q2 = resp.json()
                resp = client.post("/api/probe/answer", json={
                    "session_id": sid,
                    "question_id": q2["question_id"],
                    "answer": "D",
                })
                assert resp.status_code == 200

        # At this point, check if we can get a diagnosis
        resp = client.get(f"/api/diagnose/explain?session_id={sid}")
        if resp.status_code == 200:
            explain = resp.json()
            assert "explanation" in explain

            # Get remediation for the root cause
            root = explain.get("root_node_id")
            if root:
                resp = client.get(f"/api/remediation/{root}")
                assert resp.status_code == 200
                remed = resp.json()
                assert len(remed["practice_questions"]) >= 1

                # Practice answer
                pq = remed["practice_questions"][0]
                resp = client.post("/api/practice/answer", json={
                    "session_id": sid,
                    "question_id": pq["question_id"],
                    "answer": "A",
                })
                assert resp.status_code == 200
                pa = resp.json()
                assert "correct" in pa
                assert "node_mastered" in pa

                # Retest
                resp = client.post("/api/retest", json={
                    "session_id": sid,
                })
                assert resp.status_code == 200
                rt = resp.json()
                assert rt["solved"] is True
                assert "updated_graph_state" in rt

        # Session reset
        resp = client.post("/api/session/reset", json={"session_id": sid})
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"

        # After reset, graph should show all untested
        resp = client.get(f"/api/graph?session_id={sid}")
        assert resp.status_code == 200
        for node in resp.json()["nodes"]:
            assert node["status"] == "untested"
