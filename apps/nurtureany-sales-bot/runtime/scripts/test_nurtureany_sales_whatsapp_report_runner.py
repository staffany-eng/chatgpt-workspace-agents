import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("nurtureany_sales_whatsapp_report_runner.py")


def load_module():
    spec = importlib.util.spec_from_file_location("nurtureany_sales_whatsapp_report_runner", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SalesWhatsappReportRunnerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_format_result_starts_with_automation_prefix(self):
        result = {
            "confidence": "verified",
            "answer": {
                "status": "posted",
                "report": {
                    "report_id": "sales-whatsapp-window-report:2026-05-18:test",
                    "countries": ["Indonesia"],
                    "summary": {"owner_country_rows": 2, "target_account_whatsapp_count": 18},
                },
                "delivery": {
                    "delivery_status": "posted",
                    "delivery_channel_id": "C04MSJ1BGF9",
                    "delivery_ts": "1779061460.320679",
                },
            },
        }

        text = self.module.format_result(result, "id-whatsapp-morning-report")

        self.assertTrue(text.startswith("NurtureAny automation: Sales WhatsApp report posted"))
        self.assertIn("Schedule: id-whatsapp-morning-report", text)
        self.assertIn("Countries: Indonesia", text)
        self.assertIn("Delivery: posted", text)

    def test_format_blocked_result_has_safe_caveat(self):
        result = {"confidence": "blocked", "caveat": "delivery channel_id is not allowlisted"}

        text = self.module.format_result(result, "id-whatsapp-morning-report")

        self.assertTrue(text.startswith("NurtureAny automation: Sales WhatsApp report blocked"))
        self.assertIn("Confidence: blocked", text)
        self.assertIn("delivery channel_id is not allowlisted", text)

    def test_dry_run_does_not_render_delivery_fields(self):
        result = {
            "confidence": "verified",
            "answer": {
                "status": "dry_run",
                "report": {
                    "report_id": "sales-whatsapp-window-report:2026-05-18:test",
                    "countries": ["Indonesia"],
                    "summary": {"owner_country_rows": 1, "target_account_whatsapp_count": 0},
                },
            },
        }

        text = self.module.format_result(result, "id-whatsapp-morning-report", dry_run=True)

        self.assertTrue(text.startswith("NurtureAny automation: Sales WhatsApp report dry run"))
        self.assertNotIn("Slack ts:", text)
        self.assertIn("Target-account WhatsApp messages: 0", text)


if __name__ == "__main__":
    unittest.main()
