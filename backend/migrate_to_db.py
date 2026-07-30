import json
from pathlib import Path
from database import save_subject

DATA_DIR = Path(__file__).parent / "data"

SUBJECTS_CONFIG = {
    "linear_algebra": {
        "title": "Linear Algebra",
        "description": "Vectors, matrices, transformations, eigenvalues & more",
        "graph_file": "linear_algebra_graph.json",
        "questions_file": "linear_algebra_questions.json",
    },
    "data_structures": {
        "title": "Data Structures",
        "description": "Arrays, linked lists, trees, graphs, heaps, hash tables & more",
        "graph_file": "data_structures_graph.json",
        "questions_file": "data_structures_questions.json",
    },
}

def run_migration():
    for slug, cfg in SUBJECTS_CONFIG.items():
        graph_path = DATA_DIR / cfg["graph_file"]
        questions_path = DATA_DIR / cfg["questions_file"]
        
        if graph_path.exists() and questions_path.exists():
            with open(graph_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)
            with open(questions_path, "r", encoding="utf-8") as f:
                questions_data = json.load(f)
                
            save_subject(slug, cfg["title"], cfg["description"], graph_data, questions_data)
            print(f"Migrated {slug}")
        else:
            print(f"Skipping {slug}, files not found.")

if __name__ == "__main__":
    run_migration()
