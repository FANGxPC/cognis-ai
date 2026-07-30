"""
remediation.py — AI-powered rich learning path & remediation generator.

Generates structured, in-depth pedagogical content for a target concept:
  - Deep concept explanation
  - Step-by-step worked examples
  - Common misconceptions & pitfalls
  - Practical tips & intuition
  - Video search recommendations & keywords
"""

from __future__ import annotations

import json
import os
from typing import Any
from dotenv import load_dotenv
from google import genai
from google.genai import types

from database import get_remediation_cache, save_remediation_cache

load_dotenv()


def _get_client() -> genai.Client | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def generate_rich_remediation(
    subject_slug: str,
    node_id: str,
    node_label: str,
    node_description: str,
    prereqs: list[dict[str, str]],
    dependents: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Returns rich remediation material for a concept node.
    Checks DB cache first; generates using Gemini if not cached.
    """
    cache_key = f"{subject_slug}:{node_id}"
    cached = get_remediation_cache(cache_key)
    if cached:
        print(f"[Remediation] Returning cached remediation for '{cache_key}'")
        return cached

    # Attempt Gemini API generation
    client = _get_client()
    if client:
        try:
            prompt = f"""
You are an expert, world-class educator creating interactive lesson materials for students who struggle with the concept: "{node_label}".

Context:
- Description: {node_description}
- Prerequisites: {', '.join([p['label'] for p in prereqs]) if prereqs else 'None'}
- Leads to downstream concepts: {', '.join([d['label'] for d in dependents]) if dependents else 'None'}

Generate a structured JSON object for this lesson containing:
1. "detailed_explanation": A comprehensive, clear 3-paragraph explanation building intuitive understanding from first principles.
2. "worked_examples": An array of 2 worked examples. Each example should have:
    - "title": Example title
    - "problem": Problem statement
    - "solution_steps": List of step-by-step explanation strings
    - "key_takeaway": Core lesson from this example
3. "common_misconceptions": An array of 2-3 objects, each with:
    - "misconception": What students wrongly believe
    - "reality": The correct mental model
4. "video_keywords": Array of 3 search strings for YouTube/Khan Academy (e.g. "Binary Search Tree traversal tutorial")
5. "summary_tips": Array of 3 key rules to remember.

Output ONLY valid JSON matching this schema (no markdown fences):
{{
  "detailed_explanation": "...",
  "worked_examples": [
    {{
      "title": "...",
      "problem": "...",
      "solution_steps": ["Step 1...", "Step 2..."],
      "key_takeaway": "..."
    }}
  ],
  "common_misconceptions": [
    {{
      "misconception": "...",
      "reality": "..."
    }}
  ],
  "video_keywords": ["..."],
  "summary_tips": ["..."]
}}
"""
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,


                config=types.GenerateContentConfig(
                    temperature=0.3,
                ),
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            ai_data = json.loads(raw_text.strip())

            result = {
                "node_id": node_id,
                "label": node_label,
                "description": node_description,
                "detailed_explanation": ai_data.get("detailed_explanation", node_description),
                "worked_examples": ai_data.get("worked_examples", []),
                "common_misconceptions": ai_data.get("common_misconceptions", []),
                "video_keywords": ai_data.get("video_keywords", [f"{node_label} tutorial", f"{node_label} explained"]),
                "summary_tips": ai_data.get("summary_tips", [f"Master {node_label} fundamentals before proceeding."]),
            }

            save_remediation_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"[Remediation] Gemini generation failed ({e}). Using robust fallback generator.")

    # Offline / Fallback Generator
    fallback = {
        "node_id": node_id,
        "label": node_label,
        "description": node_description,
        "detailed_explanation": (
            f"The concept of **{node_label}** is a cornerstone of this subject.\n\n"
            f"{node_description}\n\n"
            f"When approaching problems in {node_label}, it is critical to break down the task into foundational prerequisite steps. "
            f"Ensure you understand the core mechanics and properties before tackling advanced applications."
        ),
        "worked_examples": [
            {
                "title": f"Basic Application of {node_label}",
                "problem": f"How do you verify the fundamental property of {node_label}?",
                "solution_steps": [
                    f"Step 1: Identify the inputs and constraints required for {node_label}.",
                    "Step 2: Apply the definition step-by-step.",
                    "Step 3: Check edge cases and verify correctness."
                ],
                "key_takeaway": f"Always double-check definitions when dealing with {node_label}."
            }
        ],
        "common_misconceptions": [
            {
                "misconception": f"Assuming {node_label} works without fulfilling its prerequisite assumptions.",
                "reality": f"Prerequisites must be fully satisfied before applying rules from {node_label}."
            }
        ],
        "video_keywords": [
            f"{node_label} conceptual guide",
            f"Understanding {node_label} step by step",
            f"{node_label} solved examples"
        ],
        "summary_tips": [
            f"Review prerequisites before studying {node_label}.",
            "Work through concrete examples line by line.",
            "Test yourself with probe questions to verify retention."
        ]
    }
    save_remediation_cache(cache_key, fallback)
    return fallback
