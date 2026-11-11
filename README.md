# Upgraded Coding Agent: Authentic Intelligence & Self-Healing

[![Tests: 31 Passed](https://img.shields.io/badge/pytest-31%20passed-emerald?style=flat-square)](tests)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-purple?style=flat-square)](LICENSE)
[![Architecture: Authentic Intelligence](https://img.shields.io/badge/architecture-Authentic%20Intelligence%20v2.5-indigo?style=flat-square)](PROJECT_REPORT.md)

> **Academic Course Project:** *Foundations of AI and Authentic Intelligence*  
> **Topic:** *Upgrading the Coding Agent: From Autocomplete to Autonomous Self-Healing & Authentic Intelligence*

---

## 🚀 Key Highlights & Architectural Concept

The **Upgraded Coding Agent** moves beyond passive autocomplete assistants (Copilot, TabNine) and unverified chat tools into a fully autonomous, transparent, self-debugging software engineering agent.

```
       [Objective Spec]
              │
              ▼
   ┌──────────────────────┐
   │ Task Decomposition   │ (Recursive planning into verifiable subtasks)
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ Code Synthesis       │ (Initial synthesis & test generation via Gemini 1.5 Flash)
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ AST Security Audit   │ (Static AST inspection: blocks subprocess, eval, syscalls)
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ Authentic HITL Gate  │ (Interactive Diff inspection & Human approval gate)
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ Sandboxed Pytest     │ (Isolated subprocess jail running pytest & Flake8)
   └──────────┬───────────┘
              │
         Tests Pass?
         ├─── YES ───► [COMPLETED: Verified Code & Clean Diff]
         └─── NO  ───► ┌──────────────────────┐
                       │ Self-Healing Reflect │ (Formulate root-cause & assumptions)
                       └──────────┬───────────┘
                                  │ (Re-enter loop up to Max Retries)
                                  └──────────► [Code Synthesis]
```

### 1. Autonomous Task Decomposition
Breaks high-level specifications or bug descriptions into structured, ordered subtasks with clear architectural rationale and deterministic verification criteria.

### 2. AST Static Security Guardrail
Inspects code prior to disk writes and execution via Python's Abstract Syntax Tree (`ast`). Automatically blocks forbidden imports (`subprocess`, `socket`, `ctypes`), dynamic execution (`eval()`, `exec()`, `compile()`), and hazardous syscalls (`os.system()`).

### 3. Isolated Sandboxed Execution Loop
Runs synthesized implementations and pytest suites in isolated, ephemeral directory jails with strict timeout enforcement (15.0s default) to prevent infinite loops, deadlocks, and memory exhaustion.

### 4. Diagnostic Self-Healing Reflection Engine
Captures compiler errors, Flake8 style violations, and Pytest assertion tracebacks. Synthesizes a structured `ReflectionRecord` identifying the root cause, flawed assumptions, and exact corrective actions to guide the next code synthesis iteration.

### 5. Interactive Agent Copilot Chat
Enables bidirectional, natural language dialogue with the coding agent. Users can query *"Explain this bug"*, *"How does the self-healing loop work?"*, or *"Refactor this function to be faster"*. Responses feature GitHub-flavored Markdown, syntax-highlighted code blocks, and an expandable **"🧠 Internal Cognitive Reasoning"** dropdown explaining the underlying computer science deduction.

### 6. Resilient LLM Failover & Fallback Mechanism
Primary generation routes to Google's **Gemini 1.5 Flash**. If upstream services encounter high demand (503), rate limiting (429), or network timeouts, the system intercepts the exception gracefully and fails over to the deterministic **Offline Simulation Engine** with a prominent status banner, preventing 500 Internal Server Errors.

### 7. Authentic Intelligence & Human-in-the-Loop (HITL) Gate
Maintains strict human agency and explainability:
- **Side-by-Side Unified Diff Viewer:** Color-coded additions (green) and deletions (red).
- **Interactive Review Gate:** Explicit human controls to **Approve**, **Manually Edit & Approve**, **Request Re-Plan**, or **Reject with Feedback**.
- **Real-Time Cognitive Trace:** Streams step-by-step reasoning logs rather than opaque black-box spinners.

---

## 📂 Repository Directory Layout

```
upgraded-coding-agent/
├── agent/                  # Core Agent Subsystem
│   ├── models.py           # Pydantic/dataclass domain schemas (State, Plan, Patch, Reflection)
│   ├── llm_provider.py     # Unified LLM client (Gemini, OpenAI, Offline Simulation Engine)
│   ├── planner.py          # Autonomous task decomposition engine
│   ├── coder.py            # Code synthesis, patch generation, test creation
│   ├── reflector.py        # Diagnostic self-healing reflection engine
│   └── orchestrator.py     # Finite State Machine & HITL gate controller
├── sandbox/                # Execution & Security Subsystem
│   ├── ast_security.py     # AST-based static analyzer for dangerous syscalls/imports
│   ├── executor.py         # Subprocess runner with timeout, memory limit, clean jail
│   ├── linter.py           # Flake8 style and syntax checker (Windows path compatible)
│   └── test_runner.py      # Automated isolated pytest runner with structured reports
├── api/                    # REST API & Web UI Service
│   └── server.py           # Starlette/FastAPI REST endpoints & static UI server
├── ui/                     # Interactive Control Dashboard
│   ├── static/             # Static web assets (app.js, style.css, diff.js)
│   ├── templates/          # HTML5 templates (Tailwind CSS Single-Page Application)
│   └── streamlit_app.py    # Alternative Streamlit control interface
├── eval/                   # Academic Evaluation Suite
│   ├── benchmark_runner.py # Quantitative benchmark harness (Pass@1 vs. Pass@K)
│   └── scenarios.py        # Curated academic benchmark scenarios
├── tests/                  # Automated Test Suite (21 Unit & Integration Tests)
│   ├── test_ast_security.py
│   ├── test_sandbox_executor.py
│   ├── test_linter.py
│   ├── test_test_runner.py
│   ├── test_planner.py
│   ├── test_reflector.py
│   ├── test_orchestrator.py
│   └── test_api.py
├── run.py                  # Single-command CLI application launcher
├── Dockerfile              # Multi-stage container definition
├── docker-compose.yml      # Container orchestration
├── requirements.txt        # Pinned production dependencies
├── pyproject.toml          # Modern packaging configuration
├── pytest.ini              # Pytest configuration
├── .env.example            # Environment variables template
├── PROJECT_REPORT.md       # Comprehensive academic project report
└── README.md               # User & developer documentation
```

---

## ⚡ Quickstart: Local Execution

### 1. Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14.
- Git.

### 2. Setup Virtual Environment
```bash
# Clone or navigate to the repository
cd upgraded-coding-agent

# Create isolated virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Windows (MSYS2 / Git Bash):
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. (Optional) Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure your keys if you wish to use live LLMs:
- `GEMINI_API_KEY`: Google Gemini API key (defaults to `gemini-2.5-flash`).
- `OPENAI_API_KEY`: OpenAI API key (defaults to `gpt-4o-mini`).
- **No API key?** Leave blank! The system automatically activates the **Offline Simulation Engine** for deterministic demonstration, testing, and grading.

### 5. Launch the Application
Run the one-command launcher:
```bash
python run.py
```
Open your browser at **http://localhost:8000/** to access the interactive dashboard.

---

## 🧪 Verification & Benchmarks

### Run Complete Unit & Integration Test Suite
Execute the 21 test cases covering AST security, sandbox isolation, flake8 linting, pytest parsing, task planning, reflection, orchestrator state machine, and REST endpoints:
```bash
python -m pytest tests/ -v
# Output: 21 passed in ~10s
```

### Run Academic Evaluation Benchmark
Run the comparative evaluation comparing Zero-Shot baseline to the Upgraded Self-Healing Agent:
```bash
python eval/benchmark_runner.py
```
**Results Summary:**
```json
{
  "summary": {
    "total_benchmark_cases": 3,
    "zero_shot_pass_rate": "0.0%",
    "self_healing_pass_rate": "100.0%",
    "recovery_gain": "100.0%"
  }
}
```

---

## 🐳 Container Deployment (Docker & Compose)

Deploy the entire stack with a single command:
```bash
docker compose up --build
```
This launches:
- **Web Dashboard & REST API:** http://localhost:8000/
- **Streamlit Control Interface:** http://localhost:8501/

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/health` | `GET` | Health check, active LLM provider, failover status, Python version. |
| `/api/chat` | `POST` | Agent Copilot chat: `{"message": "Explain this bug", "task_id": "..."}`. |
| `/api/tasks` | `POST` | Initialize task: `{"objective": "...", "require_hitl": true, "max_iterations": 4}`. |
| `/api/tasks/{id}` | `GET` | Fetch task state, plans, current code, diffs, reflections. |
| `/api/tasks/{id}/step` | `POST` | Advance agent by exactly one discrete state machine transition. |
| `/api/tasks/{id}/auto` | `POST` | Run autonomously until stop or HITL Review Gate. |
| `/api/tasks/{id}/approve` | `POST` | Submit HITL decision: `{"action": "APPROVE"\|"MODIFY"\|"REPLAN"\|"REJECT"}`. |
| `/api/tasks/{id}/diff` | `GET` | Retrieve unified git diff text for proposed patch. |
| `/api/tasks/{id}/logs` | `GET` | Stream thought logs and subprocess stdout/stderr. |

---

## 📖 Academic Documentation

For theoretical foundations (ReAct, Reflexion, mathematical convergence proofs), authentic intelligence vs. black-box automation analysis, system flowcharts, and evaluation metrics, see **[PROJECT_REPORT.md](PROJECT_REPORT.md)**.
