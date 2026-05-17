from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


def sample_slack_alert() -> dict:
    return {
        "ts": "1778960645.409259",
        "bot_id": "BAPPFOLLOW",
        "attachments": [
            {
                "pretext": "App Store review for StaffAny",
                "text": ":star::star::star: MY v1.164.0\n*Missing Store Clock-In Section*\nThe store clock-in section is missing.",
                "fields": [
                    {"title": "review_id", "value": "345030591"},
                    {"title": "AppFollow", "value": "https://app.appfollow.io/apps/customer-support/reviews/518927?review_id=345030591"},
                ],
            }
        ],
    }


class PsmAppFollowServerTest(unittest.TestCase):
    def setUp(self):
        self.server = load_mcp_module("psm_appfollow_server.py")
        import appfollow_reviews_core

        self.core = appfollow_reviews_core

    def test_tools_are_registered(self):
        tool_names = {tool.__name__ for tool in self.server.mcp.tools}
        self.assertEqual(
            tool_names,
            {
                "list_appfollow_apps",
                "get_appfollow_review",
                "tag_appfollow_review",
                "draft_appfollow_reply",
                "suggest_appfollow_review_identity_candidates",
                "confirm_appfollow_review_identity",
                "publish_appfollow_reply_after_approval",
            },
        )

    def test_list_apps_uses_account_apps_endpoint(self):
        calls = []

        def fake_request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return {"apps": [{"name": "StaffAny"}, {"name": "StaffAny Manager"}]}

        with patch.dict(os.environ, {"APPFOLLOW_API_TOKEN": "token"}, clear=False), patch.object(
            self.core, "request_json", side_effect=fake_request
        ):
            result = self.server.list_appfollow_apps()

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls, [("GET", "/account/apps", {})])
        self.assertEqual(len(result["answer"]["apps"]), 2)

    def test_missing_token_blocks_without_calling_api(self):
        with patch.dict(os.environ, {"APPFOLLOW_API_TOKEN": ""}, clear=False), patch.object(
            self.core.urllib.request, "urlopen", side_effect=AssertionError("should not call network")
        ):
            result = self.server.list_appfollow_apps()

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("APPFOLLOW_API_TOKEN", result["answer"]["message"])

    def test_get_review_requires_ext_id_or_collection_name(self):
        with patch.object(self.core, "request_json", side_effect=AssertionError("should not call API")):
            result = self.server.get_appfollow_review(review_id="345030591")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("ext_id or collection_name", result["answer"]["message"])

    def test_get_known_review_uses_bounded_query(self):
        calls = []

        def fake_request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return {"reviews": [{"review_id": "345030591"}]}

        with patch.object(self.core, "request_json", side_effect=fake_request):
            result = self.server.get_appfollow_review(ext_id="1038369065", review_id="345030591")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "GET")
        self.assertEqual(calls[0][1], "/reviews")
        params = calls[0][2]["params"]
        self.assertEqual(params["ext_id"], "1038369065")
        self.assertEqual(params["review_id"], "345030591")
        self.assertIn("from", params)
        self.assertIn("to", params)

    def test_tag_update_is_preview_first(self):
        with patch.object(self.core, "request_json", side_effect=AssertionError("should not call API")):
            result = self.server.tag_appfollow_review(
                ext_id="1038369065",
                review_id="345030591",
                tags=["psm-ops-triage", "psm-ops-triage"],
            )

        self.assertEqual(result["confidence"], "preview")
        self.assertEqual(result["answer"]["would_post"]["tags"], "psm-ops-triage")

    def test_tag_update_apply_posts_tags(self):
        calls = []

        def fake_request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return {"ok": True}

        with patch.object(self.core, "request_json", side_effect=fake_request):
            result = self.server.tag_appfollow_review(
                ext_id="1038369065",
                review_id="345030591",
                tags="psm-ops-triage",
                apply=True,
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "POST")
        self.assertEqual(calls[0][1], "/reviews/tags")
        self.assertEqual(calls[0][2]["body"]["tags"], "psm-ops-triage")

    def test_draft_reply_uses_private_support_email_cta_without_public_reference_code(self):
        result = self.server.draft_appfollow_reply(
            review={
                "review_id": "345030591",
                "store": "app_store",
                "ext_id": "1038369065",
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
        self.assertIn("Never ask the reviewer to post email or phone", result["caveat"])

    def test_identity_candidate_unknown_without_private_claim(self):
        result = self.server.suggest_appfollow_review_identity_candidates(
            review={"store": "app_store", "ext_id": "1038369065", "review_id": "345030591"}
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "unknown")
        self.assertIn("identity_requested_private", result["answer"]["suggested_tags"])
        self.assertIn("support@staffany.com", result["answer"]["public_reply_cta"])

    def test_identity_candidate_exact_email_match_is_verified(self):
        result = self.server.suggest_appfollow_review_identity_candidates(
            review={"store": "app_store", "ext_id": "1038369065", "review_id": "345030591"},
            email="ops@example.com",
            company_or_outlet="Example Cafe",
            c360_candidates=[
                {
                    "customerKey": "customer-123",
                    "companyName": "Example Cafe Pte Ltd",
                    "contacts": [{"email": "ops@example.com", "phone": "+65 9123 4567"}],
                }
            ],
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["status"], "verified")
        self.assertIn("identity_candidate", result["answer"]["suggested_tags"])
        candidate = result["answer"]["candidates"][0]
        self.assertEqual(candidate["match_type"], "exact_email")
        self.assertEqual(candidate["confidence"], "verified")
        self.assertEqual(candidate["contact"]["email"], "op***@example.com")

    def test_identity_candidate_phone_only_is_needs_check(self):
        result = self.server.suggest_appfollow_review_identity_candidates(
            review={"store": "app_store", "ext_id": "1038369065", "review_id": "345030591"},
            phone="+65 9123 4567",
            c360_candidates=[
                {
                    "customerKey": "customer-123",
                    "companyName": "Example Cafe Pte Ltd",
                    "contacts": [{"phone": "+65 9123 4567"}],
                }
            ],
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "candidate")
        self.assertIn("identity_candidate", result["answer"]["suggested_tags"])
        candidate = result["answer"]["candidates"][0]
        self.assertEqual(candidate["match_type"], "phone")
        self.assertEqual(candidate["confidence"], "needs-check")
        self.assertEqual(candidate["contact"]["phone"], "[redacted-phone:4567]")

    def test_identity_candidate_company_only_is_needs_check(self):
        result = self.server.suggest_appfollow_review_identity_candidates(
            review={"store": "app_store", "ext_id": "1038369065", "review_id": "345030591"},
            company_or_outlet="Example Cafe",
            c360_candidates=[{"customerKey": "customer-123", "companyName": "Example Cafe Pte Ltd"}],
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "candidate")
        self.assertEqual(result["answer"]["candidates"][0]["match_type"], "company_or_outlet")

    def test_confirm_identity_stores_redacted_runtime_mapping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = str(Path(tmpdir) / "appfollow_reviews.json")
            result = self.server.confirm_appfollow_review_identity(
                review={"store": "app_store", "ext_id": "1038369065", "review_id": "345030591"},
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
        key = "app_store:1038369065:345030591"
        self.assertEqual(result["answer"]["review_key"], key)
        stored = state["identity_confirmations"][key]
        self.assertEqual(stored["contact_email"], "op***@example.com")
        self.assertEqual(stored["contact_phone"], "[redacted-phone:4567]")
        self.assertNotIn("ops@example.com", stored["confirmation_text"])
        self.assertNotIn("9123 4567", stored["confirmation_text"])

    def test_publish_reply_requires_approval_and_feature_flag(self):
        with patch.object(self.core, "request_json", side_effect=AssertionError("should not call API")):
            blocked = self.server.publish_appfollow_reply_after_approval(
                ext_id="1038369065",
                review_id="345030591",
                answer_text="Thanks for flagging this.",
                approval_text="looks ok",
            )
            disabled = self.server.publish_appfollow_reply_after_approval(
                ext_id="1038369065",
                review_id="345030591",
                answer_text="Thanks for flagging this.",
                approval_text="post reply",
            )

        self.assertEqual(blocked["confidence"], "blocked")
        self.assertIn("post reply", blocked["answer"]["message"])
        self.assertEqual(disabled["confidence"], "blocked")
        self.assertIn("disabled", disabled["answer"]["message"])

    def test_publish_reply_after_approval_posts_when_enabled(self):
        calls = []

        def fake_request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            return {"status": "ok"}

        with patch.dict(os.environ, {"PSM_OPS_APPFOLLOW_REPLY_PUBLISH_ENABLED": "true"}, clear=False), patch.object(
            self.core, "request_json", side_effect=fake_request
        ):
            result = self.server.publish_appfollow_reply_after_approval(
                ext_id="1038369065",
                review_id="345030591",
                answer_text="Thanks for flagging this.",
                approval_text="post reply",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "POST")
        self.assertEqual(calls[0][1], "/reviews/reply")
        self.assertEqual(calls[0][2]["body"]["answer_text"], "Thanks for flagging this.")

    def test_slack_alert_parser_and_classifier(self):
        with patch.dict(os.environ, {"PSM_OPS_APPFOLLOW_APP_EXT_IDS": '{"app_store:staffany":"1038369065"}'}, clear=False):
            extracted = self.core.extract_appfollow_review_from_slack_message(sample_slack_alert())

        self.assertEqual(extracted["review_id"], "345030591")
        self.assertEqual(extracted["apps_id"], "518927")
        self.assertEqual(extracted["ext_id"], "1038369065")
        self.assertEqual(extracted["store"], "app_store")
        self.assertEqual(extracted["rating"], 3)
        self.assertEqual(extracted["country"], "MY")
        self.assertIn("Missing Store Clock-In Section", extracted["title"])
        classification = self.core.classify_appfollow_review(extracted)
        self.assertEqual(classification["theme"], "clock_in")
        self.assertEqual(classification["severity"], "high")

    def test_slack_alert_parser_supports_default_collection_name(self):
        env = {
            "PSM_OPS_APPFOLLOW_APP_EXT_IDS": "",
            "PSM_OPS_APPFOLLOW_DEFAULT_EXT_ID": "",
            "PSM_OPS_APPFOLLOW_DEFAULT_COLLECTION_NAME": "Main",
        }
        with patch.dict(os.environ, env, clear=False):
            extracted = self.core.extract_appfollow_review_from_slack_message(sample_slack_alert())

        self.assertEqual(extracted["review_id"], "345030591")
        self.assertEqual(extracted["ext_id"], "")
        self.assertEqual(extracted["collection_name"], "Main")
        self.assertEqual(extracted["dedupe_key"], "app_store:Main:345030591")

    def test_state_key_prevents_duplicate_triage(self):
        review = {
            "store": "app_store",
            "ext_id": "1038369065",
            "review_id": "345030591",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = str(Path(tmpdir) / "appfollow_reviews.json")
            self.assertFalse(self.core.already_triaged(review, state_path=state_path))
            stored = self.core.mark_triaged(review, slack_thread_url="https://staffany.slack.com/archives/C/p1", state_path=state_path)
            self.assertEqual(stored["key"], "app_store:1038369065:345030591")
            self.assertTrue(self.core.already_triaged(review, state_path=state_path))


if __name__ == "__main__":
    unittest.main()
