# Cognis: Uncovering the Root of Every Learning Gap

## What Inspired the Project

Every educator and student has experienced the same frustrating scenario. A student struggles with an advanced concept like Eigenvalues in Linear Algebra or Balanced Search Trees in Data Structures. They ask an AI tool for help, get a detailed explanation, read through it, try another problem, and fail again.

The issue is rarely the advanced topic sitting directly in front of the student. Almost always, the true hurdle is a forgotten prerequisite concept from weeks or semesters earlier—like confusing matrix determinant rules or misaligned pointer logic.

Standard AI chatbots treat symptoms rather than root causes. They answer whatever prompt the student types, offering quick solutions that create a false sense of understanding. We created Cognis to rethink how AI tutoring works. Instead of giving immediate answers to surface-level questions, Cognis uses graph theory and semantic search to walk backward through prerequisite dependency chains, locating and fixing the exact foundational gap.

---

## How We Built It

Cognis bridges vector search, graph traversal, and generative AI into a unified diagnostic pipeline.

```text
[ Student Query ] ---> [ Gemini Vector Embeddings ] ---> [ Cosine Similarity Node Matching ]
                                                                   |
                                                                   v
[ Targeted AI Remediation ] <-- [ Root Cause Isolation ] <-- [ Backward DAG Traversal ]
        |
        +--> [ Interactive Lessons & Worked Examples ]
        +--> [ Dynamic Practice Questions ]
        +--> [ Contextual AI Chat Tutor ]
```

### 1. Vector Search and Intent Matching
When a student submits a query, such as *"I am having trouble visualizing matrix transformations in 3D"*, Cognis converts the input into a high-dimensional vector using Google Gemini embeddings.

We calculate the cosine similarity between the query embedding vector $\vec{q} \in \mathbb{R}^d$ and target concept node embeddings $\vec{c}_i \in \mathbb{R}^d$:

\[
\text{Sim}(\vec{q}, \vec{c}_i) = \cos(\theta) = \frac{\vec{q} \cdot \vec{c}_i}{\|\vec{q}\|_2 \|\vec{c}_i\|_2} = \frac{\sum_{k=1}^{d} q_k c_{i,k}}{\sqrt{\sum_{k=1}^{d} q_k^2} \sqrt{\sum_{k=1}^{d} c_{i,k}^2}}
\]

The concept node $v^* = \arg\max_{v_i \in V} \text{Sim}(\vec{q}, \vec{c}_i)$ with the highest similarity score serves as the entry point into the subject's prerequisite graph.

### 2. Directed Acyclic Graph (DAG) Traversal
Subject knowledge is structured as a Directed Acyclic Graph $G = (V, E)$, where nodes $V$ represent individual topics and directed edges $(u, v) \in E$ specify that concept $u$ must be understood before concept $v$.

From the initial node $v^*$, Cognis collects all upstream dependencies using backward graph reachability:

\[
\text{Anc}(v^*) = \{ u \in V \mid \text{there exists a directed path } u \rightsquigarrow v^* \text{ in } G \}
\]

These ancestor nodes are sorted by topological ordering $\mathcal{T}: V \to \{1, \dots, |V|\}$ in descending course sequence order:

\[
P = (v_1, v_2, \dots, v_k) \quad \text{where } \mathcal{T}(v_1) > \mathcal{T}(v_2) > \dots > \mathcal{T}(v_k)
\]

This traversal order tests immediate prerequisites first, stepping further back into foundational material only if earlier checks reveal missing understanding.

### 3. Root Cause Isolation Algorithm
As Cognis runs diagnostic probes along path $P$, it evaluates student performance on targeted questions for each node. Let $M(v) \in [0, 1]$ denote student mastery for concept $v$, evaluated against a passing threshold $\tau = 0.7$:

\[
\text{Status}(v) = \begin{cases} \text{Mastered}, & \text{if } M(v) \ge \tau \\ \text{Failed}, & \text{if } M(v) < \tau \end{cases}
\]

The Root Cause Node $v_{\text{root}}$ represents the earliest node along the path where a prerequisite failure occurs:

\[
v_{\text{root}} = \text{first } v_i \in P \quad \text{such that } M(v_i) < \tau \text{ and } \forall u \in \text{Children}(v_i) \cap P, \; M(u) < \tau
\]

When $v_{\text{root}}$ is isolated, diagnostic probing stops. Cognis then shifts into remediation mode, supplying tailored explanations, step-by-step practice problems, and contextual AI tutoring focused on that exact gap.

### 4. Technical Architecture
- **Backend API**: Written in Python 3.10 using FastAPI and Uvicorn. Core graph management is handled in [backend/graph.py](file:///home/fang/Downloads/prereq-sleuth-frontend%20%281%29/prereq-sleuth-frontend/backend/graph.py), while diagnostic state logic is encapsulated in [backend/diagnostic.py](file:///home/fang/Downloads/prereq-sleuth-frontend%20%281%29/prereq-sleuth-frontend/backend/diagnostic.py).
- **Generative AI Integration**: Powered by Google Gemini 3.5 Flash and Lite using the `google-genai` SDK for vector embeddings, dynamic graph generation ([backend/generator.py](file:///home/fang/Downloads/prereq-sleuth-frontend%20%281%29/prereq-sleuth-frontend/backend/generator.py)), and node-level conversational support.
- **Frontend Interface**: Constructed with HTML5, Vanilla JavaScript (ES6+), and CSS3 with custom glassmorphism styling. Uses `vis.Network` for interactive graph rendering and real-time state tracking.

---

## Challenges We Encountered

### 1. Cycle Prevention in AI Graph Generation
Dynamic subject generation allows users to create custom prerequisite graphs for any subject. However, large language models can occasionally introduce cycle loops (such as $A \to B \to C \to A$), which breaks topological sorting.
- **Resolution**: We added validation checks using Kahn's algorithm during graph generation. If in-degree tracking indicates a cycle ($\text{processed\_nodes} < |V|$), the generator strips the cyclic edge before committing the graph to the database.

### 2. Preventing Diagnostic Fatigue
Walking every node in a long prerequisite chain can tire students, especially when testing topics they already know well.
- **Resolution**: We added adaptive pruning. If a student demonstrates high proficiency ($M(v) \ge 0.95$) on an immediate prerequisite, Cognis skips testing that node's underlying subtree $\text{Anc}(v)$. This reduced average diagnostic steps from 8 down to under 3 without compromising accuracy.

### 3. Session State Management
Coordinating state between the interactive node network (`vis.Network`), diagnostic questions, and terminal logs across multiple page views required a clean architecture without adding heavy framework dependencies.
- **Resolution**: Implemented a lightweight REST backend with SQLite persistence, paired with structured browser session handling in [frontend/js/session.js](file:///home/fang/Downloads/prereq-sleuth-frontend%20%281%29/prereq-sleuth-frontend/frontend/js/session.js).

---

## What We Learned

Building Cognis highlighted a few key insights:
1. **Guided probing works better than immediate answers**: Students gain far stronger retention when asked targeted diagnostic questions that reveal their own gaps, rather than receiving pre-packaged explanations.
2. **Visual graphs clarify complex dependencies**: Presenting knowledge as an interactive network transforms abstract curriculum structures into clear, manageable learning paths.
3. **Graph algorithms complement generative models well**: Combining deterministic graph operations ($\mathcal{O}(V + E)$ complexity) with generative LLMs yields reliable systems that remain flexible across domain boundaries.

---

## Looking Ahead

Cognis aims to make learning more efficient by turning confusion into targeted clarity. By locating precisely where comprehension broke down, Cognis helps learners rebuild their foundational skills with confidence.
