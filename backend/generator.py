import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Optional: ensure api key is present (assuming it is set in env vars, e.g. GEMINI_API_KEY)
# If not, client will raise an error.

def get_client():
    return genai.Client()


GRAPH_SCHEMA_STR = """
{
  "nodes": [
    {
      "id": "node_slug",
      "label": "Node Title",
      "description": "Brief description of the concept",
      "order": 1
    }
  ],
  "edges": [
    {
      "from": "prerequisite_node_slug",
      "to": "dependent_node_slug",
      "label": "requires"
    }
  ]
}
"""

QUESTIONS_SCHEMA_STR = """
{
  "node_slug": [
    {
      "id": "q1",
      "question": "What is the capital of France?",
      "choices": {
        "A": "London",
        "B": "Paris",
        "C": "Berlin",
        "D": "Madrid"
      },
      "correct_answer": "B",
      "explanation": "Paris is the capital of France."
    }
  ]
}
"""

def parse_json_response(text: str) -> dict:
    # Safely extract JSON block if wrapped in markdown
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())

def generate_subject_content(topic: str, file_bytes: bytes = None, mime_type: str = "image/jpeg"):
    client = get_client()

    # Step 1: Generate Dense Learning Graph JSON
    graph_prompt = f"Create a DENSE, highly detailed, and deeply interconnected prerequisite knowledge graph for the subject: '{topic}'."
    if file_bytes:
        graph_prompt = "Analyze this syllabus document/image and create a DENSE, highly detailed, and deeply interconnected prerequisite knowledge graph based on its topics."

    graph_prompt += f"""
Return ONLY a single valid JSON object matching this schema (no markdown, no additional text):
{GRAPH_SCHEMA_STR}

CRITICAL DENSITY REQUIREMENTS:
1. Generate a DENSE network containing between 12 to 18 distinct concept nodes ranging from foundational prerequisites up to advanced topics.
2. Ensure HIGH EDGE DENSITY: Every non-root node MUST connect to multiple prerequisite nodes (e.g. 2-3 incoming/outgoing edges per node), forming a rich, branching dependency web rather than a simple linear chain.
3. Nodes must be logically ordered (order 1, 2, 3...) and edges must point strictly from prerequisite to dependent (from -> to).
"""


    contents = [graph_prompt]
    if file_bytes:
        contents = [
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            graph_prompt
        ]

    graph_response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json"
        )
    )

    graph_data = json.loads(graph_response.text.strip())

    # Step 2: Generate Question Bank for the Graph
    node_summaries = ", ".join([f"{n['id']} ({n['label']})" for n in graph_data.get("nodes", [])])

    questions_prompt = f"""
For the subject '{topic}' with concept nodes: {node_summaries}, generate at least 2 multiple-choice questions for EACH concept node.

Return ONLY a single valid JSON object where keys are node_slugs and values are arrays of question objects:
{QUESTIONS_SCHEMA_STR}
Ensure each choice dictionary has exactly keys "A", "B", "C", "D".
"""

    questions_response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=[questions_prompt],
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json"
        )
    )


    questions_data = json.loads(questions_response.text.strip())

    return graph_data, questions_data


