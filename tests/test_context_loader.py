from pathlib import Path
import unittest

from performance_planning_qa.context_loader import load_prompt_context


ROOT = Path(__file__).resolve().parents[1]


class PromptContextTests(unittest.TestCase):
    def test_loads_schema_and_all_sample_files(self):
        context = load_prompt_context(ROOT / "performance.sql", ROOT / "sample_data")

        self.assertIn("CREATE SET TABLE DP_EDW_PPF.F_RM_POSTPAID_BASE", context.schema.text)
        self.assertEqual(8, len(context.samples))

        rendered = context.render_raw()
        self.assertIn('<schema_file name="performance.sql">', rendered)
        self.assertIn("F_RM_PSD_SALES_202607091039.json", rendered)
        self.assertIn("_SELECT_DISTINCT_AF_RET_GSM_CHURN", rendered)


if __name__ == "__main__":
    unittest.main()
