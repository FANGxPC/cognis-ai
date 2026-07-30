"""
embeddings.py — Embedding API wrapper and similarity utilities.

Uses Google's gemini-embedding-004 model via the google-genai SDK (v2.x).
Embeddings for all graph node descriptions are cached at startup to avoid
repeated API calls during a session.
"""

from __future__ import annotations

import os
import math
from typing import Any

from dotenv import load_dotenv
from google import genai

load_dotenv()

import hashlib
import re

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMBEDDING_MODEL = "gemini-embedding-2"


def _get_client() -> genai.Client:
    """Return a configured Gemini client. Reads GEMINI_API_KEY from env."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set. Copy backend/.env.example to backend/.env and fill it in."
        )
    return genai.Client(api_key=api_key)


def _offline_embed_text(text: str, dim: int = 128) -> list[float]:
    """
    Deterministic fallback embedding generator when Gemini API is unavailable or unauthenticated.
    Uses TF-IDF-style word and n-gram feature hashing to construct a unit-length vector.
    """
    stop_words = {
        "i", "m", "a", "an", "the", "about", "confused", "stuck", "don", "t",
        "understand", "get", "is", "of", "in", "or", "and", "by", "to", "on",
        "for", "with", "what", "how", "why", "can", "you", "help", "me", "this"
    }
    vec = [0.0] * dim
    words = re.findall(r"\w+", text.lower())
    for word in words:
        if word in stop_words:
            continue
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        vec[h % dim] += 5.0
        for i in range(len(word) - 2):
            gh = int(hashlib.md5(word[i : i + 3].encode()).hexdigest(), 16)
            vec[gh % dim] += 1.0

    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        vec[0] = 1.0
        return vec
    return [x / norm for x in vec]


# ---------------------------------------------------------------------------
# Core embedding functions
# ---------------------------------------------------------------------------

_FALLBACK_WARNED = False


def embed_text(text: str) -> list[float]:
    """
    Embed a single piece of text using gemini-embedding-2.
    Falls back to offline deterministic embeddings if API authentication fails.
    """
    global _FALLBACK_WARNED
    try:
        client = _get_client()
        result = client.models.embed_content(
            model=_EMBEDDING_MODEL,
            contents=[text],
        )
        return result.embeddings[0].values
    except Exception as e:
        if not _FALLBACK_WARNED:
            print(f"[EmbeddingCache] WARNING: Gemini API call failed ({e}). Using offline embeddings fallback.")
            _FALLBACK_WARNED = True
        return _offline_embed_text(text)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts (one vector per text).
    Returns a list of embedding vectors.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _embed_one(text: str) -> list[float]:
        return embed_text(text)

    with ThreadPoolExecutor(max_workers=5) as executor:
        return list(executor.map(_embed_one, texts))


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two embedding vectors.
    Returns a float in [-1, 1]; higher = more similar.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Node embedding cache
# ---------------------------------------------------------------------------

class NodeEmbeddingCache:
    """
    Precomputes and caches embeddings for all node descriptions in the graph.
    Call `build(graph.nodes)` once at startup; then use `match_query(query_text)`.
    """

    def __init__(self) -> None:
        self._node_embeddings: dict[str, list[float]] = {}
        self._nodes: dict[str, Any] = {}
        self._built = False

    def build(self, nodes: dict[str, Any]) -> None:
        """
        Embed all node descriptions in a single batch call.
        `nodes` is a dict of {node_id: ConceptNode}.
        """
        self._nodes = nodes
        node_ids = list(nodes.keys())
        texts = [
            f"{nodes[nid].label} {nodes[nid].label} {nodes[nid].description}"
            for nid in node_ids
        ]

        print(f"[EmbeddingCache] Embedding {len(texts)} node texts...")
        vectors = embed_texts(texts)

        self._node_embeddings = dict(zip(node_ids, vectors))
        self._built = True
        print(f"[EmbeddingCache] Done. Vector dim = {len(vectors[0])}")

    def match_query(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """
        Embed the query and find the top-k most similar nodes.
        Returns a list of dicts: [{node_id, score}, ...] sorted descending.
        """
        if not self._built:
            raise RuntimeError("Call build() before match_query().")

        query_vec = embed_text(query)
        stop_words = {"i", "m", "don", "t", "get", "a", "the", "about", "confused", "stuck", "is", "in", "of", "to"}
        query_words = set(re.findall(r"\w+", query.lower())) - stop_words

        scores: list[dict[str, Any]] = []
        for nid, vec in self._node_embeddings.items():
            sim = cosine_similarity(query_vec, vec)
            node = self._nodes.get(nid)
            if node:
                label_words = set(re.findall(r"\w+", f"{nid} {node.label}".lower())) - stop_words
                overlap = query_words.intersection(label_words)
                if overlap:
                    sim = max(sim, min(0.95, 0.75 + 0.1 * len(overlap)))
            scores.append({"node_id": nid, "score": sim})

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    @property
    def is_built(self) -> bool:
        return self._built


# Singleton instance used by the FastAPI app
node_cache = NodeEmbeddingCache()
