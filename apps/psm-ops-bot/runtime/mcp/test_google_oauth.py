from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import io

from test_helpers import load_mcp_module


class GoogleOauthTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.token_path = Path(self.tmpdir.name) / "token.json"
        self.client_path = Path(self.tmpdir.name) / "client.json"
        self.client_path.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        self.module = load_mcp_module("google_oauth.py", "google_oauth_test")

    def _write_token(self, **overrides):
        payload = {
            "token": "cached-access-token",
            "refresh_token": "rt-1",
            "client_id": "cid",
            "client_secret": "csec",
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
        }
        payload.update(overrides)
        self.token_path.write_text(json.dumps(payload), encoding="utf-8")
        return payload

    def _make_response(self, body: dict) -> io.BytesIO:
        wrapper = io.BytesIO(json.dumps(body).encode("utf-8"))
        wrapper.__enter__ = lambda self: self  # type: ignore[attr-defined]
        wrapper.__exit__ = lambda self, *args: None  # type: ignore[attr-defined]
        return wrapper

    def _call_access_token(self):
        return self.module.access_token(
            self.token_path,
            self.client_path,
            {"https://www.googleapis.com/auth/drive.file"},
            "test-agent",
            5,
            "Drive",
            RuntimeError,
        )

    def test_returns_cached_token_when_expiry_is_in_the_future(self):
        future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        self._write_token(expiry=future)
        # urlopen would only be called on refresh — fail if called
        with patch.object(self.module.urllib.request, "urlopen", side_effect=AssertionError("must not refresh")):
            tok = self._call_access_token()
        self.assertEqual(tok, "cached-access-token")

    def test_refreshes_when_token_is_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        self._write_token(expiry=past)
        captured = []

        def fake_urlopen(request, timeout=None):
            captured.append(request)
            return self._make_response({"access_token": "fresh-token-xyz", "expires_in": 3599, "token_type": "Bearer"})

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            tok = self._call_access_token()
        self.assertEqual(tok, "fresh-token-xyz")
        self.assertEqual(len(captured), 1)
        # New expiry was written to the token file so subsequent calls can cache.
        saved = json.loads(self.token_path.read_text())
        self.assertEqual(saved["token"], "cached-access-token")  # original "token" preserved unless refresh provides one
        self.assertEqual(saved["access_token"], "fresh-token-xyz")
        self.assertIn("expiry", saved)
        # The new expiry should be roughly an hour from now.
        new_exp = saved["expiry"]
        new_exp_dt = datetime.fromisoformat(new_exp.replace("Z", "+00:00"))
        self.assertGreater(new_exp_dt, datetime.now(timezone.utc) + timedelta(minutes=50))

    def test_refreshes_when_expiry_field_is_missing(self):
        # Tokens written before this fix may have no expiry — treat as expired.
        self._write_token()  # no expiry field
        self.token_path.write_text(
            json.dumps({"refresh_token": "rt-1", "scopes": ["https://www.googleapis.com/auth/drive.file"]}),
            encoding="utf-8",
        )
        captured = []

        def fake_urlopen(request, timeout=None):
            captured.append(request)
            return self._make_response({"access_token": "fresh-no-expiry", "expires_in": 3599, "token_type": "Bearer"})

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            tok = self._call_access_token()
        self.assertEqual(tok, "fresh-no-expiry")
        self.assertEqual(len(captured), 1)


if __name__ == "__main__":
    unittest.main()
