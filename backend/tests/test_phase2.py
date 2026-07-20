"""
test_phase2.py — Integration tests for Phase 2: Diagnostic & Remediation Engine.

Run with:
    cd backend
    pytest tests/test_phase2.py -v

Tests:
  1. Traverse endpoint builds correct path
  2. Question endpoint serves valid questions
  3. Answer endpoint grades correctly and advances traversal
  4. Full diagnostic journey: match → traverse → probe → fail prereq → diagnose
  5. All-clear diagnosis when student passes everything
  6. Remediation endpoint returns correct content
  7. Retest endpoint serves questions for root cause
  8. Edge cases: invalid sessions, unknown nodes, empty answers
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


@pytest.fixture
def fresh_session() -> dict:
    """A clean session dict for unit-level diagnostic tests."""
    return {
        "session_id": "test-session-001",
        "original_query": "I don't understand eigenvectors",
        "matched_node": None,
        "traversal_path": [],
        "traversal_index": 0,
        "mastery": {},
        "asked_questions": {},
        "root_cause_node": None,
        "status": "matched",
    }


@pytest.fixture(scope="class")
def api_client():
    """FastAPI TestClient fixture — requires GEMINI_API_KEY."""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set — skipping API integration tests")
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. DiagnosticEngine: init_traversal
# ---------------------------------------------------------------------------

class TestInitTraversal:
    def test_traversal_includes_target_node(self, engine, fresh_session):
        result = engine.init_traversal(fresh_session, "eigenvectors")
        assert result["traversal_path"][0] == "eigenvectors"
        assert result["status"] == "traversing"

    def test_traversal_includes_prerequisites(self, engine, fresh_session):
        result = engine.init_traversal(fresh_session, "eigenvectors")
        path = result["traversal_path"]
        # eigenvectors has prerequisites, path should be > 1
        assert len(path) > 1
        # Known prereqs should appear in path
        assert "eigenvalues_intro" in path or "linear_independence" in path

    def test_traversal_sets_session_state(self, engine, fresh_session):
        engine.init_traversal(fresh_session, "eigenvectors")
        assert fresh_session["status"] == "traversing"
        assert fresh_session["matched_node"] == "eigenvectors"
        assert fresh_session["traversal_index"] == 0

    def test_traversal_unknown_node_raises(self, engine, fresh_session):
        with pytest.raises(ValueError, match="Unknown node"):
            engine.init_traversal(fresh_session, "nonexistent_node")

    def test_root_node_traversal(self, engine, fresh_session):
        """A root node (no prereqs) should have a path of just itself."""
        result = engine.init_traversal(fresh_session, "vectors_intro")
        assert result["traversal_path"] == ["vectors_intro"]
        assert result["total_steps"] == 1


# ---------------------------------------------------------------------------
# 2. DiagnosticEngine: get_probe_question
# ---------------------------------------------------------------------------

class TestGetProbeQuestion:
    def test_returns_valid_question(self, engine, fresh_session):
        engine.init_traversal(fresh_session, "eigenvectors")
        q = engine.get_probe_question(fresh_session, "eigenvectors")
        assert q is not None
        assert "question_id" in q
        assert "question" in q
        assert "choices" in q
        assert set(q["choices"].keys()) == {"A", "B", "C", "D"}

    def test_no_duplicate_questions(self, engine, fresh_session):
        engine.init_traversal(fresh_session, "eigenvectors")
        seen = set()
        for _ in range(10):
            q = engine.get_probe_question(fresh_session, "eigenvectors")
            if q is None:
                break
            assert q["question_id"] not in seen, f"Duplicate question: {q['question_id']}"
            seen.add(q["question_id"])

    def test_returns_none_when_exhausted(self, engine, fresh_session):
        engine.init_traversal(fresh_session, "eigenvectors")
        # Exhaust all questions
        for _ in range(20):
            q = engine.get_probe_question(fresh_session, "eigenvectors")
            if q is None:
                break
        # After exhaustion, should return None
        assert engine.get_probe_question(fresh_session, "eigenvectors") is None


# ---------------------------------------------------------------------------
# 3. DiagnosticEngine: record_answer
# ---------------------------------------------------------------------------

class TestRecordAnswer:
    def test_correct_answer_updates_mastery(self, engine, fresh_session, questions):
        engine.init_traversal(fresh_session, "eigenvectors")
        q = engine.get_probe_question(fresh_session, "eigenvectors")
        # Find the correct answer
        full_q = next(
            fq for fq in questions["eigenvectors"] if fq["id"] == q["question_id"]
        )
        result = engine.record_answer(
            fresh_session, "eigenvectors", q["question_id"], full_q["correct_answer"]
        )
        assert result["is_correct"] is True
        assert fresh_session["mastery"]["eigenvectors"] == 1.0

    def test_incorrect_answer_on_target_continues(self, engine, fresh_session, questions):
        """Failing the target node should continue probing prerequisites."""
        engine.init_traversal(fresh_session, "eigenvectors")
        q = engine.get_probe_question(fresh_session, "eigenvectors")
        full_q = next(
            fq for fq in questions["eigenvectors"] if fq["id"] == q["question_id"]
        )
        # Give wrong answer
        wrong = [c for c in "ABCD" if c != full_q["correct_answer"]][0]
        result = engine.record_answer(
            fresh_session, "eigenvectors", q["question_id"], wrong
        )
        assert result["is_correct"] is False
        # Should continue to prerequisites
        assert result["next_action"] == "continue"
        assert fresh_session["mastery"]["eigenvectors"] == 0.0

    def test_incorrect_answer_on_prereq_diagnoses(self, engine, fresh_session, questions):
        """Failing a prerequisite node should trigger diagnosis."""
        engine.init_traversal(fresh_session, "eigenvectors")
        path = fresh_session["traversal_path"]

        # Pass the target node first
        q = engine.get_probe_question(fresh_session, path[0])
        full_q = next(fq for fq in questions[path[0]] if fq["id"] == q["question_id"])
        engine.record_answer(
            fresh_session, path[0], q["question_id"], full_q["correct_answer"]
        )

        # Now fail the first prerequisite
        prereq = path[1]
        q2 = engine.get_probe_question(fresh_session, prereq)
        full_q2 = next(fq for fq in questions[prereq] if fq["id"] == q2["question_id"])
        wrong = [c for c in "ABCD" if c != full_q2["correct_answer"]][0]
        result = engine.record_answer(
            fresh_session, prereq, q2["question_id"], wrong
        )
        assert result["is_correct"] is False
        assert result["next_action"] == "diagnosed"
        assert result["root_cause"] == prereq
        assert fresh_session["status"] == "diagnosed"


# ---------------------------------------------------------------------------
# 4. Full diagnostic journey (unit-level)
# ---------------------------------------------------------------------------

class TestFullDiagnosticJourney:
    def test_match_traverse_fail_prereq_diagnose(self, engine, questions):
        """Simulate: match eigenvectors → fail target → fail prereq → diagnose."""
        session = {
            "session_id": "journey-test",
            "original_query": "I don't understand eigenvectors",
            "matched_node": None,
            "traversal_path": [],
            "traversal_index": 0,
            "mastery": {},
            "asked_questions": {},
            "root_cause_node": None,
            "status": "matched",
        }

        # Step 1: Traverse
        traverse_result = engine.init_traversal(session, "eigenvectors")
        path = traverse_result["traversal_path"]
        assert path[0] == "eigenvectors"
        assert len(path) > 2  # Should have multiple prereqs

        # Step 2: Fail the target node
        q = engine.get_probe_question(session, "eigenvectors")
        full_q = next(fq for fq in questions["eigenvectors"] if fq["id"] == q["question_id"])
        wrong = [c for c in "ABCD" if c != full_q["correct_answer"]][0]
        result1 = engine.record_answer(session, "eigenvectors", q["question_id"], wrong)
        assert result1["next_action"] == "continue"

        # Step 3: Pass the first prereq
        prereq1 = path[1]
        q2 = engine.get_probe_question(session, prereq1)
        full_q2 = next(fq for fq in questions[prereq1] if fq["id"] == q2["question_id"])
        result2 = engine.record_answer(
            session, prereq1, q2["question_id"], full_q2["correct_answer"]
        )
        assert result2["is_correct"] is True

        # Step 4: Fail the second prereq
        prereq2 = path[2]
        q3 = engine.get_probe_question(session, prereq2)
        full_q3 = next(fq for fq in questions[prereq2] if fq["id"] == q3["question_id"])
        wrong3 = [c for c in "ABCD" if c != full_q3["correct_answer"]][0]
        result3 = engine.record_answer(session, prereq2, q3["question_id"], wrong3)
        assert result3["next_action"] == "diagnosed"
        assert result3["root_cause"] == prereq2

        # Step 5: Diagnose
        diagnosis = engine.diagnose(session)
        assert diagnosis["root_cause_node"] == prereq2
        assert diagnosis["stats"]["failed"] >= 1
        assert diagnosis["gap_depth"] > 0
        assert len(diagnosis["summary"]) > 0

    def test_all_clear_diagnosis(self, engine, questions):
        """If student passes everything, diagnosis should be 'all clear'."""
        session = {
            "session_id": "all-clear-test",
            "original_query": "vectors intro",
            "matched_node": None,
            "traversal_path": [],
            "traversal_index": 0,
            "mastery": {},
            "asked_questions": {},
            "root_cause_node": None,
            "status": "matched",
        }

        # vectors_intro has no prerequisites (root node)
        engine.init_traversal(session, "vectors_intro")
        path = session["traversal_path"]
        assert path == ["vectors_intro"]

        # Pass the only question
        q = engine.get_probe_question(session, "vectors_intro")
        full_q = next(
            fq for fq in questions["vectors_intro"] if fq["id"] == q["question_id"]
        )
        result = engine.record_answer(
            session, "vectors_intro", q["question_id"], full_q["correct_answer"]
        )
        assert result["is_correct"] is True
        assert result["next_action"] == "diagnosed"
        assert result["diagnosis"] == "all_clear"

        # Diagnose
        diagnosis = engine.diagnose(session)
        assert diagnosis["root_cause_node"] is None
        assert diagnosis["gap_depth"] == 0
        assert "Great news" in diagnosis["summary"]


# ---------------------------------------------------------------------------
# 5. Remediation
# ---------------------------------------------------------------------------

class TestRemediation:
    def test_remediation_returns_content(self, engine):
        result = engine.get_remediation("matrix_rank")
        assert result["node_id"] == "matrix_rank"
        assert result["label"] == "Matrix Rank"
        assert len(result["description"]) > 0
        assert len(result["practice_questions"]) >= 3

    def test_remediation_includes_prereqs(self, engine):
        result = engine.get_remediation("eigenvectors")
        assert len(result["prerequisites"]) > 0

    def test_remediation_unknown_node_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown node"):
            engine.get_remediation("nonexistent_node")


# ---------------------------------------------------------------------------
# 6. Retest
# ---------------------------------------------------------------------------

class TestRetest:
    def test_retest_serves_question(self, engine, questions):
        session = {
            "session_id": "retest-test",
            "original_query": "matrix rank",
            "matched_node": "matrix_rank",
            "traversal_path": ["matrix_rank"],
            "traversal_index": 0,
            "mastery": {"matrix_rank": 0.0},
            "asked_questions": {},
            "root_cause_node": "matrix_rank",
            "status": "diagnosed",
        }
        result = engine.prepare_retest(session)
        assert result["status"] == "retesting"
        assert result["root_cause_node"] == "matrix_rank"
        assert result["question"] is not None

    def test_retest_no_root_cause(self, engine):
        session = {
            "session_id": "no-root-test",
            "root_cause_node": None,
            "status": "diagnosed",
        }
        result = engine.prepare_retest(session)
        assert result["status"] == "no_root_cause"


# ---------------------------------------------------------------------------
# 7. API Integration Tests
# ---------------------------------------------------------------------------

class TestAPIPhase2:
    @pytest.fixture(scope="class")
    def client(self):
        """Test client fixture — skipped if API key not set."""
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set — skipping API integration tests")
        from fastapi.testclient import TestClient
        from main import app
        with TestClient(app) as c:
            yield c

    def test_full_api_flow(self, client):
        """End-to-end: match → traverse → question → answer → diagnose."""
        # 1. Match
        resp = client.post("/match", json={"query": "I don't get eigenvectors"})
        assert resp.status_code == 200
        match_data = resp.json()
        sid = match_data["session_id"]
        matched = match_data["matched_node_id"]

        # 2. Traverse
        resp = client.post("/traverse", json={"session_id": sid, "node_id": matched})
        assert resp.status_code == 200
        traverse_data = resp.json()
        assert traverse_data["status"] == "traversing"
        path = traverse_data["traversal_path"]
        assert len(path) >= 1

        # 3. Get question for first node
        first_node = path[0]
        resp = client.get(f"/question?node_id={first_node}&session_id={sid}")
        assert resp.status_code == 200
        q_data = resp.json()
        assert "question_id" in q_data
        assert "choices" in q_data

        # 4. Answer incorrectly (use a definitely-wrong answer)
        resp = client.post("/answer", json={
            "session_id": sid,
            "node_id": first_node,
            "question_id": q_data["question_id"],
            "answer": "Z",  # Invalid
        })
        # Should reject invalid answer
        assert resp.status_code == 400

        # 4b. Answer with a valid letter (pick one that might be wrong)
        resp = client.post("/answer", json={
            "session_id": sid,
            "node_id": first_node,
            "question_id": q_data["question_id"],
            "answer": "D",  # May or may not be correct
        })
        assert resp.status_code == 200
        answer_data = resp.json()
        assert "is_correct" in answer_data

    def test_traverse_invalid_session(self, client):
        resp = client.post(
            "/traverse",
            json={"session_id": "nonexistent", "node_id": "eigenvectors"},
        )
        assert resp.status_code == 404

    def test_traverse_invalid_node(self, client):
        # Create a session first
        resp = client.post("/match", json={"query": "test"})
        sid = resp.json()["session_id"]
        resp = client.post(
            "/traverse",
            json={"session_id": sid, "node_id": "fake_node"},
        )
        assert resp.status_code == 404

    def test_question_invalid_node(self, client):
        resp = client.get("/question?node_id=fake_node&session_id=fake_session")
        assert resp.status_code == 404

    def test_diagnose_before_ready(self, client):
        resp = client.post("/match", json={"query": "test query"})
        sid = resp.json()["session_id"]
        resp = client.get(f"/diagnose?session_id={sid}")
        assert resp.status_code == 400  # Not diagnosed yet

    def test_remediate_valid_node(self, client):
        resp = client.get("/remediate?node_id=matrix_rank")
        assert resp.status_code == 200
        data = resp.json()
        assert data["node_id"] == "matrix_rank"
        assert len(data["practice_questions"]) >= 3

    def test_remediate_invalid_node(self, client):
        resp = client.get("/remediate?node_id=nonexistent")
        assert resp.status_code == 404

    def test_retest_before_diagnosis(self, client):
        resp = client.post("/match", json={"query": "test"})
        sid = resp.json()["session_id"]
        resp = client.post(f"/retest?session_id={sid}")
        assert resp.status_code == 400
