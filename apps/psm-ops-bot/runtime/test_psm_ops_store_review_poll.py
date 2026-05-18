from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).with_name("scripts") / "psm_ops_store_review_poll.py"
MCP_DIR = Path(__file__).with_name("mcp")


def load_script():
    if str(MCP_DIR) not in sys.path:
        sys.path.insert(0, str(MCP_DIR))
    sys.modules.pop("psm_ops_store_review_poll_under_test", None)
    spec = importlib.util.spec_from_file_location("psm_ops_store_review_poll_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["psm_ops_store_review_poll_under_test"] = module
    spec.loader.exec_module(module)
    return module


class StoreReviewPollScriptTest(unittest.TestCase):
    def test_dry_run_reports_candidate_payload_without_persisting(self):
        script = load_script()
        review = {
            "store": "app_store",
            "app_ref": "1360658903",
            "review_id": "345030591",
            "rating": 3,
            "title": "Missing Store Clock-In Section",
            "body": "The store clock-in section is missing.",
            "review_url": "https://apps.apple.com/app/id1360658903",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = str(Path(tmpdir) / "store_reviews.json")
            with patch.object(script, "poll_new_reviews", return_value={"confidence": "verified", "answer": {"reviews": [review]}}), patch(
                "sys.stdout", new_callable=StringIO
            ) as stdout:
                code = script.main(["--state-path", state_path])

            self.assertEqual(code, 0)
            output = stdout.getvalue()
            self.assertIn("store_review_poll:dry_run", output)
            self.assertIn("PSM Ops automation: Store review triage", output)
            self.assertIn("identity_requested_private", output)
            self.assertFalse(Path(state_path).exists())

    def test_no_new_reviews_is_silent(self):
        script = load_script()
        with patch.object(script, "poll_new_reviews", return_value={"confidence": "verified", "answer": {"reviews": [], "skipped_duplicate_keys": ["app_store:1360658903:1"]}}), patch(
            "sys.stdout", new_callable=StringIO
        ) as stdout:
            code = script.main([])

        self.assertEqual(code, 0)
        self.assertIn("[SILENT] PSM Ops automation: store review poll no new reviews", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
