# Prereq-Sleuth

An AI-powered prerequisite detective that uncovers the real root cause of student confusion. Built with a knowledge graph + embedding-based system that traces backwards through concepts to find hidden learning gaps — then proves it with live probing questions.

## Features
- **Concept Knowledge Graph**: Maps out subject concepts and their prerequisites.
- **Embedding-based Search**: Maps student free-text queries to specific nodes in the knowledge graph.
- **Diagnostic Engine**: Traces backward through the knowledge graph to identify foundational gaps.
- **AI-Powered Probing**: Asks dynamic probing questions to verify understanding and score answers.
- **Remediation**: Provides explanations and practice questions targeted at the identified root cause.

## Tech Stack
- **Backend**: Python, FastAPI, Google GenAI (for LLM capabilities), SQLite (aiosqlite), and PyMuPDF.
- **Frontend**: Vanilla HTML, CSS, JavaScript.

## Project Structure
- `/backend`: FastAPI application, AI logic, database interactions, and graph generation.
  - `main.py`: FastAPI entry point exposing REST endpoints.
  - `diagnostic.py`: Core diagnostic traversal logic.
  - `graph.py` & `embeddings.py`: Knowledge graph structure and node embeddings.
  - `database.py`: Database connection and initial setup for tracking mastery.
- `/frontend`: Client-side interface to interact with the diagnostic engine.
  - `index.html`: Landing page for the application.
  - `/pages`: Various user interface pages including scanning, diagnostic paths, quizzes, and remediation.

## Getting Started

### Backend Setup
1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables:
   Copy `.env.example` to `.env` and fill in your required API keys (e.g., `GEMINI_API_KEY`).
5. Run the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```
   The API will be available at `http://localhost:8000`.

### Frontend Setup
1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Serve the frontend files locally. You can use Python's built-in HTTP server:
   ```bash
   python -m http.server 3000
   ```
3. Open `http://localhost:3000` in your web browser to view the application. Ensure the backend is running to allow API interactions.

## License
[MIT License](LICENSE)
