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

Optional keys:

```env
STC_MINIMAX_API_KEY="not-needed"
STC_MINIMAX_VERIFY_SSL=false
STC_MINIMAX_TIMEOUT_SECONDS=120
STC_MINIMAX_MAX_TOKENS=4096
TERADATA_DATABASE="DP_EDW_PPF"
TERADATA_LOGMECH="LDAP"
QUERY_MAX_ROWS=200
ANSWER_RESULT_MAX_CHARS=60000
SQL_REPAIR_ATTEMPTS=1
LLM_PROMPT_LOG_ENABLED=false
LLM_PROMPT_LOG_DIR="logs/llm_prompts"
```

## Install

```bash
uv sync
```

## Usage

Generate SQL and execute it:

```bash
uv run python main.py "What is monthly total revenue by REF_DATE for 2024?"
```

Show the SQL:

```bash
uv run python main.py --show-sql "Show churn count by churn type for June 2026"
```

Generate and validate SQL without executing:

```bash
uv run python main.py --dry-run "Top 10 sales channels by completed orders in 2026"
```

Interactive mode:

```bash
uv run python main.py
```

JSON output:

```bash
uv run python main.py --json --show-sql "Average line revenue by value segment"
```

Prompt logging is currently disabled in the pipeline and CLI. The logger code remains in the repo for debugging, but normal runs do not write prompt `.txt` files or print prompt log paths.

## Architecture

- `main.py`: CLI entry point.
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
