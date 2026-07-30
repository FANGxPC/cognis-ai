#!/usr/bin/env python3
"""
generate_questions.py — Day 2 script.

Calls Gemini to generate 4 multiple-choice questions per node in the concept graph,
then saves the result to backend/data/questions.json for human review.
Supports resuming from existing questions.json and implements robust retry backoff on 429s.

Usage:
    cd backend
    python scripts/generate_questions.py

Requires GEMINI_API_KEY in backend/.env
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Allow imports from backend root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
GRAPH_FILE = DATA_DIR / "graph.json"
OUTPUT_FILE = DATA_DIR / "questions.json"

# Use gemini-3.5-flash-lite model
GENERATION_MODEL = "gemini-3.5-flash-lite"



PROMPT_TEMPLATE = """You are an expert Linear Algebra educator building a diagnostic question bank.

Generate exactly 4 multiple-choice questions that test whether a student genuinely understands the concept: "{label}".

Concept description: {description}

Requirements:
- Each question should be answerable by a student who genuinely understands the concept, but not by one who is guessing.
- Questions should range from recall (1), conceptual understanding (2), and simple application (1).
- Each question must have exactly 4 answer choices (A, B, C, D).
- Exactly one answer must be correct.
- Wrong answers (distractors) should represent plausible common misconceptions.
- Keep each question concise (1-3 sentences max).

Return ONLY a valid JSON array in this exact format (no markdown, no extra text):
[
  {{
    "id": "q1",
    "question": "...",
    "choices": {{
      "A": "...",
      "B": "...",
      "C": "...",
      "D": "..."
    }},
    "correct_answer": "A",
    "explanation": "Brief explanation of why the correct answer is right."
  }},
  ...
]
"""


def generate_questions_for_node(
    client: genai.Client, node_id: str, label: str, description: str
) -> list[dict]:
    """Call Gemini to generate questions for a single node with robust retry logic on 429s."""
    prompt = PROMPT_TEMPLATE.format(label=label, description=description)

    max_retries = 6
    backoff = 4.0

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GENERATION_MODEL,
                contents=prompt,
            )
            raw_text = response.text.strip()

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                if lines[0].startswith("```"):
                    raw_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            questions = json.loads(raw_text)

            # Enforce sequential IDs scoped to node
            for i, q in enumerate(questions, start=1):
                q["id"] = f"{node_id}_q{i}"

            return questions

        except APIError as e:
            # Check for 429 / resource exhausted
            if e.code == 429 or "quota" in str(e).lower() or "exhausted" in str(e).lower():
                print(f"\n[429 Resource Exhausted] Rate limited. Waiting {backoff} seconds (Attempt {attempt+1}/{max_retries})...")
                time.sleep(backoff)
                backoff *= 2.0
                continue
            raise e
        except json.JSONDecodeError as e:
            # If the response isn't clean JSON, retry with a slightly modified format request
            print(f"\n[JSON Error] Failed to parse JSON: {e}. Retrying...")
            time.sleep(2)
            continue

    raise RuntimeError(f"Failed to generate questions for {node_id} after {max_retries} attempts.")


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    with open(GRAPH_FILE, "r") as f:
        graph_data = json.load(f)

    nodes = graph_data["nodes"]
    print(f"Generating questions for {len(nodes)} nodes using {GENERATION_MODEL}...\n")

    # Load existing question bank if it exists to resume
    bank: dict[str, list[dict]] = {}
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                bank = json.load(f)
            print(f"Resuming: found existing question bank with {sum(1 for k, v in bank.items() if v)} nodes.")
        except Exception as e:
            print(f"Warning: could not read existing questions.json: {e}")

    failed: list[str] = []

    for i, node in enumerate(nodes, start=1):
        node_id = node["id"]
        label = node["label"]
        description = node["description"]

        # Skip if already generated
        if bank.get(node_id):
            print(f"[{i:02d}/{len(nodes)}] {label} ({node_id}) -> Already generated (skipped)")
            continue

        print(f"[{i:02d}/{len(nodes)}] {label} ({node_id})...", end=" ", flush=True)

        try:
            questions = generate_questions_for_node(client, node_id, label, description)
            bank[node_id] = questions
            print(f"✓ {len(questions)} questions")
            
            # Save progress after every single successful node!
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(bank, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"✗ FAILED: {e}")
            failed.append(node_id)

        # Base delay to prevent hitting rate limits
        time.sleep(6.0)

    print(f"\n✅ All generation attempts finished.")
    print(f"   Final saved to {OUTPUT_FILE}")
    print(f"   Nodes with questions: {sum(1 for v in bank.values() if v)} / {len(nodes)}")
    if failed:
        print(f"   Failed nodes: {failed}")


if __name__ == "__main__":
    main()
