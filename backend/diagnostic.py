"""
diagnostic.py — Diagnostic engine for prerequisite gap detection.

Encapsulates the core diagnostic logic:
  1. Build a backward traversal path from a matched concept node.
  2. Walk the path, probing the student on each prerequisite.
  3. Identify the root-cause node: the earliest prerequisite that the student
     fails, which reveals the true knowledge gap.
  4. Generate a diagnostic summary and remediation recommendation.
"""

from __future__ import annotations

import random
from typing import Any

from graph import ConceptGraph
from remediation import generate_rich_remediation



# ---------------------------------------------------------------------------
# Diagnostic Engine
# ---------------------------------------------------------------------------

class DiagnosticEngine:
    """
    Stateless helper that operates on a session dict and graph.

    The session dict is the mutable state container (stored in _sessions in main.py).
    This class provides methods to advance the diagnostic flow:

        init_traversal  →  get_next_probe_node  →  record_answer  →  diagnose
    """

    def __init__(self, graph: ConceptGraph, questions: dict[str, list[dict[str, Any]]]):
        self.graph = graph
        self.questions = questions

    # ------------------------------------------------------------------
    # Step 1: Initialize traversal
    # ------------------------------------------------------------------

    def init_traversal(self, session: dict[str, Any], node_id: str) -> dict[str, Any]:
        """
        Build the backward traversal path from `node_id` and prepare
        the session for probing.

        The traversal path is ordered nearest-prerequisite-first (highest
        course order first) so we start testing the immediate prereqs of
        the target concept and walk backward only if those pass.

        Returns a summary dict for the API response.
        """
        if node_id not in self.graph.nodes:
            raise ValueError(f"Unknown node: {node_id!r}")

        # ancestors_ordered returns nearest-first (descending course order)
        path = self.graph.ancestors_ordered(node_id)

        # The target node itself is tested first, then its prereqs
        full_path = [node_id] + path

        session["matched_node"] = node_id
        session["traversal_path"] = full_path
        session["traversal_index"] = 0
        session["mastery"] = {}
        session["root_cause_node"] = None
        session["asked_questions"] = {}  # {node_id: [question_id, ...]}
        session["status"] = "traversing"

        return {
            "session_id": session["session_id"],
            "status": "traversing",
            "matched_node": node_id,
            "traversal_path": full_path,
            "total_steps": len(full_path),
            "current_step": 0,
            "current_node": full_path[0],
        }

    # ------------------------------------------------------------------
    # Step 2: Get the next probe question
    # ------------------------------------------------------------------

    def get_probe_question(
        self, session: dict[str, Any], node_id: str
    ) -> dict[str, Any] | None:
        """
        Return an unasked question for `node_id` from the question bank.
        Returns None if all questions for this node have been exhausted.
        """
        available = self.questions.get(node_id, [])
        if not available:
            return None

        asked = session.get("asked_questions", {}).get(node_id, [])
        unasked = [q for q in available if q["id"] not in asked]

        if not unasked:
            return None

        # Pick a random unasked question for variety
        question = random.choice(unasked)

        # Track that we've served this question
        if "asked_questions" not in session:
            session["asked_questions"] = {}
        session["asked_questions"].setdefault(node_id, []).append(question["id"])

        return {
            "node_id": node_id,
            "node_label": self.graph.nodes[node_id].label,
            "question_id": question["id"],
            "question": question["question"],
            "choices": question["choices"],
        }

    # ------------------------------------------------------------------
    # Step 3: Record an answer and advance
    # ------------------------------------------------------------------

    def record_answer(
        self,
        session: dict[str, Any],
        node_id: str,
        question_id: str,
        answer: str,
    ) -> dict[str, Any]:
        """
        Grade the student's answer and update session state.

        Logic:
        - If correct: mark node mastery = 1.0, advance to next node in path.
        - If incorrect: mark node mastery = 0.0, flag this as root cause
          (the earliest failed prerequisite), trigger diagnosis.

        Returns a result dict for the API response.
        """
        # Find the question
        node_qs = self.questions.get(node_id, [])
        question = next((q for q in node_qs if q["id"] == question_id), None)
        if question is None:
            raise ValueError(f"Question {question_id!r} not found for node {node_id!r}")

        is_correct = answer.strip().upper() == question["correct_answer"].strip().upper()

        # Update mastery
        session["mastery"][node_id] = 1.0 if is_correct else 0.0

        result: dict[str, Any] = {
            "session_id": session["session_id"],
            "node_id": node_id,
            "question_id": question_id,
            "submitted_answer": answer,
            "correct_answer": question["correct_answer"],
            "is_correct": is_correct,
            "explanation": question["explanation"],
        }

        if is_correct:
            # Advance traversal index
            path = session["traversal_path"]
            current_idx = session["traversal_index"]

            # Find the next node to probe
            next_idx = current_idx + 1
            session["traversal_index"] = next_idx

            if next_idx < len(path):
                result["next_action"] = "continue"
                result["next_node"] = path[next_idx]
                result["progress"] = f"{next_idx}/{len(path)}"
            else:
                # Student passed all nodes — no gap found!
                session["status"] = "diagnosed"
                session["root_cause_node"] = None
                result["next_action"] = "diagnosed"
                result["diagnosis"] = "all_clear"
                result["progress"] = f"{len(path)}/{len(path)}"
        else:
            # Student failed — this is the root cause (or we probe deeper)
            # The diagnostic strategy: if the student fails the target node itself,
            # we continue probing prerequisites. If they fail a prerequisite,
            # that's the root cause.
            path = session["traversal_path"]
            current_idx = session["traversal_index"]
            matched = session["matched_node"]

            if node_id == matched and current_idx == 0:
                # Failed the target node itself — this is expected.
                # Advance to probe prerequisites to find the real gap.
                next_idx = current_idx + 1
                session["traversal_index"] = next_idx
                if next_idx < len(path):
                    result["next_action"] = "continue"
                    result["next_node"] = path[next_idx]
                    result["progress"] = f"{next_idx}/{len(path)}"
                    result["note"] = (
                        "You struggled with the target concept. "
                        "Let's check your prerequisites to find the real gap."
                    )
                else:
                    # Target node has no prerequisites — it IS the root cause
                    session["root_cause_node"] = node_id
                    session["status"] = "diagnosed"
                    result["next_action"] = "diagnosed"
                    result["root_cause"] = node_id
            else:
                # Failed a prerequisite — this is the root cause
                session["root_cause_node"] = node_id
                session["status"] = "diagnosed"
                result["next_action"] = "diagnosed"
                result["root_cause"] = node_id

        return result

    # ------------------------------------------------------------------
    # Step 4: Generate diagnosis summary
    # ------------------------------------------------------------------

    def diagnose(self, session: dict[str, Any]) -> dict[str, Any]:
        """
        Generate a diagnostic summary card from the session state.
        """
        matched_node = session["matched_node"]
        root_cause = session.get("root_cause_node")
        mastery = session.get("mastery", {})
        path = session.get("traversal_path", [])

        # Build the traversal results with mastery scores
        traversal_results = []
        for nid in path:
            node = self.graph.nodes.get(nid)
            if node:
                traversal_results.append({
                    "node_id": nid,
                    "label": node.label,
                    "order": node.order,
                    "mastery": mastery.get(nid),
                    "status": (
                        "passed" if mastery.get(nid, 0) >= 1.0
                        else "failed" if mastery.get(nid) is not None
                        else "untested"
                    ),
                })

        # Count stats
        tested = sum(1 for nid in path if mastery.get(nid) is not None)
        passed = sum(1 for nid in path if mastery.get(nid, 0) >= 1.0)
        failed = sum(1 for nid in path if mastery.get(nid) is not None and mastery.get(nid, 0) < 1.0)

        # Confidence: how deep into the tree we probed
        confidence = tested / max(len(path), 1)

        diagnosis: dict[str, Any] = {
            "session_id": session["session_id"],
            "original_query": session.get("original_query", ""),
            "matched_node": matched_node,
            "matched_node_label": self.graph.nodes[matched_node].label if matched_node else None,
            "root_cause_node": root_cause,
            "root_cause_label": (
                self.graph.nodes[root_cause].label if root_cause else None
            ),
            "traversal_path": traversal_results,
            "stats": {
                "total_nodes": len(path),
                "tested": tested,
                "passed": passed,
                "failed": failed,
                "confidence": round(confidence, 2),
            },
            "status": session["status"],
        }

        if root_cause:
            # Compute how many steps back the root cause is
            gap_depth = 0
            for i, nid in enumerate(path):
                if nid == root_cause:
                    gap_depth = i
                    break
            diagnosis["gap_depth"] = gap_depth
            diagnosis["summary"] = (
                f"Your confusion about '{self.graph.nodes[matched_node].label}' "
                f"traces back to a gap in '{self.graph.nodes[root_cause].label}', "
                f"which is {gap_depth} prerequisite{'s' if gap_depth != 1 else ''} "
                f"earlier in the course."
            )
        else:
            diagnosis["gap_depth"] = 0
            diagnosis["summary"] = (
                f"Great news! You demonstrated mastery of "
                f"'{self.graph.nodes[matched_node].label}' and all its prerequisites. "
                f"Your confusion may be about a specific problem type rather than "
                f"a conceptual gap."
            )

        return diagnosis

    # ------------------------------------------------------------------
    # Step 5: Remediation content
    # ------------------------------------------------------------------

    def get_remediation(self, node_id: str, subject_slug: str = "linear_algebra") -> dict[str, Any]:
        """
        Return rich remediation content for a node: AI explanation, worked examples,
        misconceptions, practice questions, and video keywords.
        """
        if node_id not in self.graph.nodes:
            raise ValueError(f"Unknown node: {node_id!r}")

        node = self.graph.nodes[node_id]
        prereqs = self.graph.prereqs_of.get(node_id, [])
        dependents = self.graph.dependents_of.get(node_id, [])

        prereq_objs = [
            {"id": pid, "label": self.graph.nodes[pid].label}
            for pid in prereqs
            if pid in self.graph.nodes
        ]
        dependent_objs = [
            {"id": did, "label": self.graph.nodes[did].label}
            for did in dependents
            if did in self.graph.nodes
        ]

        rich = generate_rich_remediation(
            subject_slug=subject_slug,
            node_id=node_id,
            node_label=node.label,
            node_description=node.description,
            prereqs=prereq_objs,
            dependents=dependent_objs,
        )

        practice_qs = self.questions.get(node_id, [])
        practice = [
            {
                "question_id": q["id"],
                "question": q["question"],
                "choices": q["choices"],
            }
            for q in practice_qs
        ]

        return {
            "node_id": node_id,
            "label": node.label,
            "description": node.description,
            "detailed_explanation": rich.get("detailed_explanation", node.description),
            "worked_examples": rich.get("worked_examples", []),
            "common_misconceptions": rich.get("common_misconceptions", []),
            "video_keywords": rich.get("video_keywords", []),
            "summary_tips": rich.get("summary_tips", []),
            "order": node.order,
            "prerequisites": prereq_objs,
            "leads_to": dependent_objs,
            "practice_questions": practice,
            "tips": (
                f"Focus on understanding '{node.label}' before moving on. "
                f"This concept builds on {len(prereqs)} prerequisite(s) and "
                f"is needed for {len(dependents)} downstream concept(s)."
            ),
        }


    # ------------------------------------------------------------------
    # Step 6: Retest
    # ------------------------------------------------------------------

    def prepare_retest(self, session: dict[str, Any]) -> dict[str, Any]:
        """
        After remediation, re-serve a question for the root-cause node
        to verify the student has fixed the gap.
        """
        root_cause = session.get("root_cause_node")
        if not root_cause:
            return {
                "session_id": session["session_id"],
                "status": "no_root_cause",
                "message": "No root cause was identified — nothing to retest.",
            }

        session["status"] = "retesting"

        # Get an unasked question (or re-ask if exhausted)
        question = self.get_probe_question(session, root_cause)
        if question is None:
            # All questions exhausted — reset asked list and pick one
            session.setdefault("asked_questions", {})[root_cause] = []
            question = self.get_probe_question(session, root_cause)

        return {
            "session_id": session["session_id"],
            "status": "retesting",
            "root_cause_node": root_cause,
            "root_cause_label": self.graph.nodes[root_cause].label,
            "question": question,
        }

    # ------------------------------------------------------------------
    # Step 7: Generate trace log (for /api/diagnose)
    # ------------------------------------------------------------------

    def generate_trace_log(
        self,
        query: str,
        matched_node_id: str,
        similarity_score: float,
        traversal_path: list[str],
    ) -> list[str]:
        """
        Build the trace_log array that the frontend reasoning console
        reveals line-by-line with a typewriter effect.
        """
        matched_label = self.graph.nodes[matched_node_id].label

        log: list[str] = [
            "initializing diagnostic engine...",
            f"received query: \"{query}\"",
            "embedding query using gemini-embedding-2...",
            "matching query to concept graph...",
            f"best match: {matched_label} (similarity {similarity_score:.2f})",
        ]

        # List top prereqs for context
        prereqs = self.graph.prereqs_of.get(matched_node_id, [])
        if prereqs:
            prereq_labels = [self.graph.nodes[p].label for p in prereqs if p in self.graph.nodes]
            log.append(f"direct prerequisites: {', '.join(prereq_labels)}")

        log.append("walking backward through prerequisites...")

        # Show the traversal path step by step
        for i, nid in enumerate(traversal_path):
            node_label = self.graph.nodes[nid].label
            if i == 0:
                log.append(f"step {i}: probing target → {node_label}")
            else:
                log.append(f"step {i}: probing prerequisite → {node_label}")

        log.append(f"traversal path built: {len(traversal_path)} nodes to probe")
        log.append("ready — awaiting student responses...")

        return log

    # ------------------------------------------------------------------
    # Step 8: Generate explanation (for /api/diagnose/explain)
    # ------------------------------------------------------------------

    def generate_explanation(self, session: dict[str, Any]) -> dict[str, Any]:
        """
        Build the plain-language explanation for the confirmed root cause.
        Used by GET /api/diagnose/explain.
        """
        matched_node = session.get("matched_node")
        root_cause = session.get("root_cause_node")
        mastery = session.get("mastery", {})
        path = session.get("traversal_path", [])

        if not root_cause:
            return {
                "root_node_id": None,
                "root_node_label": None,
                "explanation": (
                    "Great news! You demonstrated mastery of all tested prerequisites. "
                    "Your confusion may be about a specific problem type rather than "
                    "a conceptual gap."
                ),
            }

        matched_label = self.graph.nodes[matched_node].label if matched_node else "the target concept"
        root_label = self.graph.nodes[root_cause].label

        # Count how many steps back the root cause is
        gap_depth = 0
        passed_labels: list[str] = []
        for i, nid in enumerate(path):
            if nid == root_cause:
                gap_depth = i
                break
            if mastery.get(nid, 0) >= 1.0:
                passed_labels.append(self.graph.nodes[nid].label)

        # Try AI explanation generation
        import os
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                prompt = (
                    f"A student reported feeling confused about '{matched_label}'. "
                    f"Our diagnostic engine probed them backward through course prerequisites. "
                    f"They successfully mastered: {', '.join(passed_labels) if passed_labels else 'none'}. "
                    f"However, they failed on '{root_label}' ({self.graph.nodes[root_cause].description}).\n\n"
                    f"Write a 2-paragraph empathetic, encouraging, and clear diagnostic explanation. "
                    f"You MUST mention both concepts by their exact titles '{matched_label}' and '{root_label}'. "
                    f"Explain precisely WHY struggling with '{root_label}' causes confusion when trying to learn '{matched_label}'."
                )

                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt
                )


                if response.text and response.text.strip():
                    return {
                        "root_node_id": root_cause,
                        "root_node_label": root_label,
                        "root_cause_node": root_cause,
                        "root_cause": root_cause,
                        "explanation": response.text.strip(),
                    }
            except Exception as e:
                print(f"[Explanation] AI generation fallback ({e})")


        # Build a narrative template explanation fallback
        if passed_labels:
            passed_str = " and ".join(passed_labels) if len(passed_labels) <= 2 else (
                ", ".join(passed_labels[:-1]) + f", and {passed_labels[-1]}"
            )
            explanation = (
                f"You said you're stuck on {matched_label}. Tracing backward, "
                f"{passed_str} {'checks' if len(passed_labels) == 1 else 'all check'} out — "
                f"but {root_label}, {gap_depth} concept{'s' if gap_depth != 1 else ''} "
                f"upstream, doesn't. That's the real gap."
            )
        else:
            explanation = (
                f"You said you're stuck on {matched_label}. Testing backward through "
                f"prerequisites, {root_label} — {gap_depth} concept{'s' if gap_depth != 1 else ''} "
                f"earlier in the course — is where the gap begins. "
                f"Strengthening this foundation should unlock the concepts that follow."
            )

        return {
            "root_node_id": root_cause,
            "root_node_label": root_label,
            "root_cause_node": root_cause,
            "root_cause": root_cause,
            "explanation": explanation,
        }



    # ------------------------------------------------------------------
    # Step 9: Score practice answer (for /api/practice/answer)
    # ------------------------------------------------------------------

    def score_practice_answer(
        self,
        session: dict[str, Any],
        question_id: str,
        answer: str,
    ) -> dict[str, Any]:
        """
        Grade a practice answer during remediation.
        Tracks attempts and flips node_mastered when the student passes.
        """
        root_cause = session.get("root_cause_node") or session.get("matched_node")
        if not root_cause:
            for nid, qlist in self.questions.items():
                if any(q["id"] == question_id for q in qlist):
                    root_cause = nid
                    break

        if not root_cause:
            root_cause = list(self.questions.keys())[0] if self.questions else None

        if not root_cause:
            raise ValueError("No node found for practice question.")

        session["root_cause_node"] = root_cause

        # Find the question in the node's bank
        node_qs = self.questions.get(root_cause, [])
        question = next((q for q in node_qs if q["id"] == question_id), None)
        if question is None:
            # Search across all node question banks
            for nid, qlist in self.questions.items():
                match = next((q for q in qlist if q["id"] == question_id), None)
                if match:
                    question = match
                    root_cause = nid
                    session["root_cause_node"] = nid
                    break

        if question is None:
            raise ValueError(f"Question {question_id!r} not found.")


        is_correct = answer.strip().upper() == question["correct_answer"].strip().upper()

        # Track practice attempts
        practice_key = "practice_attempts"
        if practice_key not in session:
            session[practice_key] = {}
        session[practice_key].setdefault(root_cause, []).append({
            "question_id": question_id,
            "answer": answer,
            "correct": is_correct,
        })

        # Determine if node is mastered (any correct practice answer = mastered)
        attempts = session[practice_key][root_cause]
        any_correct = any(a["correct"] for a in attempts)

        if any_correct:
            session["mastery"][root_cause] = 1.0

        return {
            "correct": is_correct,
            "correct_answer": question["correct_answer"],
            "explanation": question["explanation"],
            "node_mastered": any_correct,
            "attempts": len(attempts),
        }

    # ------------------------------------------------------------------
    # Step 10: Execute retest (for /api/retest spec-aligned)
    # ------------------------------------------------------------------

    def execute_retest(
        self,
        session: dict[str, Any],
        question_id: str | None = None,
        answer: str | None = None,
    ) -> dict[str, Any]:
        """
        Scoring retest answer or validating mastery.
        Returns spec-aligned response: {solved, updated_graph_state}.
        """
        root_cause = session.get("root_cause_node")
        path = session.get("traversal_path", [])
        matched = session.get("matched_node")

        # If retest answer is explicitly provided, grade it
        solved = True
        if question_id and answer and root_cause:
            node_qs = self.questions.get(root_cause, [])
            question = next((q for q in node_qs if q["id"] == question_id), None)
            if question:
                is_correct = str(answer).strip().upper() == question["correct_answer"].strip().upper()
                solved = is_correct


        if solved:
            # Mark everything in traversal path as mastered
            updated_state: list[dict[str, str]] = []
            for nid in path:
                session["mastery"][nid] = 1.0
                updated_state.append({"node_id": nid, "status": "mastered"})
            if matched and matched not in [s["node_id"] for s in updated_state]:
                session["mastery"][matched] = 1.0
                updated_state.append({"node_id": matched, "status": "mastered"})
            session["status"] = "complete"
            return {
                "solved": True,
                "updated_graph_state": updated_state,
            }
        else:
            return {
                "solved": False,
                "updated_graph_state": [
                    {"node_id": nid, "status": "weak" if nid == root_cause else "untested"}
                    for nid in path
                ],
            }

