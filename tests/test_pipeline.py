from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from performance_planning_qa.config import PromptLogSettings, load_settings
from performance_planning_qa.database import DatabaseQueryError, QueryResult
from performance_planning_qa.pipeline import NL2SQLPipeline


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    def complete_json(self, messages, *, temperature):
        self.messages.append(messages)
        if not self.responses:
            raise AssertionError("No fake LLM response left.")
        return self.responses.pop(0)


class FakeDB:
    def __init__(self):
        self.sql_calls = []

    def execute_select(self, sql, *, max_rows):
        self.sql_calls.append(sql)
        if len(self.sql_calls) == 1:
            raise DatabaseQueryError("Teradata query failed: bad column name BAD_COL")
        return QueryResult(
            columns=["CHURN_DATE"],
            rows=[{"CHURN_DATE": "2026-01-01"}],
            row_count=1,
            truncated=False,
            elapsed_ms=10,
        )

    def close(self):
        pass


def test_settings(sql_repair_attempts=1):
    settings = load_settings()
    return replace(
        settings,
        prompt_log=PromptLogSettings(
            enabled=False,
            directory=Path(tempfile.gettempdir()) / "disabled_prompt_logs",
        ),
        sql_repair_attempts=sql_repair_attempts,
    )


class PipelineTests(unittest.TestCase):
    def test_direct_answer_payload_does_not_require_sql(self):
        pipeline = NL2SQLPipeline(
            test_settings(),
            llm_client=FakeLLM(
                [
                    {
                        "needs_clarification": False,
                        "clarifying_question": None,
                        "direct_answer": "Hi. I can help with analytics over the provided tables.",
                        "sql": None,
                        "assumptions": [],
                        "explanation": "",
                        "result_intent": "",
                    }
                ]
            ),
            db_client=FakeDB(),
        )

        result = pipeline.ask("hey")

        self.assertIsNone(result.sql)
        self.assertIn("provided tables", result.answer)

    def test_missing_sql_payload_falls_back_to_scoped_answer(self):
        pipeline = NL2SQLPipeline(
            test_settings(),
            llm_client=FakeLLM(
                [
                    {
                        "needs_clarification": False,
                        "clarifying_question": None,
                        "sql": None,
                        "assumptions": [],
                        "explanation": "",
                        "result_intent": "",
                    }
                ]
            ),
            db_client=FakeDB(),
        )

        result = pipeline.ask("hey")

        self.assertIsNone(result.sql)
        self.assertIn("performance planning", result.answer)

    def test_pipeline_does_not_write_prompt_logs_while_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = replace(
                test_settings(),
                prompt_log=PromptLogSettings(enabled=True, directory=Path(tmpdir)),
            )
            pipeline = NL2SQLPipeline(
                settings,
                llm_client=FakeLLM(
                    [
                        {
                            "needs_clarification": False,
                            "clarifying_question": None,
                            "direct_answer": "Hi. I can help with analytics over the provided tables.",
                            "sql": None,
                            "assumptions": [],
                            "explanation": "",
                            "result_intent": "",
                        }
                    ]
                ),
                db_client=FakeDB(),
            )

            result = pipeline.ask("hey")

            self.assertEqual((), result.prompt_log_paths)
            self.assertEqual([], list(Path(tmpdir).iterdir()))

    def test_database_query_error_gets_one_repair_retry(self):
        fake_llm = FakeLLM(
            [
                {
                    "needs_clarification": False,
                    "clarifying_question": None,
                    "direct_answer": None,
                    "sql": "SELECT BAD_COL FROM DP_EDW_PPF.AF_RET_GSM_CHURN",
                    "assumptions": [],
                    "explanation": "Initial SQL.",
                    "result_intent": "Test.",
                },
                {
                    "needs_clarification": False,
                    "clarifying_question": None,
                    "direct_answer": None,
                    "sql": "SELECT TOP 1 CHURN_DATE FROM DP_EDW_PPF.AF_RET_GSM_CHURN",
                    "assumptions": [],
                    "explanation": "Repaired SQL.",
                    "result_intent": "Test.",
                },
                {
                    "answer": "The sample churn date is 2026-01-01.",
                    "key_points": [],
                    "caveats": [],
                },
            ]
        )
        fake_db = FakeDB()
        pipeline = NL2SQLPipeline(
            test_settings(sql_repair_attempts=0),
            llm_client=fake_llm,
            db_client=fake_db,
        )

        result = pipeline.ask("Give one churn date")

        self.assertEqual(
            [
                "SELECT BAD_COL FROM DP_EDW_PPF.AF_RET_GSM_CHURN",
                "SELECT TOP 1 CHURN_DATE FROM DP_EDW_PPF.AF_RET_GSM_CHURN",
            ],
            fake_db.sql_calls,
        )
        self.assertEqual("The sample churn date is 2026-01-01.", result.answer)
        self.assertEqual(3, len(fake_llm.messages))


if __name__ == "__main__":
    unittest.main()
