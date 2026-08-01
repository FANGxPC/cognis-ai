# 🔬 Cognis
> **Uncover the root of every learning gap.**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)
![Gemini](https://img.shields.io/badge/Google--Gemini--3.5--Flash--Lite-8E75B2.svg)
![UI](https://img.shields.io/badge/UI-Vanilla--JS%20%7C%20TailwindCSS-06B6D4.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🌐 Live Deployment
### ✨ Try Cognis now: [cognis-ai-dxzl.onrender.com](https://cognis-ai-dxzl.onrender.com)

---

## 🎬 Demo Video


https://github.com/user-attachments/assets/24912cdc-50ae-4578-ac72-d246c8e712b3



---

## 📖 About

When students struggle with complex subjects like **Linear Algebra**, **Data Structures**, or **Physics**, the problem is rarely the topic right in front of them—it is almost always an **unrecognized prerequisite gap** from weeks or semesters prior.

Traditional AI tutors just answer the student's immediate prompt, creating a false sense of understanding. **Cognis** takes a radically different approach:
1. **Semantic Natural Language Matching**: Maps student queries to graph concept nodes using vector similarity.
2. **Backward Graph Traversal**: Traverses back through prerequisite Directed Acyclic Graphs (DAGs) asking targeted probing questions.
3. **Root Cause Isolation**: Pinpoints the exact foundational gap.
4. **Targeted AI Remediation & Interactive Tutoring**: Provides tailored bite-sized lessons, interactive practice, worked examples, and a node-contextual AI Chat Tutor.

---

## ✨ Key Features

- 🎯 **AI Cognis Scanner & Terminal**: Real-time terminal streaming typewriter interface that breaks down user intent, matches vector embeddings, and builds diagnostic paths.
- 🗺️ **Live Dynamic Knowledge Map**: Interactive `vis.Network` node graph with spring physics, glowing neon mastery status indicators (🟢 Mastered, 🔴 Root Cause, ⚪ Untested), and click-to-inspect actions.
- 💬 **Interactive AI Chat Tutor**: Node-contextual chatbot powered by `gemini-3.5-flash-lite` that guides students step-by-step without giving away answer shortcuts.
- 📊 **Progress & Analytics Dashboard**: Fixed scrollable diagnostic traversal logs with aggregate subject stats and session replay capabilities.
- 📸 **Dynamic Subject Generation**: Automatically generates dense 12–18 node prerequisite DAG graphs and question banks for ANY subject or uploaded syllabus file using AI.

---

## ⚙️ Architecture & Data Flow

```text
[ Student Query ] ---> [ Gemini Vector Embeddings ] ---> [ Cosine Similarity Node Match ]
                                                                   |
                                                                   v
[ Interactive Remediation ] <-- [ Root Cause Isolation ] <-- [ Backward DAG Traversal ]
       |
       +--> [ AI Lesson & Worked Examples ]
       +--> [ Dynamic Practice Questions ]
       +--> [ Contextual AI Chat Tutor ]
```

---

## 🚀 Quick Start Guide

### 1. Backend Setup (FastAPI & Gemini AI)

Navigate to the backend directory and set up a virtual environment:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory with your Google Gemini API key:
```env
GEMINI_API_KEY=your_google_gemini_api_key
```

Run the backend server:
```bash
uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

The frontend is built with vanilla HTML5, CSS3 (Custom Glassmorphism), and JavaScript. Serve it using Python's built-in web server:

```bash
cd frontend
python3 -m http.server 3000
```

Open `http://localhost:3000` in your browser.

---

## 📚 Adding a New Subject

Cognis is designed to easily scale to new topics. To add a subject:
1. Define your graph and question bank in JSON format (e.g., `biology_graph.json` and `biology_questions.json`).
2. Place these files in `backend/data/`.
3. Add a new entry to the `SUBJECTS_CONFIG` dictionary inside `backend/graph.py`.
4. Restart the backend server. The new subject will automatically be indexed and available in the frontend!

---

## 🧪 Automated Test Suite

Run the full pytest integration suite from the backend directory:
```bash
cd backend
pytest tests/test_new_features.py -v
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
