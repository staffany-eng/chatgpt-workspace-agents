from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().with_name("nurtureany_lesson_review_digest.py")
SPEC = importlib.util.spec_from_file_location("nurtureany_lesson_review_digest", MODULE_PATH)
digest = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(digest)


def _write_candidate(directory: Path, name: str, **overrides):
    payload = {
        "lesson_id": name,
        "created_at": "2026-05-18T01:02:03Z",
        "source_thread_permalink": "https://staffany.slack.com/archives/C0B2UGK4DB6/p1778832250074079",
        "source_summary": "User corrected a reusable NurtureAny behavior.",
        "proposed_rule": "Use Lusha LinkedIn URL fallback only after scoped HubSpot company validation.",
        "applies_to": "lead enrichment",
        "target_repo_surface": "mcp_contract",
        "risk_class": "medium",
        "status": "pending_review",
        "reviewer": "",
        "review_notes": "",
    }
    payload.update(overrides)
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


class LessonReviewDigestTest(unittest.TestCase):
    def test_empty_pending_queue_is_silent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = digest.format_digest(digest.filtered_candidates(digest.load_candidates(Path(temp_dir)), "pending_review", 20), status="pending_review")

        self.assertEqual(output, "")

    def test_pending_candidate_digest_has_required_safe_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            _write_candidate(directory, "lesson-1")
            output = digest.format_digest(digest.filtered_candidates(digest.load_candidates(directory), "pending_review", 20), status="pending_review")

        self.assertIn("NurtureAny automation: Learning review", output)
        self.assertIn("Lesson: lesson-1", output)
        self.assertIn("Source: https://staffany.slack.com/archives/C0B2UGK4DB6/p1778832250074079", output)
        self.assertIn("Proposed rule: Use Lusha LinkedIn URL fallback", output)
        self.assertIn("Target repo surface: mcp_contract", output)
        self.assertIn("Risk: medium", output)
        self.assertIn("Reject, mark needs_more_evidence, or approve_for_repo_promotion.", output)
        self.assertIn("no behavior change", output)

    def test_status_filter_ignores_non_pending_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            _write_candidate(directory, "lesson-1", status="approved_for_repo_promotion")
            output = digest.format_digest(digest.filtered_candidates(digest.load_candidates(directory), "pending_review", 20), status="pending_review")

        self.assertEqual(output, "")

    def test_unsafe_candidate_is_redacted_not_printed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            _write_candidate(
                directory,
                "lesson-unsafe",
                source_summary="User: here is the transcript\nBot: thanks",
                proposed_rule="Call this phone +65 9123 4567 next time.",
            )
            output = digest.format_digest(digest.filtered_candidates(digest.load_candidates(directory), "pending_review", 20), status="pending_review")

        self.assertIn("Lesson: lesson-unsafe", output)
        self.assertIn("Redacted: unsafe candidate content", output)
        self.assertNotIn("+65 9123 4567", output)
        self.assertNotIn("User: here is the transcript", output)

    def test_main_prints_nothing_for_empty_queue(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            buffer = io.StringIO()
            with patch.dict(os.environ, {digest.HERMES_VENV_REEXEC_ENV: "1"}), redirect_stdout(buffer):
                exit_code = digest.main(["--candidates-dir", temp_dir])

        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
