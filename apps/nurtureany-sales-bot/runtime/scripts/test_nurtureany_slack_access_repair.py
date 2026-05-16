import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_module():
    path = Path(__file__).with_name("nurtureany_slack_access_repair.py")
    spec = importlib.util.spec_from_file_location("nurtureany_slack_access_repair_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class SlackAccessRepairTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_policy_emails_include_event_operators_and_active_reps_only(self):
        policy = {
            "event_operators": [{"email": "jan-e@staffany.com", "countries": ["Singapore"]}],
            "sales_reps": [
                {"slack_email": "active.rep@staffany.com", "hubspot_owner_email": "owner@staffany.com", "active": True},
                {"slack_email": "disabled.rep@staffany.com", "hubspot_owner_email": "disabled.owner@staffany.com", "active": False},
            ],
            "disabled": [{"email": "sarah@staffany.com"}],
        }

        emails = self.module.access_policy_emails(policy)

        self.assertIn("jan-e@staffany.com", emails)
        self.assertIn("active.rep@staffany.com", emails)
        self.assertIn("kaiyi@staffany.com", emails)
        self.assertNotIn("disabled.rep@staffany.com", emails)
        self.assertNotIn("sarah@staffany.com", emails)

    def test_update_dotenv_replaces_only_slack_allowed_users(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("SLACK_BOT_TOKEN=fake-slack-token\nSLACK_ALLOWED_USERS=UOLD\nOTHER=value\n", encoding="utf-8")

            backup = self.module.update_dotenv_allowed_users(env_path, ["U1", "U2"])

            updated = env_path.read_text(encoding="utf-8")
            self.assertIn("SLACK_BOT_TOKEN=fake-slack-token", updated)
            self.assertIn("SLACK_ALLOWED_USERS=U1,U2", updated)
            self.assertIn("OTHER=value", updated)
            self.assertTrue(backup.exists())
            self.assertIn("SLACK_ALLOWED_USERS=UOLD", backup.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
