"""FastAPI / Starlette REST API and UI Server.

Exposes endpoints for task lifecycle management, step-by-step execution,
HITL approval gates, real-time thought logging, and diff inspection.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from agent.llm_provider import get_llm_provider
from agent.orchestrator import AgentOrchestrator
from sandbox.executor import SandboxExecutor

logger = logging.getLogger("API.Server")

# Initialize global orchestrator
orchestrator = AgentOrchestrator()

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "ui" / "static"
TEMPLATES_DIR = BASE_DIR / "ui" / "templates"


# --- Service Handlers (Pure Python, Synchronous & Testable) ---


def handle_health() -> Dict[str, Any]:
    """Get system health metadata."""
    provider = orchestrator.llm.__class__.__name__
    fallback = orchestrator.fallback_status
    return {
        "status": "healthy",
        "system": "Upgraded Coding Agent (Authentic Intelligence & Self-Healing)",
        "active_llm_provider": provider,
        "primary_model": "gemini-1.5-flash",
        "fallback_status": fallback,
        "python_version": sys.version,
    }


def handle_create_task(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create a new autonomous coding task."""
    objective = data.get("objective", "").strip()
    if not objective:
        return 400, {"error": "Field 'objective' is required."}

    require_hitl = data.get("require_hitl", True)
    max_iterations = int(data.get("max_iterations", 4))
    target_file = data.get("target_file", "solution.py")
    test_file = data.get("test_file", "test_solution.py")

    state = orchestrator.create_task(
        objective=objective,
        require_hitl=require_hitl,
        max_iterations=max_iterations,
        target_file=target_file,
        test_file=test_file,
    )
    return 201, state.to_dict()


def handle_get_task(task_id: str) -> Tuple[int, Dict[str, Any]]:
    """Get task state by ID."""
    state = orchestrator.get_task(task_id)
    if not state:
        return 404, {"error": f"Task '{task_id}' not found."}
    return 200, state.to_dict()


def handle_step_task(task_id: str) -> Tuple[int, Dict[str, Any]]:
    """Step agent state forward."""
    try:
        state = orchestrator.step(task_id)
        return 200, state.to_dict()
    except KeyError:
        return 404, {"error": f"Task '{task_id}' not found."}
    except Exception as exc:
        logger.exception("Error stepping task")
        return 500, {"error": str(exc)}


def handle_auto_run_task(task_id: str) -> Tuple[int, Dict[str, Any]]:
    """Run agent until stop or HITL gate."""
    try:
        state = orchestrator.run_until_stop(task_id)
        return 200, state.to_dict()
    except KeyError:
        return 404, {"error": f"Task '{task_id}' not found."}
    except Exception as exc:
        logger.exception("Error running task")
        return 500, {"error": str(exc)}


def handle_approve_task(task_id: str, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Submit human decision at HITL gate."""
    action = body.get("action", "APPROVE")
    feedback = body.get("feedback")
    modified_code = body.get("modified_code")
    reviewer = body.get("reviewer", "human_operator")

    try:
        state = orchestrator.process_hitl_decision(
            task_id=task_id,
            action=action,
            feedback=feedback,
            modified_code=modified_code,
            reviewer=reviewer,
        )
        if action.upper() in ("APPROVE", "MODIFY"):
            state = orchestrator.run_until_stop(task_id)
        return 200, state.to_dict()
    except KeyError:
        return 404, {"error": f"Task '{task_id}' not found."}
    except Exception as exc:
        logger.exception("Error processing HITL approval")
        return 500, {"error": str(exc)}


def handle_get_diff(task_id: str) -> Tuple[int, str]:
    """Get unified diff for task patch."""
    state = orchestrator.get_task(task_id)
    if not state:
        return 404, f"Task '{task_id}' not found."
    diff = state.current_patch.diff_unified if state.current_patch else ""
    return 200, diff


def handle_get_logs(task_id: str) -> Tuple[int, Dict[str, Any]]:
    """Get thought logs and terminal output."""
    state = orchestrator.get_task(task_id)
    if not state:
        return 404, {"error": f"Task '{task_id}' not found."}
    return 200, {
        "thought_log": [t.to_dict() for t in state.thought_log],
        "stdout": state.execution_result.stdout if state.execution_result else "",
        "stderr": state.execution_result.stderr if state.execution_result else "",
    }


def handle_chat(data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Handle conversational copilot chat."""
    message = data.get("message", "").strip()
    if not message:
        return 400, {"error": "Field 'message' cannot be empty."}

    task_id = data.get("task_id")
    result = orchestrator.chat(message, task_id=task_id)
    return 200, result


# --- Starlette Async HTTP Routes ---


async def health(request: Request) -> JSONResponse:
    return JSONResponse(handle_health())


async def chat_endpoint(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    status_code, data = handle_chat(body)
    return JSONResponse(data, status_code=status_code)


async def create_task(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    status_code, data = handle_create_task(body)
    return JSONResponse(data, status_code=status_code)


async def get_task(request: Request) -> JSONResponse:
    task_id = request.path_params["task_id"]
    status_code, data = handle_get_task(task_id)
    return JSONResponse(data, status_code=status_code)


async def step_task(request: Request) -> JSONResponse:
    task_id = request.path_params["task_id"]
    status_code, data = handle_step_task(task_id)
    return JSONResponse(data, status_code=status_code)


async def auto_run_task(request: Request) -> JSONResponse:
    task_id = request.path_params["task_id"]
    status_code, data = handle_auto_run_task(task_id)
    return JSONResponse(data, status_code=status_code)


async def approve_task(request: Request) -> JSONResponse:
    task_id = request.path_params["task_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}
    status_code, data = handle_approve_task(task_id, body)
    return JSONResponse(data, status_code=status_code)


async def get_task_diff(request: Request) -> Response:
    task_id = request.path_params["task_id"]
    status_code, diff = handle_get_diff(task_id)
    if status_code != 200:
        return JSONResponse({"error": diff}, status_code=status_code)
    return PlainTextResponse(diff)


async def get_task_logs(request: Request) -> JSONResponse:
    task_id = request.path_params["task_id"]
    status_code, data = handle_get_logs(task_id)
    return JSONResponse(data, status_code=status_code)


async def index(request: Request) -> HTMLResponse:
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        return HTMLResponse(content)
    return HTMLResponse("<h1>Control Dashboard Template Missing</h1>", status_code=404)


# Route definitions
routes = [
    Route("/", endpoint=index, methods=["GET"]),
    Route("/api/health", endpoint=health, methods=["GET"]),
    Route("/api/chat", endpoint=chat_endpoint, methods=["POST"]),
    Route("/api/tasks", endpoint=create_task, methods=["POST"]),
    Route("/api/tasks/{task_id}", endpoint=get_task, methods=["GET"]),
    Route("/api/tasks/{task_id}/step", endpoint=step_task, methods=["POST"]),
    Route("/api/tasks/{task_id}/auto", endpoint=auto_run_task, methods=["POST"]),
    Route("/api/tasks/{task_id}/approve", endpoint=approve_task, methods=["POST"]),
    Route("/api/tasks/{task_id}/diff", endpoint=get_task_diff, methods=["GET"]),
    Route("/api/tasks/{task_id}/logs", endpoint=get_task_logs, methods=["GET"]),
]

if STATIC_DIR.exists():
    routes.append(Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"))

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(debug=True, routes=routes, middleware=middleware)


def get_app() -> Starlette:
    return app
