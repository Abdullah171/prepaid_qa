import unittest

from performance_planning_qa.prompts import ANSWER_SYSTEM_PROMPT


class AnswerPromptFormattingTests(unittest.TestCase):
    def test_tables_are_not_limited_to_chart_answers(self) -> None:
        self.assertIn(
            "Decide whether a table helps independently of whether a chart is returned",
            ANSWER_SYSTEM_PROMPT,
        )
        self.assertIn(
            'A useful table may be included when "chart" is null',
            ANSWER_SYSTEM_PROMPT,
        )
        self.assertIn(
            "multiple rows or multiple metrics that are easier to compare or scan",
            ANSWER_SYSTEM_PROMPT,
        )

    def test_table_guidance_keeps_answers_compact_and_accurate(self) -> None:
        self.assertIn("normally include at most 12 relevant rows", ANSWER_SYSTEM_PROMPT)
        self.assertIn("never alter, calculate, or invent values", ANSWER_SYSTEM_PROMPT)
        self.assertIn(
            "Do not force a table for a single scalar value",
            ANSWER_SYSTEM_PROMPT,
        )


if __name__ == "__main__":
    unittest.main()
