"""
verify_3_features.py — Comprehensive Verification Script for Prereq Sleuth's 3 New Features

Verifies:
1. AI Chat Tutor: /api/chat and /api/chat/history endpoints + chat.py module logic
2. Session History & Dashboard: database table, auto-saving, /api/history, /api/stats endpoints + dashboard.html
3. Interactive Knowledge Graph: /api/graph with session_id overlay + subject_graph.html
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app, _sessions
from chat import chat_with_tutor, get_chat_history
from database import get_session_stats, get_session_history, save_session_history, init_db


def run_verification():
    print("=" * 70)
    print(" 🔍 VERIFYING TOP 3 FEATURES FOR PREREQ SLEUTH")
    print("=" * 70)

    errors = []

    # ------------------------------------------------------------------
    # 1. VERIFY BACKEND FILES & MODULES EXIST
    # ------------------------------------------------------------------
    print("\n[1/4] Checking File Structure...")

    backend_files = [
        backend_dir / "chat.py",
        backend_dir / "main.py",
        backend_dir / "database.py",
        backend_dir / "remediation.py",
    ]
    frontend_files = [
        backend_dir.parent / "frontend" / "pages" / "dashboard.html",
        backend_dir.parent / "frontend" / "pages" / "lesson.html",
        backend_dir.parent / "frontend" / "pages" / "subject_graph.html",
        backend_dir.parent / "frontend" / "js" / "api.js",
    ]

    for f in backend_files + frontend_files:
        if f.exists():
            print(f"  ✓ Found file: {f.name}")
        else:
            print(f"  ❌ Missing file: {f}")
            errors.append(f"Missing file {f}")

    # ------------------------------------------------------------------
    # 2. VERIFY FEATURE 1: AI CHAT TUTOR
    # ------------------------------------------------------------------
    print("\n[2/4] Verifying Feature 1: AI Chat Tutor...")

    try:
        reply = chat_with_tutor(
            session_id="verif_chat_sess",
            node_id="vectors_intro",
            node_label="Vectors: Introduction",
            node_description="Foundational vector concepts",
            prereqs=[],
            user_message="What is a vector in linear algebra?",
        )
        if reply and len(reply) > 10:
            print(f"  ✓ Chat function returned response ({len(reply)} chars)")
            print(f"    Sample: \"{reply[:80]}...\"")
        else:
            errors.append("Chat tutor response empty or invalid")

        history = get_chat_history("verif_chat_sess", "vectors_intro")
        if len(history) >= 2:
            print(f"  ✓ Chat history correctly saved ({len(history)} messages)")
        else:
            errors.append("Chat history failed to persist in memory")

    except Exception as e:
        print(f"  ❌ Chat tutor error: {e}")
        errors.append(f"Chat tutor exception: {e}")

    # ------------------------------------------------------------------
    # 3. VERIFY FEATURE 2: SESSION HISTORY & DASHBOARD
    # ------------------------------------------------------------------
    print("\n[3/4] Verifying Feature 2: Session History & Dashboard...")

    try:
        init_db()
        save_session_history({
            "session_id": "verif_sess_100",
            "subject_slug": "linear_algebra",
            "original_query": "I am confused by eigenvalues",
            "matched_node": "eigenvalues_eigenvectors",
            "root_cause_node": "determinants",
            "status": "complete",
            "score_correct": 4,
            "score_total": 5,
            "traversal_path_json": "[\"eigenvalues_eigenvectors\", \"determinants\"]",
            "mastery_json": "{\"determinants\": 1.0}",
        })

        hist = get_session_history(limit=5)
        if hist and any(h["session_id"] == "verif_sess_100" for h in hist):
            print(f"  ✓ DB save & retrieve session history successful ({len(hist)} records retrieved)")
        else:
            errors.append("Session history DB retrieval failed")

        stats = get_session_stats()
        if stats and "total_sessions" in stats and "mastery_rate" in stats:
            print(f"  ✓ Dashboard aggregate stats computed: Total={stats['total_sessions']}, MasteryRate={stats['mastery_rate']}%")
        else:
            errors.append("Dashboard stats computation failed")

    except Exception as e:
        print(f"  ❌ Session history DB error: {e}")
        errors.append(f"Session history DB exception: {e}")

    # ------------------------------------------------------------------
    # 4. VERIFY ENDPOINTS VIA FASTAPI TESTCLIENT
    # ------------------------------------------------------------------
    print("\n[4/4] Verifying API Endpoints via FastAPI TestClient...")

    try:
        with TestClient(app) as client:
            # 4.1 Test POST /api/chat
            _sessions["test_session_api"] = {
                "session_id": "test_session_api",
                "subject": "linear_algebra",
                "matched_node": "vectors_intro",
                "traversal_path": ["vectors_intro"],
                "mastery": {},
                "status": "traversing",
            }
            chat_res = client.post("/api/chat", json={
                "session_id": "test_session_api",
                "node_id": "vectors_intro",
                "message": "Give me a simple example of vector addition."
            })
            if chat_res.status_code == 200 and "reply" in chat_res.json():
                print("  ✓ Endpoint POST /api/chat: 200 OK")
            else:
                errors.append(f"POST /api/chat returned status {chat_res.status_code}")

            # 4.2 Test GET /api/chat/history
            chathist_res = client.get("/api/chat/history?session_id=test_session_api&node_id=vectors_intro")
            if chathist_res.status_code == 200 and len(chathist_res.json().get("history", [])) > 0:
                print("  ✓ Endpoint GET /api/chat/history: 200 OK")
            else:
                errors.append(f"GET /api/chat/history returned status {chathist_res.status_code}")

            # 4.3 Test GET /api/history
            hist_res = client.get("/api/history")
            if hist_res.status_code == 200 and "sessions" in hist_res.json():
                print("  ✓ Endpoint GET /api/history: 200 OK")
            else:
                errors.append(f"GET /api/history returned status {hist_res.status_code}")

            # 4.4 Test GET /api/stats
            stats_res = client.get("/api/stats")
            if stats_res.status_code == 200 and "mastery_rate" in stats_res.json():
                print("  ✓ Endpoint GET /api/stats: 200 OK")
            else:
                errors.append(f"GET /api/stats returned status {stats_res.status_code}")

            # 4.5 Test Feature 3: GET /api/graph with session_id overlay
            sid = "sess_graph_mastery_verif"
            _sessions[sid] = {
                "session_id": sid,
                "subject": "linear_algebra",
                "matched_node": "vectors_intro",
                "traversal_path": ["vectors_intro"],
                "mastery": {"vectors_intro": 1.0},
                "status": "complete",
            }
            graph_res = client.get(f"/api/graph?subject=linear_algebra&session_id={sid}")
            if graph_res.status_code == 200:
                nodes = graph_res.json().get("nodes", [])
                target = next((n for n in nodes if n["id"] == "vectors_intro"), None)
                if target and target.get("status") == "mastered":
                    print("  ✓ Feature 3 (Graph Mastery Overlay): 200 OK — node status correctly marked 'mastered'")
                else:
                    errors.append("Graph node status did not overlay 'mastered'")
            else:
                errors.append(f"GET /api/graph with session_id returned status {graph_res.status_code}")

    except Exception as e:
        print(f"  ❌ API TestClient error: {e}")
        errors.append(f"API TestClient exception: {e}")

    # ------------------------------------------------------------------
    # SUMMARY REPORT
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    if not errors:
        print(" 🎉 ALL 3 FEATURES FULLY VERIFIED & WORKING PERFECTLY!")
        print("=" * 70)
        return True
    else:
        print(f" ❌ VERIFICATION FAILED WITH {len(errors)} ERROR(S):")
        for err in errors:
            print(f"   - {err}")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
