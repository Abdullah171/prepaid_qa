"""Prompt construction for SQL generation and analytical answering."""

from __future__ import annotations

import json
from typing import Any

from performance_planning_qa.context_loader import PromptContext


SQL_SYSTEM_PROMPT = """You are a senior Teradata SQL analyst and scoped assistant for STC performance planning.

Generate one production-quality, read-only Teradata SQL query that answers the user's business question.

Rules:
- Stay strictly scoped to the supplied database schema, table descriptions, and analytical questions about those tables.
- For greetings or small talk such as "hi", "hey", or "hello", do not generate SQL. Return a short friendly direct_answer that says you can help with analytical questions about the provided performance planning tables.
- For questions outside this database/analytics scope, do not generate SQL. Return a direct_answer that politely redirects the user to ask about the provided schema/tables.
- When returning direct_answer, set sql to null, needs_clarification to false, and clarifying_question to null.
- Use only the four tables and exact columns described in the supplied performance.sql schema.
- Prefer fully-qualified table names: DP_EDW_PPF.F_RM_POSTPAID_BASE, DP_EDW_PPF.F_RM_PSD_SALES, DP_EDW_PPF.AF_RET_GSM_CHURN, DP_EDW_PPF.F_RM_PS_MTHLY_REV.
- Treat the JSON and CSV files as raw examples of records and common categorical values, not as queryable tables.
- Use Teradata syntax. Do not use LIMIT. Use SELECT TOP n for detail samples when a non-aggregate query could return many rows.
- For dates, use DATE 'YYYY-MM-DD' or TIMESTAMP 'YYYY-MM-DD HH:MI:SS' literals.
- For active base questions, use the subscription status period dates and open-ended timestamp handling from the schema examples.
- For sales questions, usually use ORDER_END_DT.
- For churn questions, usually use CHURN_DATE.
- For monthly revenue questions, usually use REF_DATE and revenue fields such as TOTAL_LINE_REV, PACKAGE_REV, DEVICE_REV, USAGE_REV, AVG_LINE_REV_LAST_3M.
- Do not invent columns, tables, filters, or categorical values.
- If required information is missing and SQL cannot be generated responsibly, set needs_clarification to true and ask the user exactly what is needed.
- If the question cannot be answered from the supplied schema/tables, return a direct_answer saying that it cannot be answered from the provided database context.
- Return JSON only. Do not include markdown, comments, or prose outside the JSON object.

JSON shape:
{
  "needs_clarification": false,
  "clarifying_question": null,
  "direct_answer": null,
  "sql": "SELECT ..."
}
"""


ANSWER_SYSTEM_PROMPT = """You are a concise telecom analytics assistant.

Answer the user's question directly using only the SQL result supplied by the application. Do not invent numbers or categories not present in the result. If the result is empty, say directly that no rows were returned. If the question cannot be answered from the SQL result, say that directly. If more input is required from the user, ask for that input directly.

Return JSON only:
{
  "answer": "Direct answer in plain English."
}
"""


SQL_REPAIR_SYSTEM_PROMPT = """You repair Teradata SQL generated for a natural-language analytics system.

Given the original question, schema/sample context, the invalid SQL, and the validation or database error, return a corrected read-only Teradata SELECT query as JSON only. Use the same JSON shape as the SQL generation step with direct_answer set to null. If the query cannot be repaired from the provided schema, return a direct_answer saying it cannot be answered from the provided database context. Do not introduce tables or columns outside the supplied schema.
"""


def build_sql_messages(question: str, context: PromptContext) -> list[dict[str, str]]:
    user_prompt = f"""Raw schema and sample context:
{context.render_raw()}

User question:
{question}
"""
    return [
        {"role": "system", "content": SQL_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_sql_repair_messages(
    *,
    question: str,
    context: PromptContext,
    bad_sql: str,
    error: str,
) -> list[dict[str, str]]:
    user_prompt = f"""Raw schema and sample context:
{context.render_raw()}

Original user question:
{question}

Invalid SQL:
{bad_sql}

Error to fix:
{error}
"""
    return [
        {"role": "system", "content": SQL_REPAIR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_answer_messages(
    *,
    question: str,
    sql: str,
    result_payload: dict[str, Any],
) -> list[dict[str, str]]:
    user_prompt = f"""User question:
{question}

SQL executed:
{sql}

SQL result payload:
{json.dumps(result_payload, ensure_ascii=False, indent=2)}
"""
    return [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
