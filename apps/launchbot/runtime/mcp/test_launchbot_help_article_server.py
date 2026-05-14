from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


class LaunchbotHelpArticleServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("launchbot_help_article_server.py")
        fixtures_path = Path(__file__).with_name("fixtures") / "help_article_video_fixtures.json"
        self.fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))["fixtures"]

    def test_exposes_video_update_tools_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["create_help_article_video_update_draft", "preview_help_article_video_update"],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["publish", "delete", "tag", "collection"]:
            self.assertNotIn(forbidden, tool_names)

    def test_normalizes_loom_share_and_embed_urls(self):
        self.assertEqual(
            self.module.normalize_loom_embed_url("https://www.loom.com/share/abc12345?sid=ignored"),
            "https://www.loom.com/embed/abc12345",
        )
        self.assertEqual(
            self.module.normalize_loom_embed_url("https://loom.com/embed/abc12345"),
            "https://www.loom.com/embed/abc12345",
        )

    def test_rejects_unsupported_hosts_raw_videos_and_missing_ids(self):
        for bad_url in [
            "https://files.slack.com/files-pri/T123/video.mp4",
            "https://example.com/video.mp4",
            "https://www.loom.com/share/",
            "https://www.youtube.com/watch?v=abc123",
        ]:
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(self.module.LaunchbotHelpArticleError):
                    self.module.normalize_loom_embed_url(bad_url)

    def test_registry_lookup_by_article_hint_and_slot_id(self):
        registry = self.module._load_registry()
        article, slot = self.module._resolve_slot(registry, "Timesheet", "how-timesheet-works-video")
        self.assertEqual(article["article_key"], "web-app-timesheet")
        self.assertEqual(slot["provider"], "loom")

    def test_preview_patches_exact_single_slot_and_preserves_unrelated_html(self):
        fixture = self.fixtures[0]

        def fake_read_article(article_id):
            self.assertEqual(article_id, "3458034")
            return {"id": article_id, "title": "Web App: Timesheet", "body": fixture["body"], "state": "published"}

        with patch.dict(os.environ, {"LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN": "test-token"}, clear=True), patch.object(
            self.module, "_read_intercom_article", side_effect=fake_read_article
        ):
            result = self.module.preview_help_article_video_update(
                "Timesheet",
                "https://www.loom.com/share/timesheetnew001?sid=123",
                "how-timesheet-works-video",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["current_video"], fixture["old_video"])
        self.assertEqual(result["new_video"], fixture["new_video"])
        self.assertFalse(result["will_publish"])
        self.assertIn(fixture["new_video"], result["patch_summary"]["after_html"])
        self.assertNotIn(fixture["old_video"], result["patch_summary"]["after_html"])

    def test_public_article_fixtures_patch_one_registered_loom_block(self):
        for fixture in self.fixtures:
            with self.subTest(article_key=fixture["article_key"]):
                registry = self.module._load_registry()
                article, slot = self.module._resolve_slot(registry, fixture["article_key"], fixture["slot_id"])
                patch_result = self.module._build_video_patch(fixture["body"], article, slot, fixture["new_video"])
                unchanged_marker = {
                    "web-app-timesheet": "After copy stays.",
                    "run-payroll": "Keep this paragraph unchanged.",
                    "general-settings": "Keep this unchanged.",
                }[fixture["article_key"]]

                self.assertIn(fixture["new_video"], patch_result["updated_body"])
                self.assertNotIn(fixture["old_video"], patch_result["updated_body"])
                self.assertEqual(patch_result["updated_body"].count(fixture["new_video"]), 1)
                self.assertIn(unchanged_marker, patch_result["updated_body"])

    def test_blocks_when_anchor_missing_or_duplicated(self):
        registry = self.module._load_registry()
        article, slot = self.module._resolve_slot(registry, "Timesheet", "how-timesheet-works-video")
        with self.assertRaisesRegex(self.module.LaunchbotHelpArticleError, "anchor_text was not found"):
            self.module._build_video_patch("<p>No matching anchor</p>", article, slot, "https://www.loom.com/embed/new123")

        duplicated = (
            "<p>Here's a video of how Timesheet works:</p>"
            "<iframe src=\"https://www.loom.com/embed/old1\"></iframe>"
            "<p>Here's a video of how Timesheet works:</p>"
            "<iframe src=\"https://www.loom.com/embed/old2\"></iframe>"
        )
        with self.assertRaisesRegex(self.module.LaunchbotHelpArticleError, "multiple places"):
            self.module._build_video_patch(duplicated, article, slot, "https://www.loom.com/embed/new123")

    def test_blocks_when_video_block_missing_or_duplicated(self):
        registry = self.module._load_registry()
        article, slot = self.module._resolve_slot(registry, "Timesheet", "how-timesheet-works-video")
        with self.assertRaisesRegex(self.module.LaunchbotHelpArticleError, "No Loom iframe"):
            self.module._build_video_patch(
                "<p>Here's a video of how Timesheet works:</p><h2>Next</h2>",
                article,
                slot,
                "https://www.loom.com/embed/new123",
            )

        duplicated = (
            "<p>Here's a video of how Timesheet works:</p>"
            "<iframe src=\"https://www.loom.com/embed/old1\"></iframe>"
            "<iframe src=\"https://www.loom.com/embed/old2\"></iframe>"
            "<h2>Next</h2>"
        )
        with self.assertRaisesRegex(self.module.LaunchbotHelpArticleError, "Multiple Loom iframes"):
            self.module._build_video_patch(duplicated, article, slot, "https://www.loom.com/embed/new123")

    def test_draft_requires_approval_marker_and_payload_is_always_draft(self):
        fixture = self.fixtures[0]
        captured_payloads = []

        def fake_read_article(article_id):
            return {"id": article_id, "title": "Web App: Timesheet", "body": fixture["body"], "state": "published"}

        def fake_request(method, path, payload=None):
            captured_payloads.append({"method": method, "path": path, "payload": payload})
            return {"id": "3458034", "state": "draft"}

        with patch.dict(
            os.environ,
            {"LAUNCH_STEP3_INTERCOM_ACCESS_TOKEN": "test-token", "LAUNCH_STEP3_INTERCOM_APP_ID": "app123"},
            clear=True,
        ), patch.object(self.module, "_read_intercom_article", side_effect=fake_read_article), patch.object(
            self.module, "_intercom_request", side_effect=fake_request
        ):
            blocked = self.module.create_help_article_video_update_draft("Timesheet", fixture["new_video"], fixture["slot_id"])
            result = self.module.create_help_article_video_update_draft(
                "Timesheet",
                fixture["new_video"],
                fixture["slot_id"],
                approval_marker="draft it",
            )

        self.assertEqual(blocked["confidence"], "blocked")
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["article_state"], "draft")
        self.assertEqual(result["draft_url"], "https://app.intercom.com/a/apps/app123/articles/articles/3458034/show")
        self.assertEqual(captured_payloads[0]["method"], "PUT")
        self.assertEqual(captured_payloads[0]["payload"]["state"], "draft")
        self.assertIn(fixture["new_video"], captured_payloads[0]["payload"]["body"])
        self.assertNotIn("published", json.dumps(captured_payloads[0]["payload"]).lower())


if __name__ == "__main__":
    unittest.main()
