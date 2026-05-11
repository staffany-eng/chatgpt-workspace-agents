import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

sys.path.insert(0, str(Path(__file__).parent))
from test_helpers import load_mcp_module


def load_eazybe_module():
    return load_mcp_module("eazybe_nurtureany_server.py", "eazybe_nurtureany_server_under_test")


def template_message(message_id="msg-1", phone="+65 9123 4567"):
    return {
        "message_id": message_id,
        "run_id": "run-1",
        "company_id": "company-1",
        "company_name": "Bubble Tea Lab",
        "contact_id": f"contact-{message_id}",
        "recipient_phone": phone,
        "stakeholder_name": "Dana D.",
        "stakeholder_role": "decision_maker",
        "role_confidence": "verified",
        "material": {"material_id": "mat-1", "title": "F&B case", "url": "https://example.com/case"},
        "draft_preview": f"Hi Dana, useful read for Bubble Tea Lab. {phone}",
        "template_payload": {
            "template_name": "nurture_material_share_v1",
            "template_params_schema": ["first_name", "account_name", "material_title", "material_url"],
            "template_params": ["Dana", "Bubble Tea Lab", "F&B case", "https://example.com/case"],
        },
        "eazybe_ready": True,
        "send_status": "pending_approval",
    }


class EazybeNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_eazybe_module()

    def test_send_refuses_without_approval_marker(self):
        result = self.module.send_approved_eazybe_messages(
            "run-1",
            ["msg-1"],
            messages=[template_message()],
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("approval_marker", result["answer"])

    def test_preview_validates_template_param_count_and_redacts_phone(self):
        message = template_message()
        message["template_payload"]["template_params"] = ["Dana"]

        result = self.module.preview_eazybe_template_messages("run-1", ["msg-1"], messages=[message])
        serialized = json.dumps(result)

        self.assertEqual(result["answer"]["invalid_count"], 1)
        self.assertIn("template param count mismatch", result["answer"]["messages"][0]["validation_errors"][0])
        self.assertNotIn("+65 9123 4567", serialized)
        self.assertIn("[redacted-phone]", serialized)

    def test_send_handles_partial_failures(self):
        messages = [template_message("msg-1"), template_message("msg-2")]

        def fake_send(run_id, message):
            if message["message_id"] == "msg-2":
                raise self.module.EazybeError("provider timeout")
            return {"message_id": message["message_id"], "status": "queued", "recipient_ref": message["contact_id"]}

        with patch.object(self.module, "_send_eazybe_message", side_effect=fake_send):
            result = self.module.send_approved_eazybe_messages(
                "run-1",
                ["msg-1", "msg-2"],
                approval_marker="APPROVED-JEREMY",
                messages=messages,
            )

        self.assertEqual(result["answer"]["accepted_or_queued_count"], 1)
        self.assertEqual(result["answer"]["failed_or_blocked_count"], 1)
        statuses = {row["message_id"]: row["status"] for row in result["answer"]["results"]}
        self.assertEqual(statuses["msg-1"], "queued")
        self.assertEqual(statuses["msg-2"], "failed")

    def test_reminder_fires_for_unsent_unskipped_and_tags_ae_and_manager(self):
        messages = [template_message("msg-1"), template_message("msg-2"), template_message("msg-3")]
        messages[2]["skipped"] = True
        statuses = [{"message_id": "msg-1", "status": "queued"}]

        result = self.module.build_daily_nurture_reminder(
            "run-1",
            messages,
            statuses=statuses,
            ae_slack_user_id="UAE123",
            manager_slack_user_id="UMGR123",
            reminder_channel_id="CNU123",
        )

        self.assertTrue(result["answer"]["should_send_reminder"])
        self.assertEqual(result["answer"]["unsent_message_ids"], ["msg-2"])
        self.assertIn("<@UAE123>", result["answer"]["slack_text"])
        self.assertIn("<@UMGR123>", result["answer"]["slack_text"])

    def test_reminder_does_not_fire_for_sent_or_explicitly_skipped(self):
        messages = [template_message("msg-1"), template_message("msg-2")]
        messages[1]["explicitly_skipped"] = True
        statuses = [{"message_id": "msg-1", "status": "accepted"}]

        result = self.module.build_daily_nurture_reminder(
            "run-1",
            messages,
            statuses=statuses,
            ae_slack_user_id="UAE123",
            manager_slack_user_id="UMGR123",
            reminder_channel_id="CNU123",
        )

        self.assertFalse(result["answer"]["should_send_reminder"])
        self.assertEqual(result["answer"]["unsent_message_ids"], [])


if __name__ == "__main__":
    unittest.main()
