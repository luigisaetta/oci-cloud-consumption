# OCI Enterprise AI Deployment Constraints

## Document Metadata
- Version: 1.0
- Last modified: 2026-04-21
- Status: Active (normative)

## Scope
This document defines mandatory constraints required for deploying the system on OCI Enterprise AI.

These constraints are normative and must be followed by all services and agents.

## Service Requirements

### Health Endpoints
- Each service must expose the following additional endpoints:
  - `/health` → liveness probe
  - `/ready` → readiness probe

- Endpoints must:
  - return HTTP 200 when healthy
  - not depend on long-running checks

### API Requirements
- All agent APIs must be HTTP-based.

## Security Requirements
- Services must integrate with OCI IAM for authentication.
- No unauthenticated endpoints are allowed (except health checks if required by platform).

## Observability Integration
- Services must emit logs compatible with OCI logging.
- Tracing must be compatible with OCI-native and Langfuse.

## Compliance Rule
If a design choice conflicts with these constraints:
- the platform constraint takes precedence;
- the design must be adapted accordingly.