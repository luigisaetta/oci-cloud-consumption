# Design.md

## Document Metadata
- Version: 1.1
- Last modified: 2026-04-21
- Status: Active (normative)

## Specification Status
This document defines the initial product and architecture specifications for `oci-cloud-consumption`.
These specifications are normative and must always be followed during design and implementation, unless explicitly revised in this file.

## Product Vision
The project is focused on building a set of AI agents that help OCI tenant administrators analyze, monitor, and keep cloud consumption under control.

## Scope and Users
- The solution is intended for OCI tenant administrators.
- Capabilities exposed by this project are administrative in purpose and are not intended for unrestricted tenant users.
- Access and features must be constrained according to the role and permissions model defined for tenant admins.

## Functional Capabilities
The platform provides two main operational modes:

1. Interactive assistant:
- An AI Assistant for querying and analyzing OCI consumption data.
- Support for exploratory analysis, trend interpretation, and cost/usage investigation.

2. Batch agents:
- A set of agents that run in batch mode to generate consumption reports.
- Continuous checks for policy compliance related to consumption and governance controls.
- Alert generation when anomalies, threshold violations, or policy breaches are detected.

## Data Access Architecture
- Consumption data is accessed through a Python API implemented in this repository.
- The API is built on top of the OCI Python SDK and acts as the canonical data access layer for agent workflows.

## Remote Access via MCP
- The same Python API is exposed to remote clients through an MCP server.
- The MCP server is the remote interface for controlled access to consumption analysis capabilities.

## Security Requirements
- MCP server authentication and authorization must be enforced using JWT tokens.
- JWT tokens are issued by OCI IAM.
- No unauthenticated access to consumption APIs or administrative agent operations is allowed.

## Non-Functional Requirements

### Reliability
- All OCI API calls must implement retry policies for transient failures.
- Retries must use exponential backoff.
- Retryable errors must include network errors and OCI service throttling responses.
- Operations must be idempotent where retries are applied.

### Observability

#### Logging
- Structured logging must be used across all components.
- Logs must include:
  - timestamp
  - component (agent, API, MCP)
  - operation name
  - success/failure status
  - error details (if applicable)

#### Tracing
- Distributed tracing must be supported.
- Tracing integration with Langfuse on OCI is planned and must be supported by design.

### Failure Handling
- Agent failures must be captured and logged.
- Batch executions must report status (success, partial, failed).
- Failures must not leave the system in an inconsistent state.

## Governance Rule for Conflicts
If a requested change conflicts with this specification:
- implementation must pause before applying the conflicting change;
- clarification and explicit direction must be requested from the project owner;
- any approved exception must be documented by updating this `Design.md`.
