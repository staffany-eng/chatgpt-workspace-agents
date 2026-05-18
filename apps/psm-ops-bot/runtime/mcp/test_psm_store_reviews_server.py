from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


GOOGLE_REVIEW = {
    "reviewId": "gp-review-1",
    "authorName": "Reviewer",
    "comments": [
        {
            "userComment": {
                "text": "Clock in is missing from my store.",
                "starRating": 2,
                "reviewerLanguage": "en",
                "appVersionName": "1.2.3",
                "lastModified": {"seconds": "1778960645"},
            }
        }
    ],
}

APP_STORE_REVIEW = {
    "id": "345030591",
    "type": "customerReviews",
    "attributes": {
        "rating": 3,
        "title": "Missing Store Clock-In Section",
        "body": "The store clock-in section is missing.",
        "reviewerNickname": "staffany user",
        "createdDate": "2026-05-16T10:00:00Z",
        "territory": "MY",
        "appVersionString": "1.164.0",
    },
}


class PsmStoreReviewsServerTest(unittest.TestCase):
    def setUp(self):
        self.server = load_mcp_module("psm_store_reviews_server.py")
        import store_reviews_core

        self.core = store_reviews_core

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

    def test_list_apps_reports_direct_store_config(self):
        result = self.server.list_store_review_apps()

        self.assertEqual(result["confidence"], "verified")
        stores = {app["store"] for app in result["answer"]["apps"]}
        self.assertEqual(stores, {"google_play", "app_store"})
        self.assertIn("androidpublisher", result["answer"]["apps"][0]["required_scope"])

    def test_google_play_response_normalization(self):
        review = self.core.normalize_google_play_review(GOOGLE_REVIEW, "com.staffany.pixie")

        self.assertEqual(review["store"], "google_play")
        self.assertEqual(review["app_ref"], "com.staffany.pixie")
        self.assertEqual(review["review_id"], "gp-review-1")
        self.assertEqual(review["rating"], 2)
        self.assertEqual(review["body"], "Clock in is missing from my store.")
        self.assertEqual(review["locale"], "en")
        self.assertEqual(review["app_version"], "1.2.3")
        self.assertEqual(review["reply_status"], "no_reply")

    def test_app_store_response_normalization(self):
        review = self.core.normalize_app_store_review(APP_STORE_REVIEW, "1360658903")

        self.assertEqual(review["store"], "app_store")
        self.assertEqual(review["app_ref"], "1360658903")
        self.assertEqual(review["review_id"], "345030591")
        self.assertEqual(review["rating"], 3)
        self.assertEqual(review["title"], "Missing Store Clock-In Section")
        self.assertEqual(review["country"], "MY")
        self.assertEqual(review["app_version"], "1.164.0")

    def test_get_store_review_uses_google_play_get_endpoint(self):
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            return GOOGLE_REVIEW

        with patch.object(self.core, "google_play_access_token", return_value="token"), patch.object(
            self.core, "_request_json", side_effect=fake_request
        ):
            result = self.server.get_store_review(store="google_play", app_ref="com.staffany.pixie", review_id="gp-review-1")

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("/applications/com.staffany.pixie/reviews/gp-review-1", calls[0][1])
        self.assertEqual(result["answer"]["review"]["review_id"], "gp-review-1")

    def test_get_store_review_uses_app_store_get_endpoint(self):
        calls = []

        def fake_request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            return {"data": APP_STORE_REVIEW}

        with patch.object(self.core, "app_store_connect_token", return_value="token"), patch.object(
            self.core, "_request_json", side_effect=fake_request
        ):
            result = self.server.get_store_review(store="app_store", app_ref="1360658903", review_id="345030591")

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("/customerReviews/345030591", calls[0][1])
        self.assertEqual(result["answer"]["review"]["review_id"], "345030591")

    def test_list_reviews_normalizes_both_store_payloads(self):
        def fake_request(method, url, **kwargs):
            if "androidpublisher" in url:
                return {"reviews": [GOOGLE_REVIEW]}
            return {"data": [APP_STORE_REVIEW]}

        with patch.object(self.core, "google_play_access_token", return_value="token"), patch.object(
            self.core, "app_store_connect_token", return_value="token"
        ), patch.object(self.core, "_request_json", side_effect=fake_request):
            result = self.server.list_store_reviews(limit=5, lookback_days=30)

        self.assertEqual(result["confidence"], "verified")
        reviews = result["answer"]["reviews"]
        self.assertEqual({review["store"] for review in reviews}, {"google_play", "app_store"})

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
        self.assertIn("Never ask the reviewer to post email or phone", result["caveat"])

    def test_identity_candidate_unknown_without_private_claim(self):
        result = self.server.suggest_store_review_identity_candidates(
            review={"store": "app_store", "app_ref": "1360658903", "review_id": "345030591"}
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "unknown")
        self.assertIn("identity_requested_private", result["answer"]["internal_labels"])
        self.assertIn("support@staffany.com", result["answer"]["public_reply_cta"])

    def test_identity_candidate_exact_email_match_is_verified(self):
        result = self.server.suggest_store_review_identity_candidates(
            review={"store": "app_store", "app_ref": "1360658903", "review_id": "345030591"},
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
        candidate = result["answer"]["candidates"][0]
        self.assertEqual(candidate["match_type"], "exact_email")
        self.assertEqual(candidate["confidence"], "verified")
        self.assertEqual(candidate["contact"]["email"], "op***@example.com")

    def test_identity_candidate_phone_only_is_needs_check(self):
        result = self.server.suggest_store_review_identity_candidates(
            review={"store": "app_store", "app_ref": "1360658903", "review_id": "345030591"},
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
        candidate = result["answer"]["candidates"][0]
        self.assertEqual(candidate["match_type"], "phone")
        self.assertEqual(candidate["confidence"], "needs-check")
        self.assertEqual(candidate["contact"]["phone"], "[redacted-phone:4567]")

    def test_identity_candidate_company_only_is_needs_check(self):
        result = self.server.suggest_store_review_identity_candidates(
            review={"store": "app_store", "app_ref": "1360658903", "review_id": "345030591"},
            company_or_outlet="Example Cafe",
            c360_candidates=[{"customerKey": "customer-123", "companyName": "Example Cafe Pte Ltd"}],
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "candidate")
        self.assertEqual(result["answer"]["candidates"][0]["match_type"], "company_or_outlet")

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
        review = self.core.normalize_app_store_review(APP_STORE_REVIEW, "1360658903")
        text = self.core.build_slack_triage_text(review)

        self.assertIn("PSM Ops automation: Store review triage", text)
        self.assertIn("identity_requested_private", text)
        self.assertIn("support@staffany.com", text)
        self.assertIn("Public store reply publishing is not enabled in V1", text)
        self.assertIn("Internal correlation: app_store:1360658903:345030591", text)


if __name__ == "__main__":
    unittest.main()
