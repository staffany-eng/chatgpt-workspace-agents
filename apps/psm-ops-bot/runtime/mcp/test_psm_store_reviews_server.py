from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


APPFOLLOW_REVIEW = {
    "id": "345030591",
    "store": "app_store",
    "ext_id": "1360658903",
    "rating": 3,
    "title": "Missing Store Clock-In Section",
    "content": "The store clock-in section is missing.",
    "author": "staffany user",
    "date": "2026-05-16T10:00:00Z",
    "country": "MY",
    "lang": "en",
    "version": "1.164.0",
}


class PsmStoreReviewsServerTest(unittest.TestCase):
    def setUp(self):
        self.server = load_mcp_module("psm_store_reviews_server.py")
        import store_reviews_core

        self.core = store_reviews_core

    def appfollow_env(self, **extra: str) -> dict[str, str]:
        env = {
            "APPFOLLOW_API_TOKEN": "test-token",
            "APPFOLLOW_EXT_IDS": "1360658903,com.staffany.pixie",
            "APPFOLLOW_COLLECTION_NAME": "",
            "PSM_OPS_APPFOLLOW_CREDENTIALS_FILE": "",
            "APPFOLLOW_CREDENTIALS_FILE": "",
        }
        env.update(extra)
        return env

    def test_tools_are_registered(self):
        tool_names = {tool.__name__ for tool in self.server.mcp.tools}
        self.assertEqual(
            tool_names,
            {
                "list_store_review_apps",
                "list_store_reviews",
                "get_store_review",
                "draft_store_review_reply",
                "suggest_store_review_identity_candidates",
                "confirm_store_review_identity",
            },
        )

    def test_list_apps_reports_appfollow_config(self):
        with patch.dict(os.environ, self.appfollow_env(), clear=False):
            result = self.server.list_store_review_apps()

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["provider"], "appfollow")
        self.assertEqual({app["store"] for app in result["answer"]["apps"]}, {"appfollow"})
        self.assertEqual({app["required_permission"] for app in result["answer"]["apps"]}, {"Read"})

    def test_credentials_file_supports_geocode_style_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "credentials.json"
            path.write_text(
                json.dumps({"appfollow_api_token": "file-token", "ext_ids": ["1360658903"]}),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                self.appfollow_env(APPFOLLOW_API_TOKEN="", PSM_OPS_APPFOLLOW_CREDENTIALS_FILE=str(path), APPFOLLOW_EXT_IDS=""),
                clear=False,
            ):
                credentials = self.core._appfollow_credentials()
                app_refs = self.core._appfollow_app_refs()

        self.assertEqual(credentials["appfollow_api_token"], "file-token")
        self.assertEqual(app_refs, ["1360658903"])

    def test_list_reviews_blocks_without_appfollow_credentials(self):
        with patch.dict(
            os.environ,
            self.appfollow_env(APPFOLLOW_API_TOKEN="", APPFOLLOW_EXT_IDS="", APPFOLLOW_COLLECTION_NAME="", PSM_OPS_APPFOLLOW_CREDENTIALS_FILE="/tmp/missing-appfollow.json"),
            clear=False,
        ):
            result = self.server.list_store_reviews(limit=5, lookback_days=30)

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("AppFollow credentials file is missing", result["caveat"])

    def test_appfollow_response_normalization(self):
        review = self.core.normalize_appfollow_review(APPFOLLOW_REVIEW, "1360658903")

        self.assertEqual(review["store"], "app_store")
        self.assertEqual(review["app_ref"], "1360658903")
        self.assertEqual(review["review_id"], "345030591")
        self.assertEqual(review["rating"], 3)
        self.assertEqual(review["title"], "Missing Store Clock-In Section")
        self.assertEqual(review["body"], "The store clock-in section is missing.")
        self.assertEqual(review["country"], "MY")
        self.assertEqual(review["locale"], "en")

    def test_list_reviews_uses_appfollow_reviews_endpoint(self):
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append({"method": method, "url": url, "params": kwargs.get("params"), "headers": kwargs.get("extra_headers")})
            return {"reviews": [APPFOLLOW_REVIEW]}

        with patch.dict(os.environ, self.appfollow_env(APPFOLLOW_EXT_IDS="1360658903"), clear=False), patch.object(
            self.core, "_request_json", side_effect=fake_request
        ):
            result = self.server.list_store_reviews(limit=5, lookback_days=30)

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["provider"], "appfollow")
        self.assertEqual(result["answer"]["reviews"][0]["review_id"], "345030591")
        self.assertEqual(calls[0]["url"], "https://api.appfollow.io/api/v2/reviews")
        self.assertEqual(calls[0]["headers"]["X-AppFollow-API-Token"], "test-token")
        self.assertEqual(calls[0]["params"]["ext_id"], "1360658903")
        self.assertIn("from", calls[0]["params"])
        self.assertIn("to", calls[0]["params"])

    def test_list_reviews_uses_collection_name_when_configured(self):
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append(kwargs.get("params") or {})
            return {"reviews": [APPFOLLOW_REVIEW]}

        with patch.dict(os.environ, self.appfollow_env(APPFOLLOW_EXT_IDS="", APPFOLLOW_COLLECTION_NAME="staffany-apps"), clear=False), patch.object(
            self.core, "_request_json", side_effect=fake_request
        ):
            result = self.server.list_store_reviews(limit=5, lookback_days=30)

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0]["collection_name"], "staffany-apps")
        self.assertNotIn("ext_id", calls[0])

    def test_get_store_review_uses_appfollow_review_id_filter(self):
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append(kwargs.get("params") or {})
            return {"reviews": [APPFOLLOW_REVIEW]}

        with patch.dict(os.environ, self.appfollow_env(APPFOLLOW_EXT_IDS="1360658903"), clear=False), patch.object(
            self.core, "_request_json", side_effect=fake_request
        ):
            result = self.server.get_store_review(store="app_store", app_ref="1360658903", review_id="345030591")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0]["review_id"], "345030591")
        self.assertEqual(result["answer"]["review"]["review_id"], "345030591")

    def test_appfollow_page_token_must_be_integer(self):
        with patch.dict(os.environ, self.appfollow_env(APPFOLLOW_EXT_IDS="1360658903"), clear=False):
            result = self.server.list_store_reviews(
                store="app_store",
                app_ref="1360658903",
                page_token="https://evil.example/customerReviews?page=2",
                lookback_days=30,
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("page_token", result["caveat"])

    def test_draft_reply_uses_private_support_email_cta_without_public_reference_code(self):
        result = self.server.draft_store_review_reply(
            review={
                "review_id": "345030591",
                "store": "app_store",
                "app_ref": "1360658903",
                "title": "Missing Store Clock-In Section",
                "body": "The store clock-in section is missing.",
            }
        )

        answer_text = result["answer"]["answer_text"]
        self.assertEqual(result["confidence"], "draft")
        self.assertIn("support@staffany.com", answer_text)
        self.assertIn("account email or phone number", answer_text)
        self.assertIn("company/outlet", answer_text)
        self.assertNotIn("REV-", answer_text)
        self.assertIn("not exposed in V1", result["caveat"])

    def test_identity_candidate_unknown_without_private_claim(self):
        result = self.server.suggest_store_review_identity_candidates(
            review={"store": "app_store", "app_ref": "1360658903", "review_id": "345030591"}
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "unknown")
        self.assertIn("identity_requested_private", result["answer"]["internal_labels"])
        self.assertIn("support@staffany.com", result["answer"]["public_reply_cta"])

    def test_confirm_identity_stores_redacted_runtime_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = str(Path(tmpdir) / "store_reviews.json")
            result = self.server.confirm_store_review_identity(
                review={"store": "app_store", "app_ref": "1360658903", "review_id": "345030591"},
                customer_key="customer-123",
                customer_name="Example Cafe Pte Ltd",
                contact_email="ops@example.com",
                contact_phone="+65 9123 4567",
                confirmation_text="Kai Yi confirmed via support follow-up from ops@example.com / +65 9123 4567",
                confirmed_by="kaiyi@staffany.com",
                state_path=state_path,
            )
            state = self.core.load_state(state_path)

        self.assertEqual(result["confidence"], "verified")
        key = "app_store:1360658903:345030591"
        self.assertEqual(result["answer"]["review_key"], key)
        stored = state["identity_confirmations"][key]
        self.assertEqual(stored["contact_email"], "op***@example.com")
        self.assertEqual(stored["contact_phone"], "[redacted-phone:4567]")
        self.assertNotIn("ops@example.com", stored["confirmation_text"])
        self.assertNotIn("9123 4567", stored["confirmation_text"])

    def test_state_key_prevents_duplicate_triage_until_review_changes(self):
        review = {
            "store": "app_store",
            "app_ref": "1360658903",
            "review_id": "345030591",
            "rating": 3,
            "title": "Missing Store Clock-In Section",
            "body": "The store clock-in section is missing.",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = str(Path(tmpdir) / "store_reviews.json")
            self.assertFalse(self.core.already_triaged(review, state_path=state_path))
            stored = self.core.mark_triaged(review, slack_thread_url="https://staffany.slack.com/archives/C/p1", state_path=state_path)
            self.assertEqual(stored["key"], "app_store:1360658903:345030591")
            self.assertTrue(self.core.already_triaged(review, state_path=state_path))
            changed = {**review, "body": "Clock-in is still missing."}
            self.assertFalse(self.core.already_triaged(changed, state_path=state_path))

    def test_slack_triage_text_unknown_reviewer_action(self):
        review = self.core.normalize_appfollow_review(APPFOLLOW_REVIEW, "1360658903")
        text = self.core.build_slack_triage_text(review)

        self.assertIn("PSM Ops automation: Store review triage", text)
        self.assertIn("identity_requested_private", text)
        self.assertIn("support@staffany.com", text)
        self.assertIn("Public store reply publishing is not enabled in V1", text)
        self.assertIn("Internal correlation: app_store:1360658903:345030591", text)


if __name__ == "__main__":
    unittest.main()
