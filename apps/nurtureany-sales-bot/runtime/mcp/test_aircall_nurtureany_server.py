from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from test_helpers import load_mcp_module


class AircallNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("aircall_nurtureany_server.py", "aircall_nurtureany_server_test")

    def test_find_calls_blocks_missing_aircall_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            result = self.module.find_aircall_calls("eugene@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Missing AIRCALL_API_ID", result["answer"])

    def test_find_calls_returns_safe_metadata_only(self):
        payload = {
            "calls": [
                {
                    "id": 123,
                    "started_at": "2026-05-14T10:00:00Z",
                    "duration": 180,
                    "direction": "outbound",
                    "status": "done",
                    "recording": "https://recordings.example.test/raw.mp3",
                    "user": {"id": 7, "name": "Eugene", "email": "eugene@staffany.com"},
                    "number": {"name": "+65 9123 4567"},
                }
            ]
        }

        with patch.object(self.module, "_aircall_get", return_value=payload):
            result = self.module.find_aircall_calls("eugene@staffany.com", limit=99)

        call = result["answer"]["calls"][0]
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["call_count"], 1)
        self.assertEqual(result["scope"]["requested_limit"], 5)
        self.assertTrue(call["recording_available"])
        self.assertFalse(call["raw_recording_url_returned"])
        self.assertFalse(call["phone_numbers_returned"])
        self.assertNotIn("recordings.example", str(result))
        self.assertNotIn("9123", str(result))
        self.assertIn("[email]", call["user_name"])
        self.assertIn("[phone]", call["number_name"])

    def test_find_calls_normalizes_iso_timestamps_to_unix_params(self):
        captured = {}

        def fake_aircall_get(path, params):
            captured["path"] = path
            captured["params"] = params
            return {"calls": []}

        with patch.object(self.module, "_aircall_get", side_effect=fake_aircall_get):
            result = self.module.find_aircall_calls(
                "eugene@staffany.com",
                from_timestamp="2026-05-14T06:55:00Z",
                to_timestamp="2026-05-14 07:05:00+00:00",
                order="asc",
            )

        self.assertEqual(captured["path"], "/calls")
        self.assertEqual(captured["params"]["from"], "1778741700")
        self.assertEqual(captured["params"]["to"], "1778742300")
        self.assertEqual(result["scope"]["from_timestamp"], "1778741700")
        self.assertEqual(result["scope"]["to_timestamp"], "1778742300")

    def test_find_calls_preserves_unix_timestamp_params(self):
        captured = {}

        def fake_aircall_get(_path, params):
            captured["params"] = params
            return {"calls": []}

        with patch.object(self.module, "_aircall_get", side_effect=fake_aircall_get):
            result = self.module.find_aircall_calls(
                "eugene@staffany.com",
                from_timestamp="1778741700",
                to_timestamp="1778742300",
            )

        self.assertEqual(captured["params"]["from"], "1778741700")
        self.assertEqual(captured["params"]["to"], "1778742300")
        self.assertEqual(result["scope"]["from_timestamp"], "1778741700")

    def test_find_calls_blocks_invalid_timestamp_without_network(self):
        with patch.object(self.module, "_aircall_get", side_effect=AssertionError("should not call Aircall")):
            result = self.module.find_aircall_calls("eugene@staffany.com", from_timestamp="not-a-time")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("from_timestamp", result["answer"])

    def test_find_calls_selected_lookup_matches_safe_metadata(self):
        payload = {
            "calls": [
                {
                    "id": 111,
                    "started_at": 1778741880,
                    "duration": 90,
                    "recording": "https://recordings.example.test/111.mp3",
                    "user": {"id": 7, "name": "Someone Else", "email": "other@example.com"},
                },
                {
                    "id": 3770565512,
                    "started_at": 1778741950,
                    "duration": 162,
                    "recording": "https://recordings.example.test/3770565512.mp3",
                    "user": {"id": 8, "name": "Jeffrey Wong", "email": "jeffrey@example.com"},
                },
                {
                    "id": 333,
                    "started_at": 1778742260,
                    "duration": 162,
                    "recording": "https://recordings.example.test/333.mp3",
                    "user": {"id": 8, "name": "Jeffrey Wong", "email": "jeffrey@example.com"},
                },
            ]
        }
        captured = {}

        def fake_aircall_get(_path, params):
            captured["params"] = params
            return payload

        with patch.object(self.module, "_aircall_get", side_effect=fake_aircall_get):
            result = self.module.find_aircall_calls(
                "kaiyi@staffany.com",
                match_started_at="2026-05-14T06:59:10Z",
                match_user_name="Jeffrey Wong",
                match_duration_seconds=162,
                timestamp_tolerance_seconds=60,
                duration_tolerance_seconds=5,
            )

        self.assertEqual(captured["params"]["from"], "1778741890")
        self.assertEqual(captured["params"]["to"], "1778742010")
        self.assertEqual(captured["params"]["per_page"], self.module.MAX_LOOKUP_CALLS)
        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["selected_call_match"])
        self.assertEqual(result["answer"]["call_count"], 1)
        self.assertEqual(result["answer"]["calls"][0]["aircall_call_id"], "3770565512")
        self.assertNotIn("recordings.example", str(result))

    def test_transcribe_selected_call_deletes_temp_audio_and_redacts_output(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as handle:
            temp_path = Path(handle.name)
            handle.write(b"fake-audio")

        call_payload = {
            "call": {
                "id": 456,
                "duration": 60,
                "recording": "https://recordings.example.test/456.mp3",
                "user": {"id": 8, "name": "AE"},
                "number": {"name": "+65 8123 4567"},
            }
        }
        transcript_payload = {
            "text": "Customer jane@example.com asked us to call +65 8123 4567 next week.",
            "segments": [
                {
                    "speaker": "speaker_0",
                    "start": 0.0,
                    "end": 2.0,
                    "text": "Email jane@example.com and phone +65 8123 4567.",
                }
            ],
        }

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=True),
            patch.object(self.module, "_aircall_get", return_value=call_payload),
            patch.object(self.module, "_download_recording", return_value=(temp_path, 10, "audio/mpeg")),
            patch.object(self.module, "_openai_transcribe", return_value=transcript_payload) as transcribe,
        ):
            result = self.module.transcribe_aircall_recording(
                "eugene@staffany.com",
                "456",
                include_segments=True,
                max_segments=10,
            )

        transcribe.assert_called_once()
        self.assertFalse(temp_path.exists())
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["call"]["aircall_call_id"], "456")
        self.assertFalse(result["answer"]["raw_recording_url_returned"])
        self.assertFalse(result["answer"]["raw_audio_retained"])
        text = result["answer"]["transcription"]["transcript_text_redacted"]
        self.assertIn("[email]", text)
        self.assertIn("[phone]", text)
        self.assertNotIn("jane@example.com", str(result))
        self.assertNotIn("8123", str(result))
        self.assertNotIn("recordings.example", str(result))

    def test_transcribe_rejects_invalid_call_id(self):
        result = self.module.transcribe_aircall_recording("eugene@staffany.com", "abc")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("numeric Aircall call ID", result["answer"])

    def test_openai_default_request_uses_diarized_json_and_chunking(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as handle:
            file_path = Path(handle.name)
            handle.write(b"fake-audio")

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"text":"ok","segments":[]}'

        def fake_urlopen(request, timeout):
            captured["body"] = request.data.decode("utf-8", errors="ignore")
            captured["content_type"] = request.headers.get("Content-type") or request.headers.get("Content-Type")
            captured["timeout"] = timeout
            return FakeResponse()

        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=True), patch(
                "urllib.request.urlopen", side_effect=fake_urlopen
            ):
                result = self.module._openai_transcribe(file_path, "audio/mpeg", self.module.DEFAULT_MODEL)
        finally:
            file_path.unlink(missing_ok=True)

        self.assertEqual(result["text"], "ok")
        self.assertIn("gpt-4o-transcribe-diarize", captured["body"])
        self.assertIn("diarized_json", captured["body"])
        self.assertIn("chunking_strategy", captured["body"])
        self.assertIn("multipart/form-data", captured["content_type"])
        self.assertEqual(captured["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
