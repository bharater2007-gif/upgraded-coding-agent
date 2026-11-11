"""Unified Application Entry Point.

Starts the Uvicorn web server hosting both the REST API and the interactive UI dashboard,
or runs test suites and evaluation benchmarks from the command line.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure root directory is on PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def main():
    parser = argparse.ArgumentParser(
        description="Upgraded Coding Agent: Authentic Intelligence & Self-Healing"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--provider", choices=["gemini", "openai", "offline"], default=None, help="Force LLM Provider")
    parser.add_argument("--benchmark", action="store_true", help="Execute evaluation benchmark suite and exit")
    parser.add_argument("--test", action="store_true", help="Execute pytest test suite and exit")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn hot reloading")

    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    if args.test:
        import pytest
        sys.exit(pytest.main(["tests", "-v"]))

    if args.benchmark:
        from eval.benchmark_runner import evaluate_system
        evaluate_system()
        return

    banner = rf"""
========================================================================
    UPGRADED CODING AGENT: AUTHENTIC INTELLIGENCE & SELF-HEALING
    Course: Foundations of AI and Authentic Intelligence
========================================================================
  [+] Web Dashboard : http://{args.host}:{args.port}/
  [+] REST API Docs : http://{args.host}:{args.port}/api/health
  [+] Active Model  : {os.getenv('LLM_PROVIDER', 'Auto (Gemini/OpenAI/Offline)')}
  [+] HITL Gate     : Interactive Web Dashboard & Diff Inspector
========================================================================
"""
    print(banner)

    import uvicorn
    uvicorn.run("api.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
