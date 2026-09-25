#!/usr/bin/env python3
"""
main.py - Single command runner for AI Lead Automation.

Usage:
  python main.py           -> Starts the interactive web dashboard & API at http://localhost:8000
  python main.py --test    -> Runs all unit & integration tests
  python main.py --eval    -> Runs the 10-lead ground-truth benchmark suite
  python main.py --val     -> Validates schemas and dataset integrity
"""

import sys
import os

if __name__ == "__main__":
    # Handle CLI flags
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower().lstrip("-")
        if cmd in ("t", "test"):
            import pytest
            sys.exit(pytest.main([]))
        elif cmd in ("e", "eval", "evaluation"):
            from scripts.run_evaluation import run_benchmarks
            stats = run_benchmarks()
            sys.exit(0 if stats["scoring_accuracy"] == 100 else 1)
        elif cmd in ("v", "val", "validate"):
            from scripts.validate_schemas import main as run_val
            run_val()
            sys.exit(0)

    # Default action: start web app and API
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print("\n=======================================================")
    print("🚀 AI Lead Automation Dashboard is starting...")
    print(f"👉 Web Dashboard:  http://localhost:{port}")
    print(f"👉 Swagger API:    http://localhost:{port}/docs")
    print("=======================================================\n")
    uvicorn.run("scripts.serve_api:app", host="127.0.0.1", port=port, reload=True)
