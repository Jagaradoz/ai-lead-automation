#!/usr/bin/env python3
"""
validate_schemas.py
Validates JSON Schemas, examples, sample datasets, and configuration files
for the AI Lead Automation project.
"""

import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from jsonschema import Draft7Validator

ROOT_DIR = Path(__file__).resolve().parent.parent

SCHEMAS = {
    "lead": ROOT_DIR / "schemas" / "lead.schema.json",
    "lead_analysis": ROOT_DIR / "schemas" / "lead-analysis.schema.json",
    "lead_score": ROOT_DIR / "schemas" / "lead-score.schema.json",
}

# Only canonical data contracts are validated against schemas
CANONICAL_TARGETS = [
    ("examples/normalized-lead.json", "lead", False),
    ("examples/ai-analysis.json", "lead_analysis", False),
    ("examples/scored-lead.json", "lead_score", False),
    ("evaluation/datasets/sample-leads.json", "lead", True),  # True = list of items
]


def load_json(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    errors = []
    print("==================================================================")
    print("[*] AI Lead Automation - Schema & Data Integrity Validator")
    print("==================================================================")

    # 1. Validate JSON Schemas themselves
    validators = {}
    print("\n[1/3] Validating JSON Schema definitions (Draft-07)...")
    for name, schema_path in SCHEMAS.items():
        if not schema_path.exists():
            errors.append(f"Missing schema file: {schema_path}")
            continue
        try:
            schema_data = load_json(schema_path)
            Draft7Validator.check_schema(schema_data)
            validators[name] = Draft7Validator(schema_data)
            print(f"  [PASS] {schema_path.relative_to(ROOT_DIR)} is valid Draft-07")
        except Exception as e:
            err = f"  [FAIL] {schema_path.relative_to(ROOT_DIR)} invalid schema: {e}"
            print(err)
            errors.append(err)

    if errors:
        print(f"\n[FAIL] Aborting due to schema errors ({len(errors)})")
        sys.exit(1)

    # 2. Validate Configuration Files
    print("\n[2/3] Validating configuration files...")
    scoring_config_path = ROOT_DIR / "config" / "scoring.example.json"
    if scoring_config_path.exists():
        try:
            cfg = load_json(scoring_config_path)
            assert "priority_thresholds" in cfg, "Missing priority_thresholds"
            assert "dimensions" in cfg, "Missing dimensions"
            assert "human_review_triggers" in cfg, "Missing human_review_triggers"
            print(f"  [PASS] {scoring_config_path.relative_to(ROOT_DIR)} structure valid")
        except Exception as e:
            err = f"  [FAIL] {scoring_config_path.relative_to(ROOT_DIR)} config error: {e}"
            print(err)
            errors.append(err)

    # 3. Validate Example & Evaluation Datasets
    print("\n[3/3] Validating canonical payload instances against schemas...")
    for rel_path, schema_name, is_list in CANONICAL_TARGETS:
        file_path = ROOT_DIR / rel_path
        if not file_path.exists():
            errors.append(f"File not found: {rel_path}")
            continue

        try:
            data = load_json(file_path)
            validator = validators[schema_name]

            if is_list:
                for idx, item in enumerate(data):
                    val_errors = list(validator.iter_errors(item))
                    if val_errors:
                        for err in val_errors:
                            errors.append(f"  [FAIL] {rel_path} item #{idx} ({item.get('lead_id', 'unknown')}): {err.message}")
                    else:
                        lead_id = item.get("lead_id", f"item_{idx}")
                        print(f"  [PASS] {rel_path} -> {lead_id} complies with '{schema_name}'")
            else:
                val_errors = list(validator.iter_errors(data))
                if val_errors:
                    for err in val_errors:
                        errors.append(f"  [FAIL] {rel_path}: {err.message}")
                else:
                    print(f"  [PASS] {rel_path} complies with '{schema_name}'")

        except Exception as e:
            errors.append(f"Failed to read/validate {rel_path}: {e}")

    print("\n==================================================================")
    if errors:
        print(f"[FAIL] Validation FAILED with {len(errors)} error(s):")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("[SUCCESS] ALL schemas, examples, datasets, and configs are 100% VALID!")
        print("==================================================================")
        sys.exit(0)


if __name__ == "__main__":
    main()
