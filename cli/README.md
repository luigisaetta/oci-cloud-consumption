# Batch CLI Menu

Interactive command-line utility to run batch agents and save markdown reports.

## What it provides

- Text menu with user-friendly options:
  - `[1] Monthly report`
  - `[2] Range report`
- Guided prompts for required inputs.
- Automatic markdown output saved to file.

## Run

From repository root:

```bash
python cli/batch_menu.py
```

## Menu flows

### 1) Monthly report

Prompts:
- target month (`YYYY-MM` or `MM-YYYY`)
- query type (`COST` or `USAGE`)
- top N rows
- OCI profile
- auth type (optional)
- output file path

Output:
- one markdown file with top compartments and top services for that month.

### 2) Range report

Prompts:
- start month (`YYYY-MM` or `MM-YYYY`)
- end month (`YYYY-MM` or `MM-YYYY`)
- query type (`COST` or `USAGE`)
- top N rows
- OCI profile
- auth type (optional)
- output file path

Output:
- one markdown file containing one monthly section per month in the selected range.

## Defaults

- Query type: `COST`
- Top N: `10`
- Profile: `DEFAULT`
- Output directory: `reports/`

## Notes

- Range is inclusive (start month and end month included).
- Output files are generated in markdown (`.md`) and can be versioned or shared.
