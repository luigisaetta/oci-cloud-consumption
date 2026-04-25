# Batch CLI Menu

Interactive command-line utility to run batch agents and save markdown reports.
The interface is built with `rich` for a more visual terminal experience.

## What it provides

- Text menu with user-friendly options:
  - `[1] Monthly report`
  - `[2] Range report`
  - `[3] Trend report (last 6 full months)`
- Guided prompts (wizard-style) for required inputs.
- Run preview table before execution.
- Confirmation prompt before launching the batch job.
- Post-run preview of saved markdown output.
- Markdown output saved locally or to OCI Object Storage.

## Run

From repository root:

```bash
python cli/batch_menu.py
```

If `rich` is missing:

```bash
pip install -r requirements.txt
```

## Menu flows

### 1) Monthly report

Prompts:
- target month (`YYYY-MM` or `MM-YYYY`)
- query type (`COST` or `USAGE`)
- top N rows
- OCI profile
- auth type (`AUTO`, `API_KEY`, `RESOURCE_PRINCIPAL`, or `NONE`)
- output destination (`local` or `object_storage`)
- local file path or Object Storage bucket/object name

Output:
- one markdown file with top compartments and top services for that month.

### 2) Range report

Prompts:
- start month (`YYYY-MM` or `MM-YYYY`)
- end month (`YYYY-MM` or `MM-YYYY`)
- query type (`COST` or `USAGE`)
- top N rows
- OCI profile
- auth type (`AUTO`, `API_KEY`, `RESOURCE_PRINCIPAL`, or `NONE`)
- output destination (`local` or `object_storage`)
- local file path or Object Storage bucket/object name

Output:
- one markdown file containing one monthly section per month in the selected range.

### 3) Trend report

Prompts:
- reference month (`YYYY-MM` or `MM-YYYY`), default: current month
- query type (`COST` or `USAGE`)
- top N rows
- OCI profile
- auth type (`AUTO`, `API_KEY`, `RESOURCE_PRINCIPAL`, or `NONE`)
- output destination (`local` or `object_storage`)
- local file path or Object Storage bucket/object name

Output:
- one markdown file with analysis on the 6 full months preceding the reference month:
  - top N compartments
  - top N services
  - trend classification and growth percentage (LLM-based, with deterministic fallback)

## Defaults

- Query type: `COST`
- Top N: `10`
- Profile: `DEFAULT`
- Output directory: `reports/`
- Object Storage bucket env var: `OCI_OBJECT_STORAGE_BUCKET_NAME`
- Object Storage prefix env var: `OCI_OBJECT_STORAGE_REPORT_PREFIX`
- Canonical output names:
  - Monthly: `monthly-report-YYYY-MM.md`
  - Range: `range-report-YYYY-MM_to_YYYY-MM.md`
  - Trend: `trend-report-last6-until-YYYY-MM.md`

## Notes

- Range is inclusive (start month and end month included).
- Output files are generated in markdown (`.md`) and can be versioned or shared.
- When Object Storage is selected, the bucket can be typed in the menu or loaded
  from `OCI_OBJECT_STORAGE_BUCKET_NAME`.
