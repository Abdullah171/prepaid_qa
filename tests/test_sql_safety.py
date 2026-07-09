import unittest

from performance_planning_qa.sql_safety import SQLSafetyError, split_sql_statements, validate_readonly_sql


class SQLSafetyTests(unittest.TestCase):
    def test_accepts_allowed_select(self):
        result = validate_readonly_sql(
            """
            SELECT CHURN_DATE, COUNT(*) AS churn_count
            FROM DP_EDW_PPF.AF_RET_GSM_CHURN
            GROUP BY 1
            """
        )

        self.assertEqual(("DP_EDW_PPF.AF_RET_GSM_CHURN",), result.table_references)

    def test_accepts_cte_with_allowed_tables(self):
        result = validate_readonly_sql(
            """
            WITH sales AS (
                SELECT ORDER_END_DT, REGION
                FROM DP_EDW_PPF.F_RM_PSD_SALES
            )
            SELECT REGION, COUNT(*) AS sales_count
            FROM sales
            GROUP BY 1
            """
        )

        self.assertIn("DP_EDW_PPF.F_RM_PSD_SALES", result.table_references)

    def test_rejects_delete(self):
        with self.assertRaises(SQLSafetyError):
            validate_readonly_sql("DELETE FROM DP_EDW_PPF.AF_RET_GSM_CHURN")

    def test_rejects_unknown_table(self):
        with self.assertRaises(SQLSafetyError):
            validate_readonly_sql("SELECT * FROM DBC.TABLES")

    def test_rejects_multiple_statements(self):
        with self.assertRaises(SQLSafetyError):
            validate_readonly_sql("SELECT * FROM DP_EDW_PPF.AF_RET_GSM_CHURN; SELECT 1")

    def test_split_ignores_semicolon_in_string(self):
        statements = split_sql_statements(
            "SELECT ';' AS marker FROM DP_EDW_PPF.F_RM_PSD_SALES;"
        )

        self.assertEqual(1, len(statements))

    def test_prohibited_keyword_inside_string_is_allowed(self):
        result = validate_readonly_sql(
            "SELECT * FROM DP_EDW_PPF.F_RM_PSD_SALES WHERE ORDER_TYP_NME = 'Delete'"
        )

        self.assertEqual(("DP_EDW_PPF.F_RM_PSD_SALES",), result.table_references)


if __name__ == "__main__":
    unittest.main()
