"""Read-only SQL validation for LLM-generated Teradata queries."""

from __future__ import annotations

from dataclasses import dataclass
import re


ALLOWED_TABLES = {
    "DP_EDW_PPF.F_PP_BASE_REV_ATTRIBUTION",
    "DP_EDW_PPF.F_PP_PACKAGE_SUBSCRIPTIONS",
    "DP_EDW_PPF.F_LINE_SALES",
    "DP_EDW_PPF.F_LINE_SALES_ATTR",
    "DP_EDW_PPF.F_LINE_CHURN",
    "DP_EDW_PPF.F_MOBILITY_360",
    "DP_EDW_PPF.D_PP_PACKAGE",
    "DP_EDW_PPF.D_PP_PACKAGE_SRC_LKP",
    "DP_EDW_PPF_VEW.V_PP_RGS_CHURN_DLY",
    "DP_EDW_PPF_VEW.V_PP_RGS_CHURN_MTHLY",
    "DP_EDW_PPF_VEW.V_PP_RGS_RECONNECT_DLY",
    "DP_EDW_PPF_VEW.V_PP_RGS_RECONNET_MTHLY",
    "F_PP_BASE_REV_ATTRIBUTION",
    "F_PP_PACKAGE_SUBSCRIPTIONS",
    "F_LINE_SALES",
    "F_LINE_SALES_ATTR",
    "F_LINE_CHURN",
    "F_MOBILITY_360",
    "D_PP_PACKAGE",
    "D_PP_PACKAGE_SRC_LKP",
    "V_PP_RGS_CHURN_DLY",
    "V_PP_RGS_CHURN_MTHLY",
    "V_PP_RGS_RECONNECT_DLY",
    "V_PP_RGS_RECONNET_MTHLY",
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
    table_scan_sql = _mask_extract_from_keywords(sql)
    pattern = re.compile(
        r"\b(?:FROM|JOIN)\s+(?!\()([A-Za-z_][\w$]*(?:\s*\.\s*[A-Za-z_][\w$]*)?)",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(table_scan_sql):
        table = re.sub(r"\s+", "", match.group(1)).upper()
        references.append(table)
    return references


def _mask_extract_from_keywords(sql: str) -> str:
    """Mask ``FROM`` inside ``EXTRACT(... FROM ...)`` scalar expressions.

    Table discovery intentionally remains strict for real FROM and JOIN clauses.
    A plain regex cannot distinguish those clauses from Teradata's date-part
    expression, so mask only FROM tokens at the top level of an EXTRACT call.
    Keeping every other character in place preserves the surrounding SQL for the
    existing table-reference scanner.
    """

    chars = list(sql)
    extract_pattern = re.compile(r"\bEXTRACT\s*\(", flags=re.IGNORECASE)
    from_pattern = re.compile(r"\bFROM\b", flags=re.IGNORECASE)

    for extract_match in extract_pattern.finditer(sql):
        opening_parenthesis = sql.find("(", extract_match.start(), extract_match.end())
        if opening_parenthesis < 0:
            continue

        depth = 1
        index = opening_parenthesis + 1
        while index < len(sql) and depth:
            char = sql[index]
            if char == "(":
                depth += 1
                index += 1
                continue
            if char == ")":
                depth -= 1
                index += 1
                continue
            if depth == 1:
                from_match = from_pattern.match(sql, index)
                if from_match is not None:
                    for position in range(from_match.start(), from_match.end()):
                        chars[position] = " "
                    index = from_match.end()
                    continue
            index += 1

    return "".join(chars)


def _extract_cte_names(sql: str) -> list[str]:
    names: list[str] = []
    pattern = re.compile(r"(?:\bWITH\b|,)\s+([A-Za-z_][\w$]*)\s+AS\s*\(", flags=re.IGNORECASE)
    for match in pattern.finditer(sql):
        names.append(match.group(1).upper())
    return names
