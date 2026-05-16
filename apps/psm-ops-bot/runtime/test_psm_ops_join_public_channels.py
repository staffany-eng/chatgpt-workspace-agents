from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parent / "scripts" / "psm_ops_join_public_channels.py"


def load_script():
    spec = importlib.util.spec_from_file_location("psm_ops_join_public_channels", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PsmOpsJoinPublicChannelsScriptTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.channels = [
            {"id": "C1", "name": "already-in", "is_member": True, "is_archived": False},
            {"id": "C2", "name": "needs-join", "is_member": False, "is_archived": False},
            {"id": "C3", "name": "archived", "is_member": False, "is_archived": True},
        ]

    def test_dry_run_reports_candidates_without_joining(self):
        calls = []

        def fake_api(method, params, post=False):
            calls.append((method, params, post))
            return {"ok": True}

        result = self.module.join_public_channels(self.channels, apply=False, api=fake_api)

        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["visible_public_channels"], 2)
        self.assertEqual(result["already_member"], 1)
        self.assertEqual(result["would_join"], 1)
        self.assertEqual(result["joined"], 0)
        self.assertEqual(calls, [])

    def test_apply_reports_missing_join_scope(self):
        def fake_api(method, params, post=False):
            self.assertEqual(method, "conversations.join")
            self.assertEqual(params["channel"], "C2")
            self.assertTrue(post)
            return {"ok": False, "error": "missing_scope"}

        result = self.module.join_public_channels(self.channels, apply=True, api=fake_api)

        self.assertEqual(result["joined"], 0)
        self.assertEqual(result["failed"], [{"channel_id": "C2", "channel_name": "needs-join", "error": "missing_scope"}])

    def test_channel_id_filter_limits_join_candidates(self):
        result = self.module.join_public_channels(
            self.channels,
            apply=False,
            only_channel_ids={"C1"},
        )

        self.assertEqual(result["visible_public_channels"], 1)
        self.assertEqual(result["already_member"], 1)
        self.assertEqual(result["would_join"], 0)

    def test_load_profile_env_does_not_override_explicit_env(self):
        with tempfile.TemporaryDirectory() as tempdir:
            profile = Path(tempdir)
            (profile / ".env").write_text("SLACK_BOT_TOKEN=from-profile\nOTHER_VALUE=from-profile\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "HERMES_PROFILE_DIR": str(profile),
                    "SLACK_BOT_TOKEN": "explicit",
                },
                clear=True,
            ):
                self.module.load_profile_env()

                self.assertEqual(os.environ["SLACK_BOT_TOKEN"], "explicit")
                self.assertEqual(os.environ["OTHER_VALUE"], "from-profile")


if __name__ == "__main__":
    unittest.main()
