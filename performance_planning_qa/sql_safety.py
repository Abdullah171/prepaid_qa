"""Read-only SQL validation for LLM-generated Teradata queries."""

from __future__ import annotations

from dataclasses import dataclass
import re


ALLOWED_TABLES = {
    "DP_EDW_PPF.F_RM_POSTPAID_BASE",
    "DP_EDW_PPF.F_RM_PSD_SALES",
    "DP_EDW_PPF.AF_RET_GSM_CHURN",
    "DP_EDW_PPF.F_RM_PS_MTHLY_REV",
    "F_RM_POSTPAID_BASE",
    "F_RM_PSD_SALES",
    "AF_RET_GSM_CHURN",
    "F_RM_PS_MTHLY_REV",
}

PROHIBITED_KEYWORDS = {
    "ABORT",
    "ALTER",
    "BEGIN",
    "CALL",
    "COLLECT",
    "COMMIT",
    "CREATE",
    "DATABASE",
    "DELETE",
    "DROP",
    "EXEC",
    "EXECUTE",
    "GRANT",
    "INSERT",
    "MERGE",
    "REPLACE",
    "REVOKE",
    "ROLLBACK",
    "SET",
    "TRUNCATE",
    "UPDATE",
}


@dataclass(frozen=True)
class SQLValidationResult:
    sql: str
    table_references: tuple[str, ...]


class SQLSafetyError(ValueError):
    pass


def validate_readonly_sql(sql: str) -> SQLValidationResult:
    cleaned = normalize_sql(sql)
    statements = split_sql_statements(cleaned)
    if len(statements) != 1:
        raise SQLSafetyError("SQL must contain exactly one statement.")

    statement = statements[0]
    comment_free = strip_sql_comments(statement)
    scan_sql = mask_string_literals(comment_free)
    upper_sql = scan_sql.upper()
    first_token = _first_token(upper_sql)
    if first_token not in {"SELECT", "WITH"}:
        raise SQLSafetyError("Only read-only SELECT or WITH queries are allowed.")

    prohibited = sorted(keyword for keyword in PROHIBITED_KEYWORDS if re.search(rf"\b{keyword}\b", upper_sql))
    if prohibited:
        raise SQLSafetyError(f"Prohibited SQL keyword found: {', '.join(prohibited)}")

    cte_names = set(_extract_cte_names(comment_free)) if first_token == "WITH" else set()
    table_references = tuple(
        table for table in _extract_table_references(scan_sql) if table not in cte_names
    )
    if not table_references:
        raise SQLSafetyError("No table references were found.")

    unknown = [table for table in table_references if table not in ALLOWED_TABLES]
    if unknown:
        raise SQLSafetyError(f"Query references tables outside the allowed schema: {', '.join(unknown)}")

    return SQLValidationResult(sql=statement, table_references=table_references)


def normalize_sql(sql: str) -> str:
    sql = sql.strip()
    fenced = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", sql, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        sql = fenced.group(1).strip()
    if "\x00" in sql:
        raise SQLSafetyError("SQL contains a null byte.")
    return sql.strip()


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n\r]*", " ", sql)
    return sql


def mask_string_literals(sql: str) -> str:
    chars = list(sql)
    index = 0
    in_single = False
    while index < len(chars):
        char = chars[index]
        next_char = chars[index + 1] if index + 1 < len(chars) else ""
        if in_single:
            if char == "'" and next_char == "'":
                chars[index] = " "
                chars[index + 1] = " "
                index += 2
                continue
            if char == "'":
                in_single = False
            else:
                chars[index] = " "
        elif char == "'":
            in_single = True
        index += 1
    return "".join(chars)


def split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    start = 0
    in_single = False
    in_double = False
    index = 0
    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""
        if in_single:
            if char == "'" and next_char == "'":
                index += 2
                continue
            if char == "'":
                in_single = False
        elif in_double:
            if char == '"':
                in_double = False
        else:
            if char == "'":
                in_single = True
            elif char == '"':
                in_double = True
            elif char == ";":
                piece = sql[start:index].strip()
                if piece:
                    statements.append(piece)
                start = index + 1
        index += 1

    tail = sql[start:].strip()
    if tail:
        statements.append(tail)
    return statements


def _first_token(sql: str) -> str:
    match = re.search(r"[A-Z_]+", sql)
    return match.group(0) if match else ""


def _extract_table_references(sql: str) -> list[str]:
    references: list[str] = []
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+(?!\()([A-Za-z_][\w$]*(?:\s*\.\s*[A-Za-z_][\w$]*)?)",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(sql):
        table = re.sub(r"\s+", "", match.group(1)).upper()
        references.append(table)
    return references


def _extract_cte_names(sql: str) -> list[str]:
    names: list[str] = []
    pattern = re.compile(r"(?:\bWITH\b|,)\s+([A-Za-z_][\w$]*)\s+AS\s*\(", flags=re.IGNORECASE)
    for match in pattern.finditer(sql):
        names.append(match.group(1).upper())
    return names
