# prepaid_qa

Natural-language to Teradata SQL and analytical Q&A for the prepaid tables and helpers documented in `prepaid.sql`.

## What It Does

The app loads:

- Teradata credentials from `.env`
- STC LiteLLM OpenAI-compatible endpoint settings from `.env`
- `prepaid.sql` as the canonical schema and business metadata
- all JSON samples and CSV categorical-value dictionaries in `sample_data/` as system-level context

For each user question it:

1. Sends the schema and raw samples in the system message to GLM through LiteLLM to generate Teradata SQL.
2. Validates the SQL is read-only and references only the allowed tables.
3. Executes the SQL through `teradataml`.
4. Sends the query result back to GLM through LiteLLM to produce a concise analytical answer.
5. Conditionally builds a validated chart from those returned rows for explicit
   visualization requests and time-trend questions.

When the selected provider has streaming enabled and returns GLM's
`delta.reasoning_content` or MiniMax's `delta.reasoning`, the Streamlit interface
renders answer-generation reasoning live in a "Thinking" panel. SQL-generation
and SQL-repair reasoning remains internal so database errors, invalid SQL, and
repair details are never exposed to business users. While an analysis is running,
a Stop button cancels model streaming and the active Teradata request.
The sidebar's **Thinking** toggle is enabled by default. When it is off, every LLM
request for that question includes
`chat_template_kwargs: {"enable_thinking": false}` and the live reasoning panel is
replaced by an animated progress indicator.

For GLM only, each SQL-generation or answer-generation stream has a
50,000-character reasoning safety limit. If a stream reaches that limit, the
backend closes it, preserves the reasoning captured for that phase, and sends one
non-streaming follow-up with the original messages and captured reasoning using
`chat_template_kwargs: {"enable_thinking": false}`. For answer generation, those
original messages include the question, executed SQL, and complete analytical result.
For SQL generation, they include the schema, samples, curated rules, business
mappings, and both few-shot example sets; the fallback reuses the original bundle
without duplicating it.
The final instruction is phase-specific and placed after the captured reasoning: SQL
generation/repair must return executable SQL JSON, while answer generation must answer
from the returned rows and treat period coverage only as a supporting note. MiniMax
behavior is unchanged.

Structured LLM responses are parsed as strict JSON first. If parsing fails, the
app uses `json-repair` for common issues such as unquoted keys, single quotes,
trailing commas, surrounding prose, or an unterminated final object.

The FastAPI app also supports persisted chat sessions backed by local PostgreSQL,
DuckDB, or Teradata. Session history is passed back into the SQL and answer prompts so
follow-up questions can refer to the prior conversation.

Different chats can run LLM work concurrently. Follow-ups within the same chat remain
ordered, and Teradata execution is serialized over the shared connection. The app does
not currently provide authentication or per-user chat isolation; everyone with access
to the deployment should be treated as part of the same trusted workspace.

## Environment

Expected `.env` keys:

```env
LLM_PROVIDER="glm" # Choose "glm" or "minmax"

GLM_ENDPOINT="https://litellm.example/chat/completions"
GLM_MODEL="GLM-5.2"
GLM_API_KEY="..."

MINIMAX_ENDPOINT="https://minimax.example/v1"
MINIMAX_MODEL="MiniMaxAI/MiniMax-M2.7"
MINIMAX_API_KEY="not-needed"

TERADATA_HOST_NAME="..."
TERADATA_USER="..."
TERADATA_PASSWORD="..."
```

Choose the chat-history database in `.env`:

```env
chat_db="duckdb" # Choose "local", "duckdb", or "teradata"
CHAT_DUCKDB_PATH="data/chat_history.duckdb"

# Only used with chat_db="teradata"
CHAT_TERADATA_DATABASE="DP_EDW_PPF_STG"
```

With `chat_db="duckdb"`, startup creates the parent directory, DuckDB database file,
and chat tables automatically when they do not exist. Use an absolute path for a
server-mounted persistent volume if the application directory is ephemeral.

The `local` option uses the PostgreSQL credentials in `.env`:

```env
Host="localhost"
Port=5433
Database="pkgbench"
Username="pkgbench"
Password="pkgbench"
```

Optional keys:

```env
LLM_VERIFY_SSL=false
LLM_STREAM=false
LLM_TIMEOUT_SECONDS=1200
LLM_MAX_RETRIES=0
LLM_RETRY_BACKOFF_SECONDS=2
# Provider-specific values take precedence over the LLM_* defaults:
GLM_TIMEOUT_SECONDS=1800
GLM_STREAM=true
GLM_MAX_RETRIES=2
GLM_RETRY_BACKOFF_SECONDS=2
MINIMAX_STREAM=true
TERADATA_DATABASE="DP_EDW_PPF"
TERADATA_LOGMECH="LDAP"
SQL_REPAIR_ATTEMPTS=1
LLM_PROMPT_LOG_ENABLED=false # Set true to write LLM inputs to logs/llm_prompts/*.txt
LLM_PROMPT_LOG_DIR="logs/llm_prompts"
CHAT_DB_SCHEMA_PATH="sql/chat_memory_schema.sql"
CHAT_DB_LOCAL_SCHEMA_PATH="sql/chat_memory_schema_postgres.sql"
CHAT_DB_DUCKDB_SCHEMA_PATH="sql/chat_memory_schema_duckdb.sql"
PPQA_API_BASE_URL="http://127.0.0.1:8000"
PPQA_ALLOW_API_URL_EDIT=false
PPQA_LOG_LEVEL="INFO" # Set DEBUG, INFO, WARNING, ERROR, or CRITICAL
```

## Request diagnostics

Each question prints structured `[PPQA]` log entries to the terminal running the app.
The entries follow the request through the frontend worker, HTTP/SSE transport, API,
pipeline, LLM calls, SQL validation/repair, database query, and chat persistence. Use
the shared `request_id` to isolate one question. A failed entry includes `stage`,
`error_type`, `error`, elapsed time, and a traceback; a SQL failure returned as a
normal assistant response is also logged as failed. When a streamed request fails,
the Streamlit fallback displays its diagnostic request ID beneath the safe user-facing
message.

Failures returned inside a successful HTTP/SSE response are marked
`completed_with_error`, not `completed`. They also print a prominent `REQUEST FAILED`
block with the failed pipeline step, the backend error, and the generated or repaired
SQL that caused it.

The diagnostic log intentionally excludes credentials, model prompts/reasoning,
and database result rows. Successful requests log safe metadata such as response field
names, referenced tables, returned column names, and row counts. Generated SQL is
printed only in the failure block because it is needed to diagnose validation and
database errors.

## Install

```bash
python -m pip install -r requirements.txt
```

To install the optional `performance-planning-qa` command-line entry point, run:

```bash
python -m pip install -e .
```

## Usage

Start the FastAPI backend and Streamlit frontend together:

```bash
python run_app.py
```

The launcher uses ports 8000 and 8501 when available. If either port is already
occupied, it selects the next available port and configures the frontend to use
the FastAPI port it selected.

Run the focused frontend regression suite with:

```bash
python -m unittest discover -s tests -v
```

Start the FastAPI server:

```bash
python -m uvicorn main:app --reload
```

Or run the same server through `main.py`:

```bash
python main.py
```

Ask a question:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is monthly total revenue by REF_DATE for 2024?"}'
```

Disable model thinking for a question:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is 1+1?","enable_thinking":false}'
```

Generate and validate SQL without executing it:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Top 10 sales channels by completed orders in 2026","dry_run":true}'
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

API docs are available at `http://127.0.0.1:8000/docs`.

## Streamlit Frontend

Start the API, then run:

```bash
python -m streamlit run frontend/app.py
```

Open `http://127.0.0.1:8501`. The sidebar can create, select, and delete chat
sessions. Deleting a session removes it from the selected chat database through the
FastAPI API.

The frontend keeps one pooled API client per browser session, caches chat metadata
until an explicit mutation or refresh, and runs long analyses outside Streamlit's
render thread. While an answer runs, only its compact progress panel refreshes;
saved messages and charts are left mounted. Recent chats/messages are rendered
first, with controls for loading older history, to keep long-running sessions fast.

For production, set `PPQA_API_BASE_URL` in the deployment environment and leave
`PPQA_ALLOW_API_URL_EDIT` unset or false. This prevents browser users from directing
the Streamlit server to arbitrary API hosts. Enable that override only for trusted
local development.

## Posit Workbench and Posit Connect

From a Jupyter notebook running in Posit Workbench, this cell starts a development
preview:

```python
import sys

!{sys.executable} run_app.py
```

`run_app.py` prints the session-proxied Streamlit URL returned by Workbench's
`rserver-url` utility. The cell stays active until both development servers are
stopped with **Ctrl+C**.

Publishing that notebook does **not** publish the Streamlit application; Connect
publishes notebooks as documents. Deploy the project as Streamlit content instead.
The deployment entrypoint is `posit_app.py`. It lets Posit Connect manage the public
Streamlit URL and calls FastAPI in-process inside the same Connect worker, without
opening a second server port.

Install and register `rsconnect-python` once from Workbench:

```bash
python -m pip install rsconnect-python
export CONNECT_API_KEY='your-api-key'
rsconnect add \
  --server https://connect.example.com/ \
  --name my-connect \
  --api-key "$CONNECT_API_KEY"
```

Then deploy from the project directory (this command can also be run in a Jupyter
cell by prefixing it with `!`):

```bash
rsconnect deploy streamlit \
  --name my-connect \
  --title "Prepaid QA" \
  --entrypoint posit_app.py \
  .
```

The deploy command prints the Connect content URL. Configure the application's
LLM, Teradata, and chat-database environment variables in Posit Connect. The local
`.env` file is excluded from deployment by default, so secrets are not uploaded.
The Connect server must also have a Python version compatible with the constraint in
`pyproject.toml` and network access to the configured databases and LLM endpoint.

### Conditional Charts

Charts are generated from the rows returned for the current question, never by
loading or plotting an entire source table. Visualization wording does not
change or narrow the analytical SQL: the result must first contain everything
needed for the best textual answer. The app creates a chart when either:

- the user explicitly asks for a chart, graph, plot, visual, diagram, or visualization; or
- the question asks for a monthly, weekly, daily, quarterly, yearly, or other
  time trend.

Ordinary scalar answers and non-visual questions do not get a chart. Supported
types are line, bar, area, scatter, pie, and donut. An explicit compatible type
is honored; otherwise time series default to a line chart and categorical data
defaults to a bar chart. Other requested chart types fall back to a compatible
supported type with a visible explanation instead of being silently treated as
supported. A current instruction to use only text, prose, or a table suppresses
the chart even when the question otherwise contains trend wording.

Answer formatting is independent of chart generation. The assistant can include
a compact Markdown table whenever multi-row or multi-metric data is easier to
compare in columns, including ordinary non-chart questions. Large results are
summarized into a focused table instead of being dumped in full, while simple
scalar answers remain concise prose.

Tabular answers end with “Do you need this data in CSV format?”. A concise reply
such as “yes” reuses the immediately preceding result and displays a persistent
download button without rerunning the analysis. Users can also request CSV in the
original question to receive the button immediately. Natural replies that are not
covered by simple phrases are classified semantically, so paraphrases can accept
the offer while requests with a new metric, period, filter, or grouping start a
new analysis. The file is generated from exactly the compact Markdown table shown
in the final answer—not every row returned internally—and uses the same headings,
row order, and displayed values with standard CSV escaping and UTF-8 encoding for
Arabic text and Excel. CSV state is stored in the assistant message metadata, so
the download remains available after reopening a chat.

The language model may select returned column names, but it cannot provide chart
values. The backend validates those fields and copies every plotted value from
the returned data into a versioned chart payload. The payload is saved in the
assistant message's existing JSONB metadata, so charts render again when a chat
is reopened without a database migration. A follow-up such as “make that a bar
chart” reuses the preceding result instead of running the analysis again.
A presentation-intent layer also handles typos, missing spaces, slang, and
indirect requests such as “i need agraph for it” or “picture those numbers”.
High-confidence phrases use a fast local path; other wording is classified
semantically as a chart of the previous result, CSV of the displayed table, a
combined chart-and-CSV request, a CSV decline, or a genuinely new analysis. A
message such as “yes, CSV and also graph it” returns both artifacts without
rerunning the analysis. Requests that introduce a new metric, period, filter,
grouping, or comparison never reuse stale rows.
For a new analytical question, the answer model can also establish semantic
chart intent with a complete chart plan when flexible wording is not recognized
by the local detector. Python still validates every selected field and builds
the chart data exclusively from the current returned rows. An explicit
text-only or table-only instruction always suppresses this fallback.
A strong analytical continuation such as “do the same for churn” runs the new
analysis and inherits only the immediately preceding chart intent; it never
reuses the old chart's fields, title, or data.
When a trend or chart question first requires clarification, the resolved reply
also inherits that original visualization intent unless the user asks for text
or a table instead.

The API returns `chart: null` when no visualization is appropriate. Otherwise
the response includes a renderer-neutral payload such as:

```json
{
  "answer": "Revenue increased across the three months.",
  "chart": {
    "version": 1,
    "type": "line",
    "title": "Monthly revenue trend",
    "x": "MONTH",
    "y": ["REVENUE"],
    "series": null,
    "x_kind": "temporal",
    "trigger": "trend",
    "requested_type": null,
    "fallback_reason": null,
    "truncated": false,
    "data": [
      {"MONTH": "2026-01", "REVENUE": 10},
      {"MONTH": "2026-02", "REVENUE": 12}
    ]
  }
}
```

Chart payloads and frontend rendering retain every row returned for the selected
chart fields; the application does not truncate or sample chart data. Known
row-level identifier columns and common identifier aliases are rejected as chart
dimensions or measures, while aggregate fields such as `NUMBER_OF_LINES` remain
usable.
Multiple selected measures are rendered in separate panels with independent
value scales. The frontend uses the STC purple/cyan/magenta palette, focused
line-chart value scales, and period-aware date ticks so small trend changes and
monthly points remain readable.

## Chat Memory Schema

The DuckDB chat tables are defined in `sql/chat_memory_schema_duckdb.sql`. Select
DuckDB with:

```env
chat_db="duckdb"
CHAT_DUCKDB_PATH="data/chat_history.duckdb"
```

No manual initialization is needed: the API creates the database file, parent
directory, and schema during startup. Keep `CHAT_DUCKDB_PATH` on persistent storage
in a server deployment so chat history survives application redeployments.

The Teradata chat tables are defined in `sql/chat_memory_schema.sql`:

- `DP_EDW_PPF_STG.SC_PPQA_CHAT_SESSIONS`: session title and timestamps.
- `DP_EDW_PPF_STG.SC_PPQA_CHAT_MESSAGES`: user and assistant messages, dry-run flag,
  and Unicode CLOB JSON metadata containing complete SQL/result details for assistant
  responses.

Run that file with your Teradata SQL client before setting `chat_db="teradata"`.
The PostgreSQL version is in `sql/chat_memory_schema_postgres.sql` and can be applied
manually when needed:

```bash
PGPASSWORD=pkgbench psql -h localhost -p 5433 -U pkgbench -d pkgbench \
  -f sql/chat_memory_schema_postgres.sql
```

For local PostgreSQL and DuckDB storage, the API runs the corresponding schema at
startup with `CREATE TABLE IF NOT EXISTS`. For Teradata, startup verifies that both
tables exist.

## Session API

- `GET /sessions`: list chat sessions.
- `POST /sessions`: create a chat session.
- `GET /sessions/{session_id}`: fetch a session with messages.
- `PATCH /sessions/{session_id}`: rename a session.
- `DELETE /sessions/{session_id}`: delete a session and its messages.
- `POST /sessions/{session_id}/ask`: ask within a persisted chat session.

The original CLI remains available through the package script. Generate SQL and execute it:

```bash
performance-planning-qa "What is monthly total revenue by REF_DATE for 2024?"
```

Show the SQL:

```bash
performance-planning-qa --show-sql "Show churn count by churn type for June 2026"
```

Generate and validate SQL without executing:

```bash
performance-planning-qa --dry-run "Top 10 sales channels by completed orders in 2026"
```

Interactive mode:

```bash
performance-planning-qa
```

JSON output:

```bash
performance-planning-qa --json --show-sql "Average line revenue by value segment"
```

Prompt logging is controlled by `LLM_PROMPT_LOG_ENABLED`. When enabled, each LLM
input is written to a timestamped `.txt` file in `LLM_PROMPT_LOG_DIR`.

## Architecture

- `main.py`: FastAPI application entry point.
- `performance_planning_qa/config.py`: `.env` and runtime settings.
- `performance_planning_qa/context_loader.py`: loads `prepaid.sql` and all raw sample files.
- `performance_planning_qa/prompts.py`: SQL-generation, repair, and answer prompts.
- `performance_planning_qa/llm.py`: STC LiteLLM OpenAI-compatible client.
- `performance_planning_qa/prompt_logger.py`: optional prompt logging helper.
- `performance_planning_qa/sql_safety.py`: read-only SQL validation and table allow-list.
- `performance_planning_qa/database.py`: Teradata connection and query execution via `teradataml`.
- `performance_planning_qa/charting.py`: conditional chart intent, result-field validation,
  and versioned renderer-neutral chart payloads.
- `performance_planning_qa/csv_export.py`: displayed-table and full-query-result CSV
  exports, persisted export state, filenames, and standards-compliant serialization.
- `performance_planning_qa/pipeline.py`: end-to-end orchestration.

## Local Tests

These tests validate local streaming and CSV behavior without connecting to LiteLLM or Teradata:

```bash
python3 -m unittest discover -s tests
```
