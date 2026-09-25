#!/usr/bin/env python3
"""
send_test_lead.py
Mock Webhook Dispatcher for AI Lead Automation.
Dispatches canonical or raw channel test leads to the n8n webhook intake endpoint
to test live end-to-end workflow execution.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT_DIR / "evaluation" / "datasets" / "sample-leads.json"
RAW_EXAMPLE_PATH = ROOT_DIR / "examples" / "incoming-lead.json"
DEFAULT_URL = os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/leads/incoming")


def send_payload(url: str, payload: dict):
    print(f"[*] Dispatching test lead to: {url}")
    print(f"[*] Payload Lead ID: {payload.get('lead_id') or payload.get('submission_id')}")

    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        print(f"[*] Response Status Code: {response.status_code}")
        try:
            print("[*] Response JSON:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except Exception:
            print(f"[*] Response Body: {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"\n[!] Connection Error: Unable to reach {url}.")
        print("    If testing against local n8n, ensure n8n is running:")
        print("    npx n8n or docker run -p 5678:5678 n8nio/n8n")
    except Exception as e:
        print(f"\n[!] Request failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Dispatch test leads to n8n intake webhook")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Target webhook URL (default: {DEFAULT_URL})")
    parser.add_argument("--lead-id", default="lead_eval_001", help="Sample lead ID from evaluation dataset (default: lead_eval_001)")
    parser.add_argument("--raw", action="store_true", help="Send raw unnormalized website form submission (examples/incoming-lead.json)")

    args = parser.parse_args()

    if args.raw:
        with open(RAW_EXAMPLE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        with open(DATASET_PATH, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        matches = [l for l in dataset if l.get("lead_id") == args.lead_id]
        if not matches:
            print(f"[!] Error: Lead ID '{args.lead_id}' not found in {DATASET_PATH.relative_to(ROOT_DIR)}")
            sys.exit(1)
        payload = matches[0]

    send_payload(args.url, payload)


if __name__ == "__main__":
    main()
