"""
chat.py — AI Chat Tutor module for Prereq Sleuth.

Manages conversational Q&A sessions with Gemini for students studying a specific node.
"""

from __future__ import annotations

import json
import os
from typing import Any
from dotenv import load_dotenv
from google import genai

load_dotenv()

# In-memory store for chat histories: {"{session_id}:{node_id}": [ {"role": "user"|"assistant", "content": "..."}, ... ]}
_chat_histories: dict[str, list[dict[str, str]]] = {}
MAX_HISTORY = 20


def _get_client() -> genai.Client | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def get_chat_history(session_id: str, node_id: str) -> list[dict[str, str]]:
    key = f"{session_id}:{node_id}"
    return _chat_histories.get(key, [])


def chat_with_tutor(
    session_id: str,
    node_id: str,
    node_label: str,
    node_description: str,
    prereqs: list[str],
    user_message: str,
) -> str:
    """
    Send user_message + past history + system prompt context to Gemini 2.5 Flash,
    and return the AI response string.
    """
    key = f"{session_id}:{node_id}"
    history = _chat_histories.setdefault(key, [])

    # Append user message
    history.append({"role": "user", "content": user_message})

    # Trim history if too long
    if len(history) > MAX_HISTORY:
        _chat_histories[key] = history[-MAX_HISTORY:]
        history = _chat_histories[key]

    client = _get_client()
    if client:
        try:
            prereq_str = ", ".join(prereqs) if prereqs else "None"
            system_instruction = (
                f"You are a patient, encouraging AI tutor helping a student learn the concept '{node_label}'.\n"
                f"Concept Context: {node_description}\n"
                f"Prerequisites: {prereq_str}\n\n"
                f"Guidelines:\n"
                f"- Be concise, clear, and empathetic.\n"
                f"- Use simple real-world analogies where helpful.\n"
                f"- Break explanations into bite-sized steps.\n"
                f"- If the student is confused, ask guiding questions rather than just dumping answers.\n"
            )

            # Build full context for Gemini
            conversation_text = ""
            for item in history:
                speaker = "Student" if item["role"] == "user" else "Tutor"
                conversation_text += f"{speaker}: {item['content']}\n"

            prompt = f"{system_instruction}\n--- Conversation History ---\n{conversation_text}\nTutor:"

            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )



            reply = response.text.strip() if response and response.text else "I understand your question! Let's break this down step-by-step."
            history.append({"role": "assistant", "content": reply})
            return reply

        except Exception as e:
            print(f"[ChatTutor] Gemini call failed ({e}). Using offline fallback response.")

    # Offline / Fallback response
    fallback_reply = (
        f"Regarding **{node_label}**: {user_message.strip()} is a great question! "
        f"Remember that {node_label} focuses on: {node_description}. "
        f"Try working through the worked examples and practice questions on this page to test your understanding."
    )
    history.append({"role": "assistant", "content": fallback_reply})
    return fallback_reply
