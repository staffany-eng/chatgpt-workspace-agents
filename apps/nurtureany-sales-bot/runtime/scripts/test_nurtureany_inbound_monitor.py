from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().with_name("nurtureany_inbound_monitor.py")
SPEC = importlib.util.spec_from_file_location("nurtureany_inbound_monitor", MODULE_PATH)
monitor = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(monitor)


AS_OF = datetime(2026, 5, 17, 4, 20, tzinfo=timezone.utc)


def _result(rows, duplicate_summary=None, confidence="needs-check"):
    return {
        "answer": {
            "audit_rows": rows,
            "duplicate_summary": duplicate_summary or [],
            "will_mutate_hubspot": False,
            "external_message_sending": False,
        },
        "source": "HubSpot Conversations, HubSpot CRM activity, and supplied safe Slack alert metadata",
        "confidence": confidence,
        "caveat": "Read-only audit. No HubSpot mutation or external message send was performed.",
    }


def _row(**overrides):
    row = {
        "alert_id": "hubspot:thread-1",
        "hubspot_thread_id": "thread-1",
        "alert_time": "2026-05-17T04:00:00Z",
        "assigned_owner": "jeremy.wong@staffany.com",
        "first_customer_touch_time": "",
        "first_touch_source": "missing",
        "sla_status": "miss",
        "first_touch_sla_status": "miss",
        "ack_sla_status": "needs-check",
        "duplicate_group": "thread:thread-1",
        "lead_context": {
            "company_name": "Noci Bakehouse",
            "contact_role": "Owner",
            "email_domain": "noci.example",
            "context_status": "provided",
        },
        "hubspot_gaps": [],
        "hubspot_context": {
            "companies": [
                {
                    "company_id": "company-1",
                    "name": "Noci Bakehouse",
                    "account_status": "prospect",
                }
            ]
        },
    }
    row.update(overrides)
    return row


class InboundMonitorTest(unittest.TestCase):
    def test_new_hubspot_inbound_without_touch_posts_action_row(self):
        actions = monitor.action_rows_from_result(_result([_row()]), AS_OF)
        self.assertEqual(len(actions), 1)
        self.assertIn("Status: stale", actions[0]["line"])
        self.assertIn("manager chase or manually reassign now", actions[0]["line"])

    def test_inbound_replied_within_sla_stays_silent(self):
        actions = monitor.action_rows_from_result(
            _result(
                [
                    _row(
                        first_customer_touch_time="2026-05-17T04:04:00Z",
                        first_touch_source="hubspot_conversations_outbound",
                        sla_status="pass",
                        first_touch_sla_status="pass",
                    )
                ],
                confidence="verified",
            ),
            AS_OF,
        )
        self.assertEqual(actions, [])

    def test_existing_customer_is_flagged_as_customer_routing(self):
        actions = monitor.action_rows_from_result(
            _result(
                [
                    _row(
                        hubspot_context={
                            "companies": [
                                {
                                    "company_id": "company-customer",
                                    "name": "Existing Customer",
                                    "account_status": "customer",
                                }
                            ]
                        }
                    )
                ]
            ),
            AS_OF,
        )
        self.assertIn("Status: customer", actions[0]["line"])
        self.assertIn("support/CSM check", actions[0]["line"])

    def test_candidate_duplicate_visible_without_merging_unknowns(self):
        result = _result(
            [
                _row(alert_id="a-1", hubspot_thread_id="thread-1", duplicate_group="contact:contact-1"),
                _row(alert_id="a-2", hubspot_thread_id="thread-2", duplicate_group="contact:contact-1"),
                _row(alert_id="a-3", hubspot_thread_id="", duplicate_group="needs-check"),
            ],
            duplicate_summary=[
                {"duplicate_group": "contact:contact-1", "alert_count": 2},
                {"duplicate_group": "needs-check", "alert_count": 1},
            ],
        )
        actions = monitor.action_rows_from_result(result, AS_OF)
        duplicate_lines = [action["line"] for action in actions if "Status: duplicate" in action["line"]]
        self.assertEqual(len(duplicate_lines), 2)
        self.assertNotIn("Status: duplicate", actions[-1]["line"])

    def test_missing_context_returns_needs_check_action_without_inventing(self):
        actions = monitor.action_rows_from_result(
            _result(
                [
                    _row(
                        first_customer_touch_time="2026-05-17T04:04:00Z",
                        first_touch_source="hubspot_conversations_outbound",
                        sla_status="pass",
                        first_touch_sla_status="pass",
                        lead_context={"context_status": "missing"},
                        hubspot_gaps=["missing company", "missing current tools", "missing buying role"],
                    )
                ]
            ),
            AS_OF,
        )
        self.assertEqual(len(actions), 1)
        self.assertIn("Status: touched", actions[0]["line"])
        self.assertIn("complete clean-lead context", actions[0]["line"])

    def test_report_omits_raw_phone_email_and_message_body(self):
        result = _result(
            [
                _row(
                    lead_context={
                        "company_name": "Noci Bakehouse",
                        "contact_role": "Owner",
                        "email_domain": "buyer.example",
                        "phone_hint": "masked_last4:1234",
                        "summary": "Customer asked for payroll. Raw phone +6599999999 should not print.",
                        "context_status": "provided",
                    }
                )
            ]
        )
        actions = monitor.action_rows_from_result(result, AS_OF)
        report = monitor.format_report(result, actions, {"notified_keys": []}, dry_run=True)
        self.assertIn("NurtureAny automation: HubSpot inbound monitor DRY RUN", report)
        self.assertNotIn("+6599999999", report)
        self.assertNotIn("buyer@", report)
        self.assertNotIn("Customer asked for payroll", report)


if __name__ == "__main__":
    unittest.main()
