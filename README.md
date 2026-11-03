# AI-Assisted Sales Data Pipeline

A supervised, AI-assisted analytics workflow built with Python, Gemini,
LangGraph, DuckDB, dbt, and Tableau Public.

The project cleans sales CSVs, validates their records, builds tested
reporting models, and publishes a CSV for Tableau. An optional
question-answering agent translates supported questions into approved
parameters for fixed, read-only SQL.

## Architecture

```text
Raw sales CSV
    |
    v
Python cleaning and Pydantic validation
    |
    v
Verified clean CSV
    |
    v
DuckDB raw_sales table
    |
    v
dbt staging and monthly reporting models
    |
    v
Data-quality tests and monthly reconciliation
    |
    v
Published monthly_metrics.csv
    |
    v
Tableau Public Desktop
```

Optional AI header review:

```text
Unfamiliar headers
    -> Permission to send headers
    -> Gemini mapping proposal
    -> Human approval
    -> Local cleaning, validation, and export
```

Question answering:

```text
Plain-English question
    -> Permission to send question
    -> Gemini query plan
    -> Local plan validation
    -> Human approval
    -> Fixed, read-only SQL
    -> Reconciliation against Tableau-ready CSV
    -> Verified answer
```

## Main capabilities

- Clean known formatting problems using deterministic Python rules.
- Validate every record against a Pydantic data contract.
- Request AI header mappings without sending CSV row values.
- Require human approval before applying proposed mappings.
- Export cleaned CSVs using temporary files and verification.
- Load validated records into a local DuckDB warehouse.
- Build staging and monthly reporting models with dbt.
- Test required fields, accepted regions, reporting grain, and totals.
- Publish monthly reporting data only after dbt succeeds.
- Answer supported regional-revenue questions using fixed SQL.
- Compare query results against the local CSV used by Tableau.
- Record workflow outcomes in local JSON run reports.

## Technology stack

| Component | Purpose |
|---|---|
| Python 3.12 | Application and workflow tools |
| pandas | CSV ingestion |
| Pydantic | Record and query-plan validation |
| LangGraph | Workflow orchestration |
| Gemini API | Header-mapping and query-plan proposals |
| DuckDB | Local analytical database |
| dbt Core and dbt-duckdb | SQL models and data-quality tests |
| pytest | Automated Python tests |
| Tableau Public Desktop | Reporting visualization |

## Project structure

```text
agent_swarm/
|-- agents/               Workflow nodes and question agent
|-- graphs/               LangGraph workflow definitions
|-- tools/                Cleaning, exports, SQL, retries, and reporting
|-- dbt_project/
|   |-- models/           Sources, staging, and reporting models
|   |-- tests/            Custom SQL data tests
|   |-- dbt_project.yml
|   `-- profiles.yml
|-- tests/                Automated Python tests
|-- examples/             Invented sample CSVs
|-- data/                 Local database, outputs, and run reports
|-- cli.py                Pipeline command-line interface
|-- contracts.py          Sales-record validation rules
|-- state.py              Shared workflow state
|-- requirements.txt
|-- .env                  Local credentials; never commit
|-- .gitignore
`-- README.md
```

## Requirements

- Windows with PowerShell.
- Python 3.12.
- Git installed and available on PATH.
- Packages listed in requirements.txt.
- Tableau Public Desktop or Tableau Desktop for visualization.
- A Gemini API key only for optional AI features.

## Environment setup

For a new installation, run these commands from the project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

Check the installed dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

Commands use the virtual environment's Python directly. Activation is
not required.

Git must be discoverable from PowerShell:

```powershell
git --version
```

## Optional Gemini configuration

Create a local .env file in the project root containing:

```text
GEMINI_API_KEY=PASTE_YOUR_KEY_HERE
GEMINI_MODEL=models/gemini-flash-lite-latest
```

Replace the placeholder with your own key. The model setting is
configurable; model availability can change.

Never paste credentials into Python source files, screenshots, or public
repositories.

The ordinary ingestion and dbt workflow does not require Gemini.

AI requests may consume billable quota. Temporary API statuses 503 and
504 are retried up to three total attempts, with increasing delays.

## Sales data contract

Every cleaned record must contain these fields:

| Field | Rule |
|---|---|
| date | Valid date; cleaned CSV uses YYYY-MM-DD |
| region | North, South, East, West, or Central |
| product_category | Non-empty text |
| revenue | Finite number, zero or greater |
| units_sold | Integer, zero or greater |
| customer_segment | Non-empty text |

Missing and unexpected fields are rejected.

The cleaner handles approved header aliases, known region abbreviations,
year-first date formats, whitespace, and supported US-dollar formatting.

It does not guess ambiguous dates, invent missing values, round
fractional units, or change negative revenue into positive revenue.

Negative revenue is disallowed by this demo's contract. Refund datasets
would require an explicit change to that business rule.

## Pipeline commands

Run all commands from the agent_swarm project folder.

### Clean, validate, and export a CSV

```powershell
.\.venv\Scripts\python.exe -m cli ingest ".\examples\messy_sales.csv"
```

This runs offline and publishes sales_clean.csv.

### Also load DuckDB

```powershell
.\.venv\Scripts\python.exe -m cli ingest ".\examples\messy_sales.csv" --load-warehouse
```

This replaces raw_sales with the validated input snapshot.

### Build the complete reporting pipeline

```powershell
.\.venv\Scripts\python.exe -m cli ingest ".\examples\messy_sales.csv" --build-mart
```

This command:

1. Cleans and validates the input.
2. Exports and verifies the cleaned CSV.
3. Loads raw_sales.
4. Builds the dbt staging and reporting models.
5. Runs the dbt data tests.
6. Publishes monthly_metrics.csv after dbt succeeds.
7. Records the overall workflow outcome.

The --build-mart option includes warehouse loading. There is no need
to supply --load-warehouse as well.

### Request AI header review

```powershell
.\.venv\Scripts\python.exe -m cli ingest ".\examples\unfamiliar_headers.csv" --review-headers --build-mart
```

The tool asks for:

- SEND: permission to request an AI mapping proposal.
- APPROVE: approval to apply the displayed header mappings.

Any other response cancels the relevant step.

Only column headers and mapping instructions are sent to Gemini.
CSV row values remain local. Proposed header mappings must pass
structural checks, but human review is still needed to confirm meaning.

### Display command help

```powershell
.\.venv\Scripts\python.exe -m cli ingest --help
```

## Warehouse and reporting models

### raw_sales

The validated input snapshot loaded by Python.

Each successful load replaces this table. Loads do not append history
or deduplicate repeated records within the input.

### stg_sales

A dbt view that preserves the input records and renames date to
sale_date. It does not aggregate records.

### fct_monthly_metrics

A dbt table with one row per combination of:

- Reporting month.
- Region.
- Product category.
- Customer segment.

Its measures are:

- revenue: summed revenue.
- units_sold: summed units.
- source_record_count: number of contributing input records.

source_record_count is not described as a transaction count because the
input does not contain transaction identifiers.

## Data-quality checks

The dbt checks cover:

- Required non-null fields.
- Approved region values.
- Unique combinations at the reporting grain.
- Monthly revenue reconciliation against raw_sales.
- Exact monthly reconciliation of units and input-record counts.
- Missing or unexpected reporting months.

Revenue comparisons allow a small absolute tolerance of 0.000001
because the current warehouse stores revenue as floating-point values.

The successful build checkpoint includes:

- 1 staging view.
- 1 reporting table.
- 17 data tests.
- 19 successful build results in total.

## Natural-language question answering

Run:

```powershell
.\.venv\Scripts\python.exe -m agents.text2sql "What was revenue by region in January 2024?"
```

The agent asks for:

- SEND: permission to send the question to Gemini.
- RUN: approval to execute the displayed query plan.

Gemini receives the question and allowed-query instructions, not
warehouse rows.

Python validates the proposed plan, executes the fixed SQL, and formats
the results. The model does not calculate or invent the answer.

### Supported scope

- Revenue grouped by region.
- A continuous range of complete calendar months.
- An explicit reporting year.
- All regions, products, and customer segments.

Unsupported requests should be returned for review.

The tool does not support arbitrary SQL, daily analysis, or additional
business filters. Structural validation cannot prove that every question
was interpreted correctly, so the displayed plan requires approval.

## Answer reconciliation

Before displaying an approved answer, the agent compares warehouse
results against:

```text
data/tableau_ready/monthly_metrics.csv
```

The check uses the same date window and compares:

- The regions present in the results.
- Each region's revenue total.

A matching grand total alone is not sufficient.

Missing files, mismatched regional values, and periods without records
do not produce a verified answer.

### Run the offline demonstration

```powershell
.\.venv\Scripts\python.exe -m tools.reconciliation_tools
```

This demonstration checks January 2024 without calling Gemini or
changing any data.

Reconciliation checks the local reporting CSV. It does not inspect an
open Tableau workbook's filters, its extract, or its published website.

## Tableau Public connection

Connect Tableau to this specific file:

```text
data/tableau_ready/monthly_metrics.csv
```

In Tableau Public Desktop:

1. Select Text file as the connection type.
2. Open monthly_metrics.csv.
3. Confirm metric_month is a date and revenue is numeric.
4. Drag Region to Columns.
5. Drag Revenue to Rows.
6. Use SUM(Revenue).

Do not union all CSV files in the output folder. They contain overlapping
data and could cause double counting.

After rebuilding the pipeline, refresh the desktop data source or its
extract.

A workbook published to Tableau Public does not automatically watch this
local CSV. Refresh and republish the workbook when appropriate.

Publishing to Tableau Public makes the workbook and included data public.
Use invented, public, or appropriately licensed data, not confidential data.

## Main outputs

| Output | Purpose |
|---|---|
| data/warehouse.duckdb | Local analytical database |
| data/tableau_ready/sales_clean.csv | Ordinary cleaned input |
| data/tableau_ready/sales_reviewed.csv | Cleaned input after approved header review |
| data/tableau_ready/monthly_metrics.csv | Published monthly reporting data |
| data/run_reports/ | JSON workflow summaries |

Run reports record metadata such as status, source path, output path,
row count, timestamp, and error type. They do not contain CSV row values
or API keys.

## Automated tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests -q
```

The current verification checkpoint is:

```text
61 passed
```

Python tests cover cleaning, approval behavior, retries, reporting,
warehouse loading, workflow routing, publication, query planning, and
reconciliation.

They use simulated AI responses and temporary databases or CSVs rather
than live Gemini requests.

The 17 dbt data tests are separate from the 61 Python tests. They run
as part of the --build-mart command.

## Verified sample results

The invented sample contains 3 input records.

### Revenue by region across the sample

| Region | Revenue |
|---|---:|
| East | $2,800.75 |
| North | $1,250.50 |
| South | $3,400.00 |
| Total | $7,451.25 |

### Revenue by month

| Month | Revenue | Source records |
|---|---:|---:|
| January 2024 | $4,650.50 | 2 |
| February 2024 | $2,800.75 | 1 |
| Total | $7,451.25 | 3 |

January's regional answer reconciled against the Tableau-ready CSV:

```text
North: $1,250.50
South: $3,400.00
Total: $4,650.50
```

## Current limitations

- This is a supervised workflow, not an unrestricted autonomous system.
- AI assists with headers and supported query parameters only.
- Arbitrary missing values, shifted rows, and wide-format reshaping are
  not implemented.
- Warehouse loads replace the current snapshot rather than accumulating
  historical data.
- CSV export, warehouse loading, and dbt execution are separate stages,
  not one combined transaction.
- A failed dbt test does not automatically roll back every model change.
  The workflow does not publish a new reporting CSV after that failure.
- Matching warehouse and CSV values do not prove that both are fresh or
  that all business classifications are correct.
- Tableau desktop refresh and online publication are separate actions.
- This demonstration is intended for sequential local runs, not
  concurrent multi-user production operation.

## Security and privacy

- Keep .env private and excluded from Git.
- Review staged files before publishing the repository.
- Do not upload private datasets, credentials, or confidential workbooks.
- .gitignore prevents accidental tracking; it does not encrypt files
  or remove secrets already committed.
- Avoid confidential information in questions sent to an external API.
- Keep certificate verification enabled when installing dependencies.

## Demonstration outline

1. Show the invented messy sales CSV.
2. Run the complete pipeline using --build-mart.
3. Show the successful dbt results and published reporting CSV.
4. Refresh the Tableau chart.
5. Ask the supported January regional-revenue question.
6. Review the proposed plan and approve it.
7. Show the reconciled database answer.

## Audio walkthrough

[Download the project narration (WAV)](docs/demo/narration.wav)

This audio overview uses a Windows synthetic voice. It describes the
working pipeline, validation checks, Tableau reporting, and supervised
question-answering features.

This is narration only, not a screen-recorded demonstration.