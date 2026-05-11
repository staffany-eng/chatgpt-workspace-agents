import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


def load_writer_module():
    module_name = "near_me_outlet_match_writer_under_test"
    path = Path(__file__).with_name("near_me_outlet_match_writer.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NearMeOutletMatchWriterTest(unittest.TestCase):
    def setUp(self):
        self.module = load_writer_module()
        self.env_patch = patch.dict(
            os.environ,
            {
                "NURTUREANY_ACCESS_POLICY_PATH": "",
                "NURTUREANY_OUTLET_MATCHES_TABLE": "",
            },
        )
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()

    def payload(self, **overrides):
        row = {
            "area_id": "sg_raffles_place",
            "outlet_name": "Example Bistro Raffles",
            "google_place_id": "places/example",
            "formatted_address": "1 Raffles Place, Singapore",
            "hubspot_company_id": "12345",
            "hubspot_company_name": "Example Bistro",
            "organisation_id": "org-123",
            "account_status": "customer",
            "match_status": "confirmed",
            "confidence": "verified",
            "source": "workflow",
        }
        row.update(overrides.pop("row", {}))
        payload = {
            "approved_by_email": "kaiyi@staffany.com",
            "approval_marker": "slack-thread-approval-1",
            "matches": [row],
        }
        payload.update(overrides)
        return payload

    def test_admin_payload_builds_bounded_merge_sql(self):
        rows = self.module.validate_payload(self.payload())
        sql = self.module.build_merge_sql(rows)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reviewed_by"], "kaiyi@staffany.com")
        self.assertIn("MERGE `staffany-warehouse.analytics.nurtureany_near_me_outlet_matches`", sql)
        self.assertIn("Slack-approved manager/admin review", sql)
        self.assertIn("'sg_raffles_place' AS area_id", sql)
        self.assertIn("'confirmed' AS match_status", sql)
        self.assertIn("WHEN MATCHED THEN UPDATE SET", sql)

    def test_admin_alias_payload_canonicalizes_reviewer_email(self):
        rows = self.module.validate_payload(self.payload(approved_by_email="leekai.yi@staffany.com"))

        self.assertEqual(rows[0]["reviewed_by"], "kaiyi@staffany.com")

    def test_singapore_manager_can_approve(self):
        rows = self.module.validate_payload(self.payload(approved_by_email="kerren.fong@staffany.com"))

        self.assertEqual(rows[0]["reviewed_by"], "kerren.fong@staffany.com")

    def test_non_singapore_manager_is_blocked(self):
        with self.assertRaisesRegex(self.module.ValidationError, "configured admin or Singapore-scoped manager"):
            self.module.validate_payload(self.payload(approved_by_email="sarah@staffany.com"))

    def test_google_only_row_without_account_link_is_blocked(self):
        with self.assertRaisesRegex(self.module.ValidationError, "HubSpot company or StaffAny organisation"):
            self.module.validate_payload(
                self.payload(row={"hubspot_company_id": "", "organisation_id": "", "account_status": "unknown"})
            )

    def test_unknown_area_and_non_confirmed_status_are_blocked(self):
        with self.assertRaisesRegex(self.module.ValidationError, "Unknown area_id"):
            self.module.validate_payload(self.payload(row={"area_id": "sg_unknown"}))

        with self.assertRaisesRegex(self.module.ValidationError, "match_status must be confirmed"):
            self.module.validate_payload(self.payload(row={"match_status": "candidate"}))


if __name__ == "__main__":
    unittest.main()
