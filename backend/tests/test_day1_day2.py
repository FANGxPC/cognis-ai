"""
test_day1_day2.py — Verification tests for Day 1 & 2 deliverables.

Run with:
    cd backend
    pytest tests/test_day1_day2.py -v

Tests:
  1. Graph schema validation (25 nodes, all edges point to valid nodes, no self-loops)
  2. ConceptGraph backward traversal (spot-check eigenvectors → matrix_rank path)
  3. Embedding API call (returns correct type and dimensionality)
  4. Cosine similarity sanity (identical vectors → 1.0, opposite → -1.0)
  5. Node embedding cache match (eigenvectors query → eigenvectors node is top match)
  6. Question bank coverage (every node has >= 3 questions)
  7. Question bank schema (each question has required fields)
  8. FastAPI health endpoint (integration test with TestClient)
  9. FastAPI /graph endpoint (returns nodes + edges)
 10. FastAPI /match endpoint (correct node returned for sample queries)
"""

from __future__ import annotations

import json
import os
import math
import sys
from pathlib import Path

import pytest

# Allow imports from backend root
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph import load_graph, load_questions, ConceptGraph
from embeddings import cosine_similarity, embed_text, NodeEmbeddingCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def graph() -> ConceptGraph:
    return load_graph("linear_algebra")


@pytest.fixture(scope="session")
def questions() -> dict:
    return load_questions("linear_algebra")


@pytest.fixture(scope="session")
def embedding_cache(graph) -> NodeEmbeddingCache:
    """Build the embedding cache once per test session (makes one API call)."""
    cache = NodeEmbeddingCache()
    cache.build(graph.nodes)
    return cache


# ---------------------------------------------------------------------------
# 1. Graph schema validation
# ---------------------------------------------------------------------------

class TestGraphSchema:
    def test_node_count(self, graph):
        """Must have between 15 and 25 nodes."""
        assert 15 <= len(graph.nodes) <= 25, (
            f"Expected 15-25 nodes, got {len(graph.nodes)}"
        )

    def test_nodes_have_required_fields(self, graph):
        for nid, node in graph.nodes.items():
            assert node.id, f"Node {nid} missing id"
            assert node.label, f"Node {nid} missing label"
            assert node.description, f"Node {nid} missing description"
            assert isinstance(node.order, int), f"Node {nid} order must be int"

    def test_edges_reference_valid_nodes(self, graph):
        node_ids = set(graph.nodes.keys())
        for edge in graph.edges:
            assert edge.from_id in node_ids, f"Edge from unknown node: {edge.from_id}"
            assert edge.to_id in node_ids, f"Edge to unknown node: {edge.to_id}"

    def test_no_self_loops(self, graph):
        for edge in graph.edges:
            assert edge.from_id != edge.to_id, f"Self-loop on node: {edge.from_id}"

    def test_prerequisite_adjacency_built(self, graph):
        """prereqs_of and dependents_of dicts must include all node_ids as keys."""
        for nid in graph.nodes:
            assert nid in graph.prereqs_of
            assert nid in graph.dependents_of

    def test_specific_nodes_exist(self, graph):
        """Spot-check that key nodes are present."""
        required = [
            "eigenvectors", "eigenvalues_intro", "matrix_rank",
            "linear_independence", "vectors_intro", "svd_intro",
        ]
        for nid in required:
            assert nid in graph.nodes, f"Missing expected node: {nid}"

    def test_eigenvectors_has_prerequisites(self, graph):
        """eigenvectors must have at least one prerequisite."""
        prereqs = graph.prereqs_of["eigenvectors"]
        assert len(prereqs) > 0, "eigenvectors has no prerequisites"


# ---------------------------------------------------------------------------
# 2. Backward traversal
# ---------------------------------------------------------------------------

class TestBackwardTraversal:
    def test_eigenvectors_ancestors_include_matrix_rank(self, graph):
        """
        The 'wow moment' traversal: eigenvectors → should reach matrix_rank.
        """
        path = graph.backward_path("eigenvectors")
        assert "matrix_rank" in path, (
            f"matrix_rank not found in backward path from eigenvectors. Got: {path}"
        )

    def test_eigenvectors_ancestors_include_vectors_intro(self, graph):
        """The earliest prerequisite should be vectors_intro."""
        path = graph.backward_path("eigenvectors")
        assert "vectors_intro" in path

    def test_no_duplicates_in_path(self, graph):
        path = graph.backward_path("svd_intro")
        assert len(path) == len(set(path)), "Backward path has duplicate nodes"

    def test_root_node_has_empty_path(self, graph):
        """A root node (no prerequisites) should return an empty path."""
        path = graph.backward_path("vectors_intro")
        assert path == [], f"Root node should have empty path, got: {path}"

    def test_ancestors_ordered_reversed(self, graph):
        """ancestors_ordered should return nearest prerequisites first (higher order)."""
        ordered = graph.ancestors_ordered("eigenvectors")
        # The most immediate prereqs (eigenvalues_intro, linear_independence) have
        # higher order numbers than vectors_intro, so they appear first.
        if len(ordered) >= 2:
            first_order = graph.nodes[ordered[0]].order
            last_order = graph.nodes[ordered[-1]].order
            assert first_order >= last_order, (
                "ancestors_ordered should return nearest (higher order) nodes first"
            )

    def test_mastery_update(self, graph):
        graph.update_mastery("matrix_rank", 0.8)
        assert graph.nodes["matrix_rank"].mastery == pytest.approx(0.8)
        graph.reset_mastery()
        assert graph.nodes["matrix_rank"].mastery is None


# ---------------------------------------------------------------------------
# 3. Embedding API
# ---------------------------------------------------------------------------

class TestEmbeddingAPI:
    def test_embed_text_returns_list_of_floats(self):
        """Basic smoke test: call the API and check the return type."""
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set — skipping live API test")
        vec = embed_text("What is a vector?")
        assert isinstance(vec, list), "embed_text should return a list"
        assert len(vec) > 100, f"Expected embedding dim > 100, got {len(vec)}"
        assert all(isinstance(v, float) for v in vec), "All values should be floats"

    def test_embed_text_consistent_dimension(self):
        """Two calls should produce same-length vectors."""
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set — skipping live API test")
        v1 = embed_text("eigenvalues")
        v2 = embed_text("matrix rank and null space")
        assert len(v1) == len(v2), "Embedding dimensions should match"


# ---------------------------------------------------------------------------
# 4. Cosine similarity (pure math, no API needed)
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.5, -0.3, 0.8]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert cosine_similarity(v1, v2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert cosine_similarity(v1, v2) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.5]) == 0.0

    def test_similarity_range(self):
        import random
        random.seed(42)
        v1 = [random.gauss(0, 1) for _ in range(50)]
        v2 = [random.gauss(0, 1) for _ in range(50)]
        sim = cosine_similarity(v1, v2)
        assert -1.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# 5. Node embedding cache
# ---------------------------------------------------------------------------

class TestNodeEmbeddingCache:
    def test_cache_is_built(self, embedding_cache):
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")
        assert embedding_cache.is_built

    def test_eigenvectors_query_top_match(self, embedding_cache):
        """'I don't understand eigenvectors' should map to the eigenvectors node."""
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")
        results = embedding_cache.match_query("I don't understand eigenvectors", top_k=3)
        top_id = results[0]["node_id"]
        assert top_id == "eigenvectors", (
            f"Expected 'eigenvectors' as top match, got '{top_id}'. Full results: {results}"
        )

    def test_matrix_rank_query(self, embedding_cache):
        """'I'm confused about matrix rank' should map to matrix_rank."""
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")
        results = embedding_cache.match_query("I'm confused about matrix rank", top_k=3)
        top_ids = [r["node_id"] for r in results]
        assert "matrix_rank" in top_ids[:2], (
            f"Expected 'matrix_rank' in top 2, got: {top_ids}"
        )

    def test_scores_sorted_descending(self, embedding_cache):
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set")
        results = embedding_cache.match_query("linear independence", top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 6 & 7. Question bank coverage and schema
# ---------------------------------------------------------------------------

class TestQuestionBank:
    def test_all_nodes_have_questions(self, graph, questions):
        """Every node must have at least 3 questions."""
        for node_id in graph.nodes:
            node_qs = questions.get(node_id, [])
            assert len(node_qs) >= 3, (
                f"Node '{node_id}' has only {len(node_qs)} questions (need >= 3)"
            )

    def test_question_schema(self, questions):
        """Each question must have required fields."""
        required_fields = {"id", "question", "choices", "correct_answer", "explanation"}
        for node_id, qs in questions.items():
            for q in qs:
                missing = required_fields - set(q.keys())
                assert not missing, (
                    f"Question in node '{node_id}' missing fields: {missing}"
                )

    def test_choices_count(self, questions):
        """Each question must have exactly 4 choices (A, B, C, D)."""
        for node_id, qs in questions.items():
            for q in qs:
                assert set(q["choices"].keys()) == {"A", "B", "C", "D"}, (
                    f"Question {q.get('id')} in node '{node_id}' does not have A/B/C/D choices"
                )

    def test_correct_answer_is_valid_choice(self, questions):
        for node_id, qs in questions.items():
            for q in qs:
                assert q["correct_answer"] in {"A", "B", "C", "D"}, (
                    f"Question {q.get('id')} in node '{node_id}' has invalid correct_answer: "
                    f"{q.get('correct_answer')}"
                )


# ---------------------------------------------------------------------------
# 8, 9, 10. FastAPI integration tests
# ---------------------------------------------------------------------------

class TestAPI:
    @pytest.fixture(scope="class")
    def client(self):
        """Test client fixture — skipped if API key not set (embeddings needed)."""
        if not os.getenv("GEMINI_API_KEY"):
            pytest.skip("GEMINI_API_KEY not set — skipping API integration tests")
        from fastapi.testclient import TestClient
        from main import app
        with TestClient(app) as c:
            yield c

    def test_health_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["embeddings_ready"] == "True"

    def test_health_node_count(self, client):
        resp = client.get("/health")
        assert resp.json()["nodes"] == "25"

    def test_graph_returns_nodes_and_edges(self, client):
        resp = client.get("/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 25
        assert len(data["edges"]) > 0

    def test_match_eigenvectors(self, client):
        resp = client.post("/match", json={"query": "I don't get eigenvectors"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["matched_node_id"] == "eigenvectors"
        assert "session_id" in data
        assert data["score"] > 0.5

    def test_match_creates_session(self, client):
        resp = client.post("/match", json={"query": "null space confuses me"})
        assert resp.status_code == 200
        sid = resp.json()["session_id"]
        assert sid  # non-empty

    def test_match_empty_query_rejected(self, client):
        resp = client.post("/match", json={"query": "   "})
        assert resp.status_code == 400

    def test_implemented_endpoints_reject_invalid_input(self, client):
        """Previously-stubbed endpoints are now implemented and return proper errors."""
        # /traverse with unknown session → 404
        resp = client.post("/traverse", json={"session_id": "x", "node_id": "y"})
        assert resp.status_code == 404

        # /diagnose with unknown session → 404
        resp = client.get("/diagnose?session_id=x")
        assert resp.status_code == 404

        # /remediate with unknown node → 404
        resp = client.get("/remediate?node_id=x")
        assert resp.status_code == 404
