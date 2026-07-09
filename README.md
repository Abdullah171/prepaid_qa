# performance_planning_qa

Natural-language to Teradata SQL and analytical Q&A for the four performance planning tables in `performance.sql`.

## What It Does

The app loads:

- Teradata credentials from `.env`
- STC MiniMax OpenAI-compatible endpoint settings from `.env`
- `performance.sql` as the canonical schema and business metadata
- all raw JSON and CSV files in `sample_data/` as prompt context

For each user question it:

1. Sends the schema and raw samples to MiniMax to generate Teradata SQL.
2. Validates the SQL is read-only and references only the allowed tables.
3. Executes the SQL through `teradataml`.
4. Sends the query result back to MiniMax to produce a concise analytical answer.

The FastAPI app also supports persisted chat sessions backed by local PostgreSQL. Session
history is passed back into the SQL and answer prompts so follow-up questions can refer to
the prior conversation.

## Environment

Expected `.env` keys:

```env
ANALYSIS_PROVIDER="stc/minmax2.7"
STC_MINIMAX_ENDPOINT="https://.../v1"
DEFAULT_STC_MINIMAX_MODEL="MiniMaxAI/MiniMax-M2.7"

TERADATA_HOST_NAME="..."
TERADATA_USER="..."
TERADATA_PASSWORD="..."
```

Local chat memory uses the PostgreSQL credentials in `.env`:

```env
Host="localhost"
Port=5433
Database="pkgbench"
Username="pkgbench"
Password="pkgbench"
```

Optional keys:

```env
STC_MINIMAX_API_KEY="not-needed"
STC_MINIMAX_VERIFY_SSL=false
STC_MINIMAX_TIMEOUT_SECONDS=120
STC_MINIMAX_MAX_TOKENS=4096
TERADATA_DATABASE="DP_EDW_PPF"
TERADATA_LOGMECH="LDAP"
SQL_REPAIR_ATTEMPTS=1
LLM_PROMPT_LOG_ENABLED=false
LLM_PROMPT_LOG_DIR="logs/llm_prompts"
CHAT_DB_SCHEMA_PATH="sql/chat_memory_schema.sql"
PPQA_API_BASE_URL="http://127.0.0.1:8000"
```

## Install

```bash
uv sync
```

## Usage

Start the FastAPI server:

```bash
uv run uvicorn main:app --reload
```

Or run the same server through `main.py`:

```bash
uv run python main.py
```

Ask a question:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is monthly total revenue by REF_DATE for 2024?"}'
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
uv run streamlit run frontend/app.py
```

Open `http://127.0.0.1:8501`. The sidebar can create, select, and delete chat
sessions. Deleting a session removes it from PostgreSQL through the FastAPI API.

## Chat Memory Schema

The chat tables are defined in `sql/chat_memory_schema.sql`:

- `public.ppqa_chat_sessions`: session title and timestamps.
- `public.ppqa_chat_messages`: user and assistant messages, dry-run flag, and JSONB
  metadata containing SQL/result details for assistant responses.

Apply the schema manually when needed:

```bash
PGPASSWORD=pkgbench psql -h localhost -p 5433 -U pkgbench -d pkgbench \
  -f sql/chat_memory_schema.sql
```

The API also runs this schema file at startup with `CREATE TABLE IF NOT EXISTS`.

## Session API

- `GET /sessions`: list chat sessions.
- `POST /sessions`: create a chat session.
- `GET /sessions/{session_id}`: fetch a session with messages.
- `PATCH /sessions/{session_id}`: rename a session.
- `DELETE /sessions/{session_id}`: delete a session and its messages.
- `POST /sessions/{session_id}/ask`: ask within a persisted chat session.

The original CLI remains available through the package script. Generate SQL and execute it:

```bash
uv run performance-planning-qa "What is monthly total revenue by REF_DATE for 2024?"
```

Show the SQL:

```bash
uv run performance-planning-qa --show-sql "Show churn count by churn type for June 2026"
```

Generate and validate SQL without executing:

```bash
uv run performance-planning-qa --dry-run "Top 10 sales channels by completed orders in 2026"
```

Interactive mode:

```bash
uv run performance-planning-qa
```

JSON output:

```bash
uv run performance-planning-qa --json --show-sql "Average line revenue by value segment"
```

Prompt logging is currently disabled in the pipeline and CLI. The logger code remains in the repo for debugging, but normal runs do not write prompt `.txt` files or print prompt log paths.

## Architecture

- `main.py`: FastAPI application entry point.
- `performance_planning_qa/config.py`: `.env` and runtime settings.
- `performance_planning_qa/context_loader.py`: loads `performance.sql` and all raw sample files.
- `performance_planning_qa/prompts.py`: SQL-generation, repair, and answer prompts.
- `performance_planning_qa/llm.py`: STC MiniMax OpenAI-compatible client.
- `performance_planning_qa/prompt_logger.py`: optional prompt logging helper, currently disabled in the pipeline.
- `performance_planning_qa/sql_safety.py`: read-only SQL validation and table allow-list.
- `performance_planning_qa/database.py`: Teradata connection and query execution via `teradataml`.
- `performance_planning_qa/pipeline.py`: end-to-end orchestration.

## Local Tests

These tests validate local context loading and SQL guardrails without connecting to MiniMax or Teradata:

```bash
python3 -m unittest discover -s tests
```
