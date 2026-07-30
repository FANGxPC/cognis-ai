"""
graph.py — Concept graph data model and loading utilities.
Provides the in-memory graph representation and prerequisite traversal helpers.

Supports multiple subjects via SUBJECTS_CONFIG. Each subject has its own
graph and question bank files under the data/ directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from database import get_subject_graph, get_subject_questions, get_all_subjects

# ---------------------------------------------------------------------------
# Subject registry (now dynamic via DB)
# ---------------------------------------------------------------------------
def get_subjects_config():
    subjects = get_all_subjects()
    config = {}
    for sub in subjects:
        config[sub['slug']] = {
            "title": sub['title'],
            "description": sub['description']
        }
    return config

# Maintain for backwards compat where possible, though main.py should ideally use get_subjects_config()
SUBJECTS_CONFIG = get_subjects_config()


# ---------------------------------------------------------------------------
# Graph model
# ---------------------------------------------------------------------------

class ConceptNode:
    """Represents a single concept in the prerequisite graph."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.label: str = data["label"]
        self.description: str = data["description"]
        self.order: int = data["order"]
        self.mastery: float | None = data.get("mastery")  # None = untested

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "order": self.order,
            "mastery": self.mastery,
        }

    def __repr__(self) -> str:
        return f"<ConceptNode id={self.id!r} order={self.order}>"


class ConceptEdge:
    """Directed edge: `from_id` is a prerequisite of `to_id`."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.from_id: str = data["from"]
        self.to_id: str = data["to"]
        self.label: str = data.get("label", "requires")

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.from_id, "to": self.to_id, "label": self.label}


class ConceptGraph:
    """
    In-memory concept prerequisite graph.

    Edge direction: from_id → to_id means "from_id REQUIRES/must come before to_id".
    Backward traversal starts at a given node and walks toward its prerequisites.
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        self.nodes: dict[str, ConceptNode] = {
            n["id"]: ConceptNode(n) for n in raw["nodes"]
        }
        self.edges: list[ConceptEdge] = [ConceptEdge(e) for e in raw["edges"]]

        # Build adjacency: prereqs_of[node_id] = list of prerequisite node_ids
        self.prereqs_of: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        # And dependents: dependents_of[node_id] = list of concepts that need this one
        self.dependents_of: dict[str, list[str]] = {nid: [] for nid in self.nodes}

        for edge in self.edges:
            self.prereqs_of[edge.to_id].append(edge.from_id)
            self.dependents_of[edge.from_id].append(edge.to_id)

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------

    def backward_path(self, start_node_id: str) -> list[str]:
        """
        BFS backward traversal starting from `start_node_id`.
        Returns an ordered list of ancestor node IDs (prerequisites) from nearest
        to earliest, breadth-first.  The start node itself is NOT included.
        """
        if start_node_id not in self.nodes:
            raise ValueError(f"Unknown node: {start_node_id!r}")

        visited: set[str] = {start_node_id}
        queue: list[str] = [start_node_id]
        path: list[str] = []

        while queue:
            current = queue.pop(0)
            for prereq_id in self.prereqs_of.get(current, []):
                if prereq_id not in visited:
                    visited.add(prereq_id)
                    path.append(prereq_id)
                    queue.append(prereq_id)

        # Sort by order so the path reads chronologically (earliest first in course)
        path.sort(key=lambda nid: self.nodes[nid].order)
        return path

    def ancestors_ordered(self, start_node_id: str) -> list[str]:
        """
        Returns all ancestors (prerequisites, transitive) of a node,
        sorted by course order ascending (earliest prerequisite first).
        Useful for traversal: we probe from nearest prerequisite to farthest.
        """
        raw = self.backward_path(start_node_id)
        # Return nearest-in-course-order first (reverse so we test immediate prereqs first)
        return list(reversed(raw))

    def reset_mastery(self) -> None:
        """Reset all node mastery scores to None (untested). Used per session."""
        for node in self.nodes.values():
            node.mastery = None

    def update_mastery(self, node_id: str, score: float) -> None:
        """Update the mastery score (0.0–1.0) for a node."""
        if node_id not in self.nodes:
            raise ValueError(f"Unknown node: {node_id!r}")
        self.nodes[node_id].mastery = max(0.0, min(1.0, score))

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full graph (used by /graph endpoint)."""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def node_ids(self) -> list[str]:
        return list(self.nodes.keys())

    def get_node(self, node_id: str) -> ConceptNode:
        if node_id not in self.nodes:
            raise ValueError(f"Unknown node: {node_id!r}")
        return self.nodes[node_id]


# ---------------------------------------------------------------------------
# Factory — subject-aware loaders
# ---------------------------------------------------------------------------

def load_graph(subject: str = "linear_algebra") -> ConceptGraph:
    """Load the concept graph from the database for a given subject."""
    raw = get_subject_graph(subject)
    if not raw or not raw.get("nodes"):
        raise ValueError(f"Unknown subject '{subject}' or missing graph.")
    return ConceptGraph(raw)


def load_questions(subject: str = "linear_algebra") -> dict[str, list[dict[str, Any]]]:
    """Load the question bank from the database. Keyed by node_id."""
    questions = get_subject_questions(subject)
    if not questions:
        raise ValueError(f"Unknown subject '{subject}' or missing questions.")
    return questions
