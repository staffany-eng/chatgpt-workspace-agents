from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from test_helpers import load_mcp_module


class StaffAnyDataLearningServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("staffany_data_learning_server.py")

    def test_exposes_reviewed_learning_tools_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            [
                "list_staffany_data_lesson_candidates",
                "read_staffany_data_lesson_candidate",
                "record_staffany_data_lesson_candidate",
                "update_staffany_data_lesson_candidate_status",
            ],
        )

    def test_lesson_candidate_write_list_read(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            written = self.module.record_staffany_data_lesson_candidate(
                lesson_id="thread-123-learning",
                source_thread_permalink="https://staffany.slack.com/archives/C0AU19E6T0C/p1710000000000100",
                source_summary="User corrected that first data requests should remain plan-first even when the request sounds urgent.",
                proposed_rule="For first Slack mentions that need app data, return the preflight and wait for run.",
                applies_to="Slack data request routing",
                target_repo_surface="skill_reference",
                risk_class="low",
            )
            listed = self.module.list_staffany_data_lesson_candidates(status="pending_review")
            loaded = self.module.read_staffany_data_lesson_candidate("thread-123-learning")

        self.assertEqual(written["confidence"], "verified")
        self.assertEqual(written["answer"]["status"], "pending_review")
        self.assertEqual(written["answer"]["reviewer"], "")
        self.assertFalse(written["answer"]["honcho_used"])
        self.assertFalse(written["answer"].get("active_behavior_changed", False))
        self.assertEqual(listed["answer"]["returned_count"], 1)
        self.assertEqual(loaded["answer"]["lesson_id"], "thread-123-learning")
        self.assertEqual(loaded["answer"]["target_repo_surface"], "skill_reference")

    def test_lesson_candidate_status_update_requires_human_marker_and_notes(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            self.module.record_staffany_data_lesson_candidate(
                lesson_id="thread-123-learning",
                source_thread_permalink="https://staffany.slack.com/archives/C0AU19E6T0C/p1710000000000100",
                source_summary="User corrected that first data requests should remain plan-first.",
                proposed_rule="For first Slack mentions that need app data, return the preflight and wait for run.",
                applies_to="Slack data request routing",
                target_repo_surface="skill_reference",
                risk_class="low",
            )
            missing_marker = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="approved_for_repo_promotion",
                reviewer="kaiyi@staffany.com",
                review_notes="Approved for repo reference update.",
                approval_marker="approve",
            )
            missing_notes = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="approved_for_repo_promotion",
                reviewer="kaiyi@staffany.com",
                review_notes="",
                approval_marker="human reviewed lesson",
            )
            updated = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="approved_for_repo_promotion",
                reviewer="kaiyi@staffany.com",
                review_notes="Approved for repo reference update.",
                approval_marker="human reviewed lesson",
            )
            loaded = self.module.read_staffany_data_lesson_candidate("thread-123-learning")

        self.assertEqual(missing_marker["confidence"], "blocked")
        self.assertEqual(missing_notes["confidence"], "blocked")
        self.assertEqual(updated["confidence"], "verified")
        self.assertEqual(updated["answer"]["previous_status"], "pending_review")
        self.assertEqual(updated["answer"]["status"], "approved_for_repo_promotion")
        self.assertEqual(updated["answer"]["reviewer"], "kaiyi@staffany.com")
        self.assertEqual(len(updated["answer"]["review_history"]), 1)
        self.assertEqual(loaded["answer"]["status"], "approved_for_repo_promotion")

    def test_lesson_candidate_status_update_blocks_automation_reviewer_without_false_positive(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            self.module.record_staffany_data_lesson_candidate(
                lesson_id="thread-123-learning",
                source_thread_permalink="https://staffany.slack.com/archives/C0AU19E6T0C/p1710000000000100",
                source_summary="Reusable behavior correction.",
                proposed_rule="Change future behavior after review.",
                applies_to="Da Ta Hermz",
                target_repo_surface="skill_reference",
                risk_class="low",
            )
            automation = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="rejected",
                reviewer="staffanydatabot automation",
                review_notes="Rejecting my own candidate.",
                approval_marker="human reviewed lesson",
            )
            human_named_robert = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="needs_more_evidence",
                reviewer="Robert Tan",
                review_notes="Needs a second live example before repo promotion.",
                approval_marker="human reviewed lesson",
            )

        self.assertEqual(automation["confidence"], "blocked")
        self.assertIn("cannot approve", automation["answer"])
        self.assertEqual(human_named_robert["confidence"], "verified")
        self.assertEqual(human_named_robert["answer"]["status"], "needs_more_evidence")

    def test_lesson_candidate_promoted_requires_approval_and_live_evidence(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            self.module.record_staffany_data_lesson_candidate(
                lesson_id="thread-123-learning",
                source_thread_permalink="https://staffany.slack.com/archives/C0AU19E6T0C/p1710000000000100",
                source_summary="Reusable behavior correction.",
                proposed_rule="Change future behavior after review.",
                applies_to="Da Ta Hermz",
                target_repo_surface="mcp_contract",
                risk_class="medium",
            )
            early_promote = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="promoted",
                reviewer="kaiyi@staffany.com",
                review_notes="Trying to promote before repo approval.",
                approval_marker="human reviewed lesson",
                repo_commit_sha="abcdef1",
                live_verified_at="2026-05-19T01:00:00Z",
                live_verification_summary="Verified live.",
            )
            self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="approved_for_repo_promotion",
                reviewer="kaiyi@staffany.com",
                review_notes="Approved for MCP contract change.",
                approval_marker="human reviewed lesson",
            )
            missing_evidence = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="promoted",
                reviewer="kaiyi@staffany.com",
                review_notes="Repo change merged.",
                approval_marker="human reviewed lesson",
                repo_commit_sha="abcdef1",
            )
            bad_sha = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="promoted",
                reviewer="kaiyi@staffany.com",
                review_notes="Repo change merged.",
                approval_marker="human reviewed lesson",
                repo_commit_sha="not-a-sha",
                live_verified_at="2026-05-19T01:00:00Z",
                live_verification_summary="Verified live.",
            )
            promoted = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="promoted",
                reviewer="kaiyi@staffany.com",
                review_notes="Repo change verified, deployed, and live-checked.",
                approval_marker="human reviewed lesson",
                repo_commit_sha="abcdef1",
                live_verified_at="2026-05-19T01:00:00Z",
                live_verification_summary="Hermes Data Bot verify passed; cloud doctor reported active gateway and learning tools.",
            )

        self.assertEqual(early_promote["confidence"], "blocked")
        self.assertIn("approved_for_repo_promotion", early_promote["answer"])
        self.assertEqual(missing_evidence["confidence"], "blocked")
        self.assertEqual(bad_sha["confidence"], "blocked")
        self.assertEqual(promoted["confidence"], "verified")
        self.assertEqual(promoted["answer"]["status"], "promoted")
        self.assertEqual(promoted["answer"]["repo_commit_sha"], "abcdef1")
        self.assertEqual(promoted["answer"]["active_behavior_changed"], False)

    def test_lesson_candidate_status_update_rejects_unsafe_review_notes(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            self.module.record_staffany_data_lesson_candidate(
                lesson_id="thread-123-learning",
                source_thread_permalink="https://staffany.slack.com/archives/C0AU19E6T0C/p1710000000000100",
                source_summary="Reusable behavior correction.",
                proposed_rule="Change future behavior after review.",
                applies_to="Da Ta Hermz",
                target_repo_surface="skill_reference",
                risk_class="low",
            )
            result = self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="rejected",
                reviewer="kaiyi@staffany.com",
                review_notes="Reject this because user pasted api_key=redacted-token-value.",
                approval_marker="human reviewed lesson",
            )
            loaded = self.module.read_staffany_data_lesson_candidate("thread-123-learning")

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(loaded["answer"]["status"], "pending_review")

    def test_lesson_candidate_rejects_secret_payload(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            result = self.module.record_staffany_data_lesson_candidate(
                source_summary="User pasted api_key=redacted-token-value",
                proposed_rule="Remember this credential for future BigQuery runs.",
                applies_to="runtime",
                target_repo_surface="skill_reference",
                risk_class="high",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("No candidate was written", result["caveat"])

    def test_lesson_candidate_rejects_raw_transcript_query_rows_and_phone(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            transcript = self.module.record_staffany_data_lesson_candidate(
                source_summary="User: please use this forever\nBot: okay I will",
                proposed_rule="Use the raw transcript forever.",
                applies_to="Slack",
                target_repo_surface="skill_reference",
                risk_class="medium",
            )
            rows = self.module.record_staffany_data_lesson_candidate(
                source_summary='{"rows": [{"org_id": "1", "phone": "+65 9123 4567"}]}',
                proposed_rule="Store the query output as memory.",
                applies_to="BigQuery",
                target_repo_surface="skill_reference",
                risk_class="high",
            )
            phone = self.module.record_staffany_data_lesson_candidate(
                source_summary="User corrected a support path.",
                proposed_rule="Use +65 9123 4567 for future checks.",
                applies_to="support",
                target_repo_surface="skill_reference",
                risk_class="high",
            )

        self.assertEqual(transcript["confidence"], "blocked")
        self.assertEqual(rows["confidence"], "blocked")
        self.assertEqual(phone["confidence"], "blocked")

    def test_lesson_candidate_rejects_invalid_surface_and_risk(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            bad_surface = self.module.record_staffany_data_lesson_candidate(
                source_summary="User gave a reusable correction.",
                proposed_rule="Change future behavior.",
                applies_to="Da Ta Hermz",
                target_repo_surface="honcho",
                risk_class="low",
            )
            bad_risk = self.module.record_staffany_data_lesson_candidate(
                source_summary="User gave a reusable correction.",
                proposed_rule="Change future behavior.",
                applies_to="Da Ta Hermz",
                target_repo_surface="skill_reference",
                risk_class="auto_approved",
            )

        self.assertEqual(bad_surface["confidence"], "blocked")
        self.assertEqual(bad_risk["confidence"], "blocked")

    def test_list_allows_zero_limit_and_needs_more_evidence_filter(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            self.module.record_staffany_data_lesson_candidate(
                lesson_id="thread-123-learning",
                source_thread_permalink="https://staffany.slack.com/archives/C0AU19E6T0C/p1710000000000100",
                source_summary="Reusable behavior correction.",
                proposed_rule="Change future behavior after review.",
                applies_to="Da Ta Hermz",
                target_repo_surface="skill_reference",
                risk_class="low",
            )
            self.module.update_staffany_data_lesson_candidate_status(
                lesson_id="thread-123-learning",
                status="needs_more_evidence",
                reviewer="kaiyi@staffany.com",
                review_notes="Needs a second live example before repo promotion.",
                approval_marker="human reviewed lesson",
            )
            zero = self.module.list_staffany_data_lesson_candidates(status="needs_more_evidence", limit=0)
            listed = self.module.list_staffany_data_lesson_candidates(status="needs_more_evidence")

        self.assertEqual(zero["answer"]["returned_count"], 0)
        self.assertEqual(zero["answer"]["total_matching_count"], 1)
        self.assertEqual(listed["answer"]["returned_count"], 1)
        self.assertEqual(listed["answer"]["candidates"][0]["status"], "needs_more_evidence")

    def test_list_redacts_unsafe_runtime_drift(self):
        with tempfile.TemporaryDirectory() as lesson_dir, patch.dict(os.environ, {"STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir}):
            Path(lesson_dir, "unsafe.json").write_text(
                json.dumps(
                    {
                        "lesson_id": "unsafe",
                        "created_at": "2026-05-19T00:00:00+00:00",
                        "source_summary": "User: secret\nBot: okay",
                        "proposed_rule": "Use raw transcript.",
                        "applies_to": "Slack",
                        "target_repo_surface": "skill_reference",
                        "risk_class": "high",
                        "status": "pending_review",
                    }
                ),
                encoding="utf-8",
            )
            listed = self.module.list_staffany_data_lesson_candidates()
            loaded = self.module.read_staffany_data_lesson_candidate("unsafe")

        self.assertEqual(listed["confidence"], "verified")
        self.assertTrue(listed["answer"]["candidates"][0]["redacted"])
        self.assertEqual(loaded["confidence"], "blocked")


class StaffAnyDataLearningReportTest(unittest.TestCase):
    def test_report_prints_safe_counts_only(self):
        report_path = Path(__file__).parents[1] / "report-staffany-data-learning.py"
        with tempfile.TemporaryDirectory() as lesson_dir:
            Path(lesson_dir, "safe.json").write_text(
                json.dumps(
                    {
                        "lesson_id": "safe",
                        "created_at": "2026-04-01T00:00:00+00:00",
                        "source_summary": "Do not print this text in the report.",
                        "proposed_rule": "Do not print this rule in the report.",
                        "applies_to": "Slack",
                        "target_repo_surface": "skill_reference",
                        "risk_class": "low",
                        "status": "pending_review",
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(report_path), "--stale-days", "1"],
                check=False,
                capture_output=True,
                text=True,
                env={**os.environ, "STAFFANY_DATA_LEARNING_CANDIDATES_DIR": lesson_dir},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("staffany_data_learning_review_report:ok", result.stdout)
        self.assertIn("pending=1", result.stdout)
        self.assertIn("stale_pending=1", result.stdout)
        self.assertIn("lesson_candidates_content:omitted", result.stdout)
        self.assertNotIn("Do not print this text", result.stdout)
        self.assertNotIn("Do not print this rule", result.stdout)


if __name__ == "__main__":
    unittest.main()
