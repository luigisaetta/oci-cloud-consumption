# Consumption Utils Public API

This document describes the **public functions** exposed by `utils/consumption_utils.py`.
It is intended for developers integrating these functions from MCP servers, automation jobs, and AI agents.

## Scope
The module exposes 4 public functions:
- `usage_summary_by_service_structured`
- `usage_summary_by_compartment_structured`
- `fetch_consumption_by_compartment`
- `usage_summary_by_service_for_compartment`

## Dependency Rule (Public-to-Public)
A key design note: **none of these public functions directly depends on another public function in the same file**.
Each function is independent at the public API level and relies on private helpers plus `utils/oci_utils.py` utilities.

---

## 1) `usage_summary_by_service_structured`

### What It Does
Returns a tenant-wide aggregated summary of OCI consumption grouped by **service** for a given date range.

### Inputs
- `start_day`: inclusive start date (`YYYY-MM-DD`, `date`, or `datetime`)
- `end_day_inclusive`: inclusive end date (`YYYY-MM-DD`, `date`, or `datetime`)
- `query_type`: `"COST"` or `"USAGE"` (default: `"COST"`)

### Output Shape (high level)
- `period`: normalized start/end window (`end_exclusive`)
- `group_by`: `["service"]`
- `items`: one row per service with `amount` and `quantity`
- `totals`: global totals for amount/quantity
- `metadata`: region and optional `opc_request_id`

### Public Dependencies in `consumption_utils.py`
- **Depends on other public function in this file:** `No`

### Other Internal/External Dependencies
- Internal helpers: `_normalize_query_type`, `_window_start_end_exclusive`, `_build_usage_summary_output`
- External utility: `make_oci_client` from `utils/oci_utils.py`
- OCI SDK: `RequestSummarizedUsagesDetails`, Usage API client call

---

## 2) `usage_summary_by_compartment_structured`

### What It Does
Returns a tenant-wide aggregated summary of OCI consumption grouped by **compartment name** for a given date range.

### Inputs
- `start_day`: inclusive start date
- `end_day_inclusive`: inclusive end date
- `query_type`: `"COST"` or `"USAGE"` (default: `"COST"`)

### Output Shape (high level)
- `period`
- `group_by`: `["compartmentName"]`
- `items`: one row per compartment
- `totals`
- `metadata`

### Public Dependencies in `consumption_utils.py`
- **Depends on other public function in this file:** `No`

### Other Internal/External Dependencies
- Internal helpers: `_normalize_query_type`, `_window_start_end_exclusive`, `_build_usage_summary_output`
- External utility: `make_oci_client`
- OCI SDK summarized usage API

---

## 3) `fetch_consumption_by_compartment`

### What It Does
Returns compartment-level rows filtered by a target service, with robust fallback strategy:
1. discover available services in selected time window;
2. try server-side filtering if service resolution is unique;
3. fallback to client-side filtering;
4. fallback to alternate query type (`COST` <-> `USAGE`) when needed.

### Inputs
- `day_start`: inclusive start date
- `day_end`: inclusive end date
- `service`: requested service string (exact or partial)
- `query_type`: preferred `"COST"`/`"USAGE"`
- `include_subcompartments`: whether subtree is included
- `max_compartment_depth`: max depth (1..7)
- `config_profile`: OCI config profile (default `"DEFAULT"`; `None` for RP auth)
- `debug`: include diagnostics when `True`

### Output Shape (high level)
Always:
- `rows`: filtered rows with compartment and service data

When `debug=True`, also includes:
- `resolved_service`, `service_candidates`
- `query_used`, `filtered_server_side`
- `depth`, `time_window`, `input`

### Public Dependencies in `consumption_utils.py`
- **Depends on other public function in this file:** `No`

### Other Internal/External Dependencies
- Internal helpers: `_normalize_query_type`, `_window_start_end_exclusive`, `_effective_depth`, `_discover_services_union`, `_grouped_query`, `_transform_grouped_rows`, `_filter_rows_by_service`, `_build_debug_payload`
- External utilities: `make_oci_client`, `resolve_service`
- OCI SDK filters and summarized usage API

### Error Conditions
- `ValueError` for invalid service or invalid `max_compartment_depth`
- `RuntimeError` when tenancy cannot be resolved from auth context

---

## 4) `usage_summary_by_service_for_compartment`

### What It Does
Returns an aggregated service-level summary **within a specific compartment scope** (by OCID or exact compartment name) over a date range.

### Inputs
- `start_day`: inclusive start date
- `end_day_inclusive`: inclusive end date
- `compartment`: compartment OCID or exact compartment name
- `query_type`: `"COST"` or `"USAGE"`
- `include_subcompartments`: include subtree
- `max_compartment_depth`: max depth (1..7)
- `config_profile`: OCI profile or `None` for RP auth

### Output Shape (high level)
- `period`
- `scope`: compartment input, resolved compartment OCID, depth settings
- `group_by`: `["service"]`
- `items`: service rows including share percentage
- `totals`
- `metadata`

### Public Dependencies in `consumption_utils.py`
- **Depends on other public function in this file:** `No`

### Other Internal/External Dependencies
- Internal helpers: `_normalize_query_type`, `_window_start_end_exclusive`, `_effective_depth`, `_round_or_none`
- External utilities: `make_oci_client`, `make_identity_client`, `resolve_compartment_id`, `extract_group_value`, `get_opc_request_id`
- OCI SDK summarized usage API

### Error Conditions
- `ValueError` for invalid input (depth/compartment) or unresolved compartment
- `RuntimeError` when tenancy cannot be resolved

---

## Integration Notes
- Public APIs are designed to be called independently.
- Date normalization always uses inclusive start + exclusive end semantics when querying OCI.
- Authentication behavior depends on `make_oci_client` in `utils/oci_utils.py`.
- For external consumers (MCP/agents), `debug=True` in `fetch_consumption_by_compartment` is useful for troubleshooting resolution and fallback paths.
