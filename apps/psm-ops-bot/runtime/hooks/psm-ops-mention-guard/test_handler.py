from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import os
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock, patch


HANDLER_PATH = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("psm_ops_mention_guard_handler", HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScanResponseTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()

    def test_clean_reply_with_no_mention_returns_no_violations(self):
        violations = self.module.scan_response("Logged this on <https://x/PCO-31|PCO-31>.", sender_user_id="U043M9HRWHG")

        self.assertEqual(violations, [])

    def test_only_tagger_mention_is_allowed(self):
        violations = self.module.scan_response(
            "Hey <@U043M9HRWHG>, noted on <https://x/PCO-31|PCO-31>.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, [])

    def test_non_tagger_mention_is_a_violation(self):
        violations = self.module.scan_response(
            "Hey <@U6E68280P|Kai Yi>, logged this on PCO-31.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["U6E68280P"])

    def test_multiple_non_tagger_mentions_dedup_and_order_preserved(self):
        violations = self.module.scan_response(
            "Hey <@U6E68280P>, FYI <@U05P7PFUWDP> and <@U6E68280P> again.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["U6E68280P", "U05P7PFUWDP"])

    def test_bot_self_reference_is_allowed(self):
        violations = self.module.scan_response(
            "Hey <@U043M9HRWHG>, <@U0B39JHV8TG> here.",
            sender_user_id="u043m9hrwhg",  # lowercased on purpose
            bot_user_id="U0B39JHV8TG",
        )

        self.assertEqual(violations, [])

    def test_workspace_id_w_prefix_is_recognized(self):
        violations = self.module.scan_response(
            "FYI <@W123ABC>.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["W123ABC"])

    def test_dict_response_is_scanned_as_string(self):
        violations = self.module.scan_response(
            {"slack_reply": "ping <@U6E68280P>"},
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["U6E68280P"])


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()
        # Stub bot-id discovery so tests never hit Slack auth.test.
        self._bot_id_patch = patch.object(self.module, "_bot_user_id", return_value="")
        self._bot_id_patch.start()
        self.addCleanup(self._bot_id_patch.stop)

    def test_empty_response_is_skipped(self):
        verdict = self.module.evaluate({"response": "", "user_id": "U043M9HRWHG"})

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "empty_response")
        self.assertEqual(verdict["violations"], [])

    def test_cron_output_is_skipped_even_with_stray_mentions(self):
        cron_text = "PSM Ops automation: PCO assignment hygiene - 2026-05-26\n*PS Team: Kai Yi* <@U6E68280P>"
        verdict = self.module.evaluate({"response": cron_text, "user_id": "U043M9HRWHG"})

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "cron_output")

    def test_silent_cron_output_is_skipped(self):
        verdict = self.module.evaluate({
            "response": "[SILENT] PSM Ops automation: no PCO assignment hygiene gaps for 2026-05-26.",
            "user_id": "U043M9HRWHG",
        })

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "cron_output")

    def test_dict_form_cron_output_is_skipped(self):
        verdict = self.module.evaluate({
            "response": {"slack_reply": "PSM Ops automation: PCO due-date reminder - 2026-05-26"},
            "user_id": "U043M9HRWHG",
        })

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "cron_output")

    def test_non_slack_platform_is_skipped(self):
        verdict = self.module.evaluate({
            "response": "Hey <@U6E68280P>",
            "user_id": "U043M9HRWHG",
            "platform": "cli",
        })

        self.assertTrue(verdict["skipped"])
        self.assertTrue(verdict["skip_reason"].startswith("non_slack_platform"))

    def test_missing_sender_is_skipped(self):
        verdict = self.module.evaluate({"response": "Hey <@U6E68280P>", "user_id": ""})

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "missing_sender")

    def test_violation_yields_expected_fields(self):
        verdict = self.module.evaluate({
            "response": "Hey <@U6E68280P|Kai Yi>, logged on PCO-31.",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        })

        self.assertFalse(verdict["skipped"])
        self.assertEqual(verdict["violations"], ["U6E68280P"])
        self.assertEqual(verdict["sender"], "U043M9HRWHG")
        self.assertIn("PCO-31", verdict["response_preview"])


class HandleAlertingTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "C0B2VT50YT1",
                "SLACK_HOME_CHANNEL": "",
                "SLACK_BOT_TOKEN": "test-fake-bot-token",
                "PSM_OPS_SLACK_BOT_TOKEN": "",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.module = load_handler()
        self._bot_id_patch = patch.object(self.module, "_bot_user_id", return_value="U0B39JHV8TG")
        self._bot_id_patch.start()
        self.addCleanup(self._bot_id_patch.stop)

    def test_violation_posts_central_warning(self):
        context = {
            "response": "Hey <@U6E68280P|Kai Yi>, logged on PCO-31.",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
            "session_id": "sess-1",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("agent:end", context))

        self.assertEqual(fake_post.call_count, 1)
        verdict = fake_post.call_args[0][0]
        self.assertEqual(verdict["sender"], "U043M9HRWHG")
        self.assertEqual(verdict["violations"], ["U6E68280P"])

    def test_clean_reply_does_not_post(self):
        context = {
            "response": "Hey <@U043M9HRWHG>, noted on PCO-31.",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("agent:end", context))

        fake_post.assert_not_called()

    def test_cron_output_does_not_post(self):
        context = {
            "response": "PSM Ops automation: PCO assignment hygiene - 2026-05-26\n*PS Team: Kai Yi* <@U6E68280P>",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("agent:end", context))

        fake_post.assert_not_called()

    def test_non_agent_end_event_is_ignored(self):
        context = {
            "response": "Hey <@U6E68280P>",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("session:start", context))

        fake_post.assert_not_called()


class PostAuditWarningTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "C0B2VT50YT1",
                "SLACK_BOT_TOKEN": "test-fake-bot-token",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.module = load_handler()

    @staticmethod
    def _fake_response(payload: dict) -> MagicMock:
        body = json.dumps(payload).encode("utf-8")
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = body
        cm.__exit__.return_value = False
        return cm

    def test_audit_message_identifies_as_automation(self):
        verdict = {
            "skipped": False,
            "sender": "U043M9HRWHG",
            "violations": ["U6E68280P"],
            "response_preview": "Hey <@U6E68280P>",
        }
        captured = {}

        def fake_urlopen(request, timeout=10):
            captured["body"] = request.data
            return self._fake_response({"ok": True})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.module._post_audit_warning(verdict)

        body = json.loads(captured["body"].decode("utf-8"))
        self.assertTrue(
            body["text"].startswith("PSM Ops mention-guard automation:"),
            f"audit text must self-identify as automation, got: {body['text']!r}",
        )

    def test_slack_ok_false_is_surfaced_on_stderr(self):
        verdict = {"sender": "U043M9HRWHG", "violations": ["U6E68280P"]}
        stderr = io.StringIO()

        def fake_urlopen(request, timeout=10):
            return self._fake_response({"ok": False, "error": "missing_scope"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stderr(stderr):
            self.module._post_audit_warning(verdict)

        self.assertIn("psm-ops-mention-guard:alert-failed:missing_scope", stderr.getvalue())

    def test_slack_ok_true_is_silent(self):
        verdict = {"sender": "U043M9HRWHG", "violations": ["U6E68280P"]}
        stderr = io.StringIO()

        def fake_urlopen(request, timeout=10):
            return self._fake_response({"ok": True, "ts": "1.0", "channel": "C0B2VT50YT1"})

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stderr(stderr):
            self.module._post_audit_warning(verdict)

        self.assertEqual(stderr.getvalue(), "")

    def test_transport_error_does_not_raise(self):
        verdict = {"sender": "U043M9HRWHG", "violations": ["U6E68280P"]}
        stderr = io.StringIO()

        import urllib.error

        def fake_urlopen(request, timeout=10):
            raise urllib.error.URLError("network down")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stderr(stderr):
            # Must not raise: hook is best-effort.
            self.module._post_audit_warning(verdict)

        self.assertIn("alert-transport-error", stderr.getvalue())


class CoerceTextFallbackTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()
        self._bot_id_patch = patch.object(self.module, "_bot_user_id", return_value="")
        self._bot_id_patch.start()
        self.addCleanup(self._bot_id_patch.stop)

    def test_non_json_serializable_falls_back_to_str(self):
        class Weird:
            def __str__(self):
                return "weird-value <@U6E68280P>"

        # _coerce_text must not raise even when json.dumps cannot serialize.
        text = self.module._coerce_text(Weird())
        self.assertIn("weird-value", text)
        # And evaluate() must still flow through scan_response over the fallback text.
        verdict = self.module.evaluate({
            "response": Weird(),
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        })
        self.assertFalse(verdict["skipped"])
        self.assertEqual(verdict["violations"], ["U6E68280P"])


class BotUserIdAutoDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()
        self.module._BOT_USER_ID_CACHE = ""

    @staticmethod
    def _fake_response(payload: dict) -> MagicMock:
        body = json.dumps(payload).encode("utf-8")
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = body
        cm.__exit__.return_value = False
        return cm

    def test_auth_test_resolves_and_caches(self):
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "x"}, clear=False):
            calls = []

            def fake_urlopen(request, timeout=10):
                calls.append(request.full_url)
                return self._fake_response({"ok": True, "user_id": "U0B39JHV8TG"})

            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                self.assertEqual(self.module._bot_user_id(), "U0B39JHV8TG")
                # second call must come from cache, not the network
                self.assertEqual(self.module._bot_user_id(), "U0B39JHV8TG")

            self.assertEqual(len(calls), 1)
            self.assertIn("auth.test", calls[0])

    def test_auth_test_failure_is_not_cached_and_recovers_next_call(self):
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "x"}, clear=False):
            stderr = io.StringIO()
            responses = [
                self._fake_response({"ok": False, "error": "ratelimited"}),
                self._fake_response({"ok": True, "user_id": "U0B39JHV8TG"}),
            ]

            def fake_urlopen(request, timeout=10):
                return responses.pop(0)

            with patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stderr(stderr):
                # First call: Slack returns ok=false; must not poison the cache.
                self.assertEqual(self.module._bot_user_id(), "")
                # Second call: Slack recovers; the hook resolves the real ID.
                self.assertEqual(self.module._bot_user_id(), "U0B39JHV8TG")

            self.assertIn("auth-test-failed:ratelimited", stderr.getvalue())
            self.assertEqual(self.module._BOT_USER_ID_CACHE, "U0B39JHV8TG")

    def test_transport_error_is_not_cached_and_recovers_next_call(self):
        import urllib.error

        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "x"}, clear=False):
            stderr = io.StringIO()
            call_index = {"n": 0}

            def fake_urlopen(request, timeout=10):
                call_index["n"] += 1
                if call_index["n"] == 1:
                    raise urllib.error.URLError("temporary blip")
                return self._fake_response({"ok": True, "user_id": "U0B39JHV8TG"})

            with patch("urllib.request.urlopen", side_effect=fake_urlopen), redirect_stderr(stderr):
                self.assertEqual(self.module._bot_user_id(), "")
                self.assertEqual(self.module._bot_user_id(), "U0B39JHV8TG")

            self.assertIn("auth-test-error", stderr.getvalue())

    def test_missing_token_returns_empty_without_network(self):
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "", "PSM_OPS_SLACK_BOT_TOKEN": ""}, clear=False):
            with patch("urllib.request.urlopen") as fake:
                self.assertEqual(self.module._bot_user_id(), "")
                fake.assert_not_called()


class CentralChannelResolutionTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()

    def test_central_channel_does_not_fall_back_to_slack_home_channel(self):
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "",
                "SLACK_HOME_CHANNEL": "C_CUSTOMER_FACING",
            },
            clear=False,
        ):
            self.assertEqual(self.module._central_channel(), "")

    def test_central_channel_returns_configured_audit_channel(self):
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "C0B2VT50YT1",
                "SLACK_HOME_CHANNEL": "C_CUSTOMER_FACING",
            },
            clear=False,
        ):
            self.assertEqual(self.module._central_channel(), "C0B2VT50YT1")


if __name__ == "__main__":
    unittest.main()
