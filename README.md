# 🚀 AlgoLens

<p align="center">
  <img src="https://img.shields.io/badge/status-active-success.svg" />
  <img src="https://img.shields.io/badge/python-3.11-blue.svg" />
  <img src="https://img.shields.io/badge/frontend-next.js-black.svg" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg" />
</p>

<p align="center">
  <b>Visualize code. Understand execution. See how algorithms actually run.</b>
</p>

---

## ⚡ What is AlgoLens?

AlgoLens is an **execution-level visualization engine** for Python programs.

It doesn't just show outputs — it shows **how your code behaves step by step**.

You can:

- Watch execution in real time
- Inspect variables at each step
- Visualize data structures dynamically
- Understand algorithm behavior visually

---

<p align="center">
<img width="1900" height="967" alt="image" src="https://github.com/user-attachments/assets/606c3c89-d11f-448f-8fef-4ec8e90e0cf6" />
</p>

---

## 🎥 Demo

- Heap insertion animation
- BST construction
- Stack vs Queue behavior
- Execution timeline navigation
  
---

<p align="center">
<img width="1896" height="970" alt="AlgoLens Capture" src="https://github.com/user-attachments/assets/d7037c0e-4a2e-463f-9f13-1ea5a1090e96" />
</p>

---

## ✨ Features

### ⚙️ Execution Engine
- Line-by-line execution tracing
- Frame-based program recording
- Runtime variable inspection

### 🧬 Semantic Understanding
AlgoLens detects *what your code is doing*, not just what it says.

| Code Behavior | Interpreted As |
|--------------|---------------|
| append + pop | Stack |
| append + pop(0) | Queue |
| heapq usage | Heap |

---

### 📊 Supported Structures
- Arrays
- Stacks
- Queues
- Deques
- Linked Lists (SLL / DLL / CLL)
- Binary Search Trees
- Binary Heaps

---

### ⏱ Execution Timeline
- Step forward / backward
- Frame scrubbing
- State replay
- Variable inspection per frame

---

## 🏗 Architecture

```
Python Code
     │
     ▼
Execution Tracer (sys.settrace)
     │
     ▼
Frame Engine (state diffing)
     │
     ▼
Semantic Analyzer (behavior detection)
     │
     ▼
Visualization Layer (GraphTreeRenderer)
     │
     ▼
Frontend (Next.js + React)
```

---

## 🚀 Getting Started

### Requirements
- Python 3.11+
- Node.js 18+
- npm

---

### Clone

```bash
git clone https://github.com/MadhavKathuria826/AlgoLens.git
cd AlgoLens
```

---

## 🧩 Backend

```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload
```

Backend runs at:
```
http://127.0.0.1:8000
```

---

## 🎨 Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend runs at:
```
http://localhost:3000
```

---

## 🧱 Project Structure

```
backend/
frontend/
PROJECT_STATE.md
LICENSE
README.md
```

(Full structure simplified for clarity)

---

## 🛣 Roadmap

### v1.0
- Execution tracing
- Stack / Queue / Heap visualization
- Linked lists
- BSTs

### v1.1
- `collections.deque`
- Better semantic detection
- Hardcoded structure recognition
- Import system generalization

### v2.0
- AVL trees
- Red-black trees
- Tries
- Graphs
- Multi-language support

---

## 💡 Why AlgoLens?

Traditional visualizers show **fixed examples**.

AlgoLens shows **your program executing in real time**.

This makes debugging, learning, and teaching fundamentally more intuitive.

---

## 🤝 Contributing

Pull requests are welcome.

1. Fork repo
2. Create feature branch
3. Commit changes
4. Open PR

---

## 📜 License

MIT License © 2026 Madhav Kathuria
