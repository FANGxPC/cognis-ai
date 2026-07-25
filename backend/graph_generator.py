import json
import os
from typing import Any
from google import genai

def generate_graph_from_text(subject_id: str, subject_title: str, text: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert curriculum designer. Based on the following textbook text about {subject_title}, 
    generate a prerequisite concept graph and a set of diagnostic questions.
    
    The response must be valid JSON matching this schema:
    {{
        "graph": {{
            "nodes": [
                {{"id": "concept_1", "label": "Concept 1", "description": "...", "order": 1}}
            ],
            "edges": [
                {{"from": "concept_1", "to": "concept_2", "label": "requires"}}
            ]
        }},
        "questions": {{
            "concept_1": [
                {{
                    "id": "q1",
                    "question": "...",
                    "choices": {{"A": "...", "B": "..."}},
                    "correct_answer": "A",
                    "explanation": "..."
                }}
            ]
        }}
    }}
    
    Keep it to 5-7 core concepts, with 2 questions per concept. 
    Ensure it's a valid directed acyclic graph.
    
    Text snippet:
    {text[:5000]}
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt]
    )
    
    # Very naive JSON extraction
    text = response.text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end+1]
    
    return json.loads(text)

