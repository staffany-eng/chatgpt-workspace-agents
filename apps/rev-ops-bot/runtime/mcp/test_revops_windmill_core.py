from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import revops_windmill_core as core


class FakeResponse:
    def __init__(self, body: object):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class RevOpsWindmillCoreTest(unittest.TestCase):
    def setUp(self):
        self.env = {
            "REVOPS_WINDMILL_BASE_URL": "https://mill.staffany.net/",
            "REVOPS_WINDMILL_WORKSPACE_ID": "staffany",
            "REVOPS_WINDMILL_TOKEN": "test-token",
        }

    def test_check_config_redacts_token(self):
        with patch.dict(os.environ, self.env, clear=True):
            result = core.check_windmill_revops_config()
        self.assertTrue(result["ok"])
        self.assertEqual(result["base_url"], "https://mill.staffany.net")
        self.assertTrue(result["token_configured"])
        self.assertNotIn("test-token", json.dumps(result))

    def test_preview_forces_dry_run(self):
        calls = []

        def fake_urlopen(req, timeout):
            calls.append((req, json.loads(req.data.decode("utf-8"))))
            return FakeResponse({"ok": True, "status": "preview"})

        request_payload = {
            "requestId": "req-1",
            "approval": {"status": "approved", "confirmationText": "create sub deal"},
        }
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", fake_urlopen):
            result = core.preview_create_sub_deal_and_service_agreement(request_payload)

        self.assertEqual(result["status"], "preview")
        self.assertEqual(calls[0][1]["request"], request_payload)
        self.assertTrue(calls[0][1]["dry_run"])
        self.assertIn(
            "/api/w/staffany/jobs/run_wait_result/p/f/rev_ops/create_sub_deal_and_service_agreement",
            calls[0][0].full_url,
        )
        self.assertEqual(calls[0][0].headers["Authorization"], "Bearer test-token")

    def test_apply_preflight_updates_uses_requested_dry_run_flag(self):
        calls = []

        def fake_urlopen(req, timeout):
            calls.append((req, json.loads(req.data.decode("utf-8"))))
            return FakeResponse({"ok": True, "status": "completed"})

        request_payload = {
            "updateProposals": [
                {
                    "objectType": "deal",
                    "objectId": "123",
                    "property": "billing_automation_owner",
                    "currentValue": None,
                    "proposedValue": "billing_engine",
                    "reason": "required",
                }
            ],
            "approval": {"status": "approved", "approvedBy": "U123"},
        }
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", fake_urlopen):
            result = core.apply_preflight_updates(request_payload, dry_run=False)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(calls[0][1]["request"], request_payload)
        self.assertFalse(calls[0][1]["dry_run"])
        self.assertIn(
            "/api/w/staffany/jobs/run_wait_result/p/f/rev_ops/apply_preflight_updates",
            calls[0][0].full_url,
        )

    def test_execute_create_sub_deal_forces_live_run(self):
        calls = []

        def fake_urlopen(req, timeout):
            calls.append((req, json.loads(req.data.decode("utf-8"))))
            return FakeResponse({"ok": True, "status": "completed"})

        request_payload = {
            "requestId": "req-1",
            "approval": {"status": "approved", "confirmationText": "create sub deal"},
        }
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", fake_urlopen):
            result = core.execute_create_sub_deal_and_service_agreement(request_payload)

        self.assertEqual(result["status"], "completed")
        self.assertEqual(calls[0][1]["request"], request_payload)
        self.assertFalse(calls[0][1]["dry_run"])
        self.assertIn(
            "/api/w/staffany/jobs/run_wait_result/p/f/rev_ops/create_sub_deal_and_service_agreement",
            calls[0][0].full_url,
        )

    def test_search_uses_windmill_search_script(self):
        calls = []

        def fake_urlopen(req, timeout):
            calls.append((req, json.loads(req.data.decode("utf-8"))))
            return FakeResponse({"ok": True, "data": {"items": []}})

        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", fake_urlopen):
            result = core.search_billing_main_deals("Acme", limit=1)

        self.assertTrue(result["ok"])
        self.assertEqual(calls[0][1]["search"], "Acme")
        self.assertEqual(calls[0][1]["limit"], 1)
        self.assertIn(
            "/api/w/staffany/jobs/run_wait_result/p/f/rev_ops/search_billing_main_deals",
            calls[0][0].full_url,
        )

    def test_preflight_uses_windmill_preflight_script(self):
        calls = []

        def fake_urlopen(req, timeout):
            calls.append((req, json.loads(req.data.decode("utf-8"))))
            return FakeResponse({"ok": True, "status": "ready"})

        request_payload = {
            "hubspotDealUrlOrId": "316899066558",
            "contacts": [{"email": "signer@example.com"}],
        }
        with patch.dict(os.environ, self.env, clear=True), patch("urllib.request.urlopen", fake_urlopen):
            result = core.preflight_create_sub_deal_request(request_payload)

        self.assertEqual(result["status"], "ready")
        self.assertEqual(calls[0][1]["request"], request_payload)
        self.assertIn(
            "/api/w/staffany/jobs/run_wait_result/p/f/rev_ops/preflight_create_sub_deal_request",
            calls[0][0].full_url,
        )

    def test_invalid_json_returns_structured_error(self):
        result = core.preview_create_sub_deal_and_service_agreement_json("{bad json")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid_json")

    def test_preflight_invalid_json_returns_structured_error(self):
        result = core.preflight_create_sub_deal_request_json("{bad json")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid_json")


if __name__ == "__main__":
    unittest.main()
