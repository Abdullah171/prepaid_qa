from pathlib import Path
import tempfile
import unittest

from performance_planning_qa.config import LLMSettings, PromptLogSettings
from performance_planning_qa.prompt_logger import PromptLogger


class PromptLoggerTests(unittest.TestCase):
    def test_writes_prompt_messages_to_text_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = PromptLogger(
                PromptLogSettings(enabled=True, directory=Path(tmpdir)),
                LLMSettings(
                    provider="test",
                    endpoint="https://example.test/v1",
                    model="model",
                    api_key="not-needed",
                    verify_ssl=False,
                    timeout_seconds=30,
                    sql_temperature=0,
                    answer_temperature=0,
                    max_tokens=100,
                ),
            )

            record = logger.log(
                phase="sql_generation",
                temperature=0,
                messages=[
                    {"role": "system", "content": "System prompt"},
                    {"role": "user", "content": "Schema and sample context"},
                ],
            )

            self.assertIsNotNone(record)
            text = record.path.read_text(encoding="utf-8")
            self.assertIn("phase: sql_generation", text)
            self.assertIn("role=system", text)
            self.assertIn("System prompt", text)
            self.assertIn("Schema and sample context", text)

    def test_disabled_logger_does_not_write_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = PromptLogger(
                PromptLogSettings(enabled=False, directory=Path(tmpdir)),
                LLMSettings(
                    provider="test",
                    endpoint="https://example.test/v1",
                    model="model",
                    api_key="not-needed",
                    verify_ssl=False,
                    timeout_seconds=30,
                    sql_temperature=0,
                    answer_temperature=0,
                    max_tokens=100,
                ),
            )

            record = logger.log(
                phase="sql_generation",
                temperature=0,
                messages=[{"role": "user", "content": "Prompt"}],
            )

            self.assertIsNone(record)
            self.assertEqual([], list(Path(tmpdir).iterdir()))


if __name__ == "__main__":
    unittest.main()
