# Automation Scripts & Tooling

This directory will contain developer utilities, local testing scripts, schema validators, and evaluation runners.

---

## Planned Scripts

### 1. Schema Validator (`validate-schemas.js` / `.py`)
- **Status**: [Planned - Milestone 0.1]
- **Purpose**: Validates all JSON files in `schemas/`, `examples/`, `config/`, and `evaluation/datasets/` against their corresponding JSON Schemas to prevent schema regressions.

### 2. Mock Webhook Dispatcher (`send-test-lead.js` / `.py`)
- **Status**: [Planned - Milestone 0.1]
- **Purpose**: Sends sample leads from `evaluation/datasets/sample-leads.json` to the local or remote n8n webhook endpoint via HTTP POST, simulating live channel intake.

### 3. Evaluation Runner (`run-evaluation.js` / `.py`)
- **Status**: [Planned - Milestone 0.6]
- **Purpose**: Executes the benchmark evaluation test suite:
  1. Loads dataset leads.
  2. Submits them through the AI extraction and scoring pipeline.
  3. Compares actual results against ground-truth assertions in `evaluation/expected/`.
  4. Generates an automated markdown/HTML report in `evaluation/reports/`.
