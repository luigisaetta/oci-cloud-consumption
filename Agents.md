---
Author: L. Saetta
Last modified: 2026-04-21
License: MIT
Description: Operational rules and quality standards for AI agents contributing to oci-cloud-consumption.
---

# Agents.md

## Purpose
This file defines the roles of AI agents in the `oci-cloud-consumption` project, their operational responsibilities, and the minimum quality rules for contributing consistently.
The project specification baseline is defined in `Design.md` and is normative for all contributors.

## Project Context
`oci-cloud-consumption` contains code for an enhanced agent focused on analyzing OCI cloud consumption.

Main areas (to be kept aligned with repository evolution):
- core agent logic for consumption analysis
- integrations/adapters for OCI data sources
- tests and validation utilities
- project documentation and usage notes

## Agent Roles

### 1) Maintainer Agent
Responsible for:
- proposing and applying code changes
- keeping consistency with repository structure and conventions
- updating documentation when behavior changes

### 2) Review Agent
Responsible for:
- identifying bugs, regressions, risks, and edge cases
- checking minimum test coverage for changes
- reviewing impacts on configuration and compatibility

### 3) Docs Agent
Responsible for:
- updating `README.md` and supporting docs
- adding reproducible usage examples
- keeping prerequisites, environment variables, and commands aligned

## Operating Rules
- Always follow the current project specifications in `Design.md`.
- Prefer small, focused changes.
- Do not introduce dependencies without a clear reason.
- Avoid hardcoding secrets, OCIDs, tenancy identifiers, or keys.
- Keep scripts runnable from repository root when possible.
- Preserve backward compatibility unless explicitly requested otherwise.
- Update tests and docs whenever behavior changes.
- If a request conflicts with `Design.md`, stop and ask for clarification before implementing.

## Standard Workflow
1. Understand the task and identify impacted files.
2. Implement the minimum required change.
3. Update or add tests when behavior changes.
4. Run essential local checks (tests, lint, formatting) for impacted files.
5. Update documentation when needed.

## Quality Checklist (Definition of Done)
A change is considered ready when:
- relevant tests pass (full or targeted subset)
- lint/format checks pass for changed files
- code remains readable and consistent
- no obvious functional regressions are introduced
- documentation is updated if UX/config/commands changed

## Repository-Specific Conventions
- Keep implementation and tests aligned as the project grows.
- Prefer explicit configuration through environment variables.
- Add new modules with clear responsibility boundaries.

## Useful Commands
```bash
# Project setup (adjust based on stack)
# python -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt

# Tests (example)
# pytest -q

# Lint/format (example)
# ruff check .
# black .
```

## Security and Configuration
- Credentials must remain outside the repository (local `.env*` files).
- Configuration must support environment-variable overrides.
- Before running operations against OCI resources, verify target tenancy/compartment.

## Escalation
Require human review when:
- a change impacts OCI authentication/authorization
- production-facing endpoints or billing-related calculations are changed
- scripts for bulk update/delete operations are introduced

## Template for New Tasks
Use this format in tickets/prompts:
- Goal:
- Files involved:
- Constraints:
- Acceptance criteria:
- Required tests:
- Rollout notes:

## Mandatory Reference
- Project specification: [Design.md](/Users/lsaetta/Progetti/oci-cloud-consumption/Design.md)
