"""
test_new_features.py — Tests for AI Chat Tutor, Session History & Dashboard, and Graph Mastery.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
import pytest
from main import app, _sessions
from chat import chat_with_tutor, get_chat_history
from database import get_session_stats, get_session_history


def test_chat_tutor_fallback():
    reply = chat_with_tutor(
        session_id="test_chat_session",
        node_id="vectors_intro",
        node_label="Vectors: Introduction",
        node_description="Foundational vector operations",
        prereqs=["scalar_multiplication"],
        user_message="What is a vector?",
    )
    assert reply is not None
    assert len(reply) > 0

    history = get_chat_history("test_chat_session", "vectors_intro")
    assert len(history) >= 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What is a vector?"


def test_api_chat_endpoint():
    with TestClient(app) as client:
        # Setup session
        _sessions["sess_chat_1"] = {
            "session_id": "sess_chat_1",
            "subject": "linear_algebra",
            "matched_node": "vectors_intro",
            "traversal_path": ["vectors_intro"],
            "mastery": {},
            "status": "traversing",
        }

        res = client.post("/api/chat", json={
            "session_id": "sess_chat_1",
            "node_id": "vectors_intro",
            "message": "Can you explain vectors simply?"
        })
        assert res.status_code == 200
        data = res.json()
        assert "reply" in data
        assert data["node_id"] == "vectors_intro"

        hist_res = client.get("/api/chat/history?session_id=sess_chat_1&node_id=vectors_intro")
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert "history" in hist_data
        assert len(hist_data["history"]) >= 2


def test_api_history_and_stats():
    with TestClient(app) as client:
        # Trigger a diagnose to create a session record
        diag_res = client.post("/api/diagnose", json={
            "query": "I struggle with vector spaces",
            "subject": "linear_algebra"
        })
        assert diag_res.status_code == 200

        hist_res = client.get("/api/history")
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert "sessions" in hist_data
        assert len(hist_data["sessions"]) > 0

        stats_res = client.get("/api/stats")
        assert stats_res.status_code == 200
        stats_data = stats_res.json()
        assert "total_sessions" in stats_data
        assert stats_data["total_sessions"] > 0
        assert "mastery_rate" in stats_data


def test_graph_mastery_overlay():
    with TestClient(app) as client:
        sid = "sess_graph_1"
        _sessions[sid] = {
            "session_id": sid,
            "subject": "linear_algebra",
            "matched_node": "vectors_intro",
            "traversal_path": ["vectors_intro"],
            "mastery": {"vectors_intro": 1.0},
            "status": "complete",
        }

        res = client.get(f"/api/graph?subject=linear_algebra&session_id={sid}")
        assert res.status_code == 200
        data = res.json()
        assert "nodes" in data
        node = next(n for n in data["nodes"] if n["id"] == "vectors_intro")
        assert node["status"] == "mastered"
        assert node["mastery"] == 1.0


