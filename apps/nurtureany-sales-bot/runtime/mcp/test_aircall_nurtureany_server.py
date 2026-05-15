from __future__ import annotations

import os
import json
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

    def _valid_coaching_payload(self):
        return {
            "answer": "The call had useful discovery but needed a cleaner next step.",
            "scorecard": [
                {
                    "dimension": dimension,
                    "score": 1,
                    "evidence": f"{dimension} evidence at 00:10.",
                    "timestamp": "00:10",
                    "segment_ref": "seg_1",
                }
                for dimension in self.module.CALL_COACH_SCORE_DIMENSIONS
            ],
            "coachable_moments": [
                {
                    "timestamp": "00:10",
                    "segment_ref": "seg_1",
                    "note": "Customer asked about pricing.",
                    "coaching_point": "Acknowledge the concern, then quantify the staffing risk.",
                }
            ],
            "interaction_cues": {
                "status": "Interaction cues checked from transcript/timing",
                "tone_audio_cues": "audio-native tone not checked",
                "talk_ratio": "Rep spoke 64% of measured time.",
                "interactivity": "Medium turn-taking.",
                "longest_monologue": "Longest run was 40s.",
                "question_count": "3 questions.",
                "objections": "Pricing objection surfaced.",
                "next_step_clarity": "Partial next step.",
                "customer_reaction_moments": "Short answer after pricing.",
            },
            "manager_coaching_note": {
                "praise": "Good job finding the payroll angle.",
                "correction": "Do not leave pricing as a loose objection.",
                "practice_assignment": "Practice a 20-second pricing bridge.",
                "next_action": "Book a dated follow-up.",
            },
            "next_action": "Rep should send a recap and ask for a dated follow-up.",
            "source": "Aircall/OpenAI selected-call analysis.",
            "scope": "selected call",
            "confidence": "verified",
            "caveat": "audio-native tone not checked.",
        }

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

    def test_resolve_call_uses_exact_aircall_id_and_returns_safe_metadata(self):
        call_payload = {
            "call": {
                "id": 3770565512,
                "started_at": 1778741950,
                "duration": 162,
                "recording": "https://recordings.example.test/3770565512.mp3",
                "user": {"id": 8, "name": "Jeffrey Wong", "email": "jeffrey@example.com"},
                "number": {"name": "+65 8123 4567"},
            }
        }

        with patch.object(self.module, "_aircall_get", return_value=call_payload) as aircall_get:
            result = self.module.resolve_aircall_call_for_coaching(
                "kaiyi@staffany.com",
                aircall_call_id="3770565512",
            )

        aircall_get.assert_called_once_with("/calls/3770565512")
        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["selected_call_resolved"])
        self.assertEqual(result["answer"]["selected_aircall_call_id"], "3770565512")
        self.assertFalse(result["answer"]["raw_recording_urls_returned"])
        self.assertFalse(result["answer"]["phone_numbers_returned"])
        self.assertNotIn("recordings.example", str(result))
        self.assertNotIn("8123", str(result))

    def test_resolve_call_blocks_non_numeric_aircall_id(self):
        with patch.object(self.module, "_aircall_get", side_effect=AssertionError("should not call Aircall")):
            result = self.module.resolve_aircall_call_for_coaching(
                "kaiyi@staffany.com",
                aircall_call_id="hubspot-call-123",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("numeric Aircall call ID", result["answer"])

    def test_resolve_call_uses_bounded_hints_when_exact_id_is_missing(self):
        payload = {
            "calls": [
                {
                    "id": 3770565512,
                    "started_at": 1778741950,
                    "duration": 162,
                    "recording": "https://recordings.example.test/3770565512.mp3",
                    "user": {"id": 8, "name": "Jeffrey Wong", "email": "jeffrey@example.com"},
                }
            ]
        }

        with patch.object(self.module, "_aircall_get", return_value=payload) as aircall_get:
            result = self.module.resolve_aircall_call_for_coaching(
                "kaiyi@staffany.com",
                match_started_at="2026-05-14T06:59:10Z",
                match_user_name="Jeffrey Wong",
                match_duration_seconds=162,
                timestamp_tolerance_seconds=60,
                duration_tolerance_seconds=5,
            )

        _path, params = aircall_get.call_args.args
        self.assertEqual(params["from"], "1778741890")
        self.assertEqual(params["to"], "1778742010")
        self.assertEqual(params["per_page"], self.module.MAX_LOOKUP_CALLS)
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["resolution_method"], "bounded_aircall_match")
        self.assertTrue(result["answer"]["selected_call_resolved"])
        self.assertEqual(result["answer"]["selected_aircall_call_id"], "3770565512")
        self.assertEqual(result["scope"]["lookup_scope"]["requested_limit"], self.module.MAX_RESOLVER_CANDIDATES)
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

    def test_compute_interaction_metrics_from_diarized_segments(self):
        segments = [
            {
                "ref": "seg_1",
                "speaker": "rep",
                "start": 0.0,
                "end": 40.0,
                "timestamp": "00:00",
                "duration_seconds": 40.0,
                "word_count": 10,
                "text": "Can you walk me through your current scheduling process?",
            },
            {
                "ref": "seg_2",
                "speaker": "customer",
                "start": 43.0,
                "end": 46.0,
                "timestamp": "00:43",
                "duration_seconds": 3.0,
                "word_count": 2,
                "text": "Too expensive.",
            },
            {
                "ref": "seg_3",
                "speaker": "rep",
                "start": 47.0,
                "end": 58.0,
                "timestamp": "00:47",
                "duration_seconds": 11.0,
                "word_count": 8,
                "text": "What budget range would make sense if payroll errors drop?",
            },
            {
                "ref": "seg_4",
                "speaker": "customer",
                "start": 59.0,
                "end": 66.0,
                "timestamp": "00:59",
                "duration_seconds": 7.0,
                "word_count": 9,
                "text": "Can you send that before our meeting tomorrow?",
            },
        ]

        metrics = self.module._compute_interaction_metrics(segments)

        self.assertEqual(metrics["talk_ratio_basis"], "seconds")
        self.assertEqual(metrics["dominant_speaker"], "rep")
        self.assertEqual(metrics["turn_count"], 4)
        self.assertEqual(metrics["question_count"], 3)
        self.assertEqual(metrics["next_step_clarity"]["status"], "strong")
        self.assertEqual(metrics["objection_moments"][0]["categories"], ["pricing"])
        self.assertEqual(metrics["longest_monologue"]["units"], 40.0)
        self.assertTrue(any(moment["cue"] == "short answer" for moment in metrics["customer_reaction_moments"]))
        self.assertTrue(any(moment["cue"] == "silence gap" for moment in metrics["customer_reaction_moments"]))

    def test_compute_interaction_metrics_handles_missing_timestamps_and_speakers(self):
        segments = [
            {
                "ref": "seg_1",
                "speaker": "",
                "timestamp": "call-level",
                "word_count": 5,
                "text": "Can we follow up?",
            },
            {
                "ref": "seg_2",
                "speaker": "",
                "timestamp": "call-level",
                "word_count": 3,
                "text": "Next week works.",
            },
        ]

        metrics = self.module._compute_interaction_metrics(segments)

        self.assertEqual(metrics["talk_ratio_basis"], "word_count")
        self.assertEqual(metrics["turn_count"], 1)
        self.assertEqual(metrics["question_count"], 1)
        self.assertEqual(metrics["next_step_clarity"]["status"], "strong")

    def test_validate_coaching_payload_rejects_missing_score_dimension(self):
        payload = self._valid_coaching_payload()
        payload["scorecard"] = payload["scorecard"][:-1]

        with self.assertRaises(self.module.AircallError):
            self.module._validate_coaching_payload(payload)

    def test_validate_coaching_payload_sanitizes_hidden_emotion_claims(self):
        payload = self._valid_coaching_payload()
        payload["answer"] = "The customer was frustrated after pricing."

        sanitized = self.module._validate_coaching_payload(payload)

        self.assertNotIn("frustrated", str(sanitized).lower())
        self.assertIn("showed friction", sanitized["answer"])
        self.assertEqual(sanitized["interaction_cues"]["tone_audio_cues"], "audio-native tone not checked")

    def test_openai_call_coach_uses_responses_structured_outputs(self):
        captured = {}
        response_body = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(self._valid_coaching_payload()),
                        }
                    ]
                }
            ]
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(response_body).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=True), patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            result = self.module._openai_call_coach(
                "redacted transcript",
                [],
                {"interaction_cue_status": "Interaction cues checked from transcript/timing"},
                {"hubspot_company_id": "123"},
                "gpt-5.5",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(captured["url"], self.module.OPENAI_RESPONSES_URL)
        self.assertEqual(captured["payload"]["model"], "gpt-5.5")
        self.assertEqual(captured["payload"]["text"]["format"]["type"], "json_schema")
        self.assertTrue(captured["payload"]["text"]["format"]["strict"])
        self.assertEqual(captured["timeout"], 120)

    def test_analyze_call_coaching_returns_safe_json_and_deletes_temp_audio(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as handle:
            temp_path = Path(handle.name)
            handle.write(b"fake-audio")

        call_payload = {
            "call": {
                "id": 789,
                "duration": 179,
                "recording": "https://recordings.example.test/789.mp3",
                "user": {"id": 8, "name": "Jeffrey", "email": "jeffrey@example.com"},
                "number": {"name": "+65 8123 4567"},
            }
        }
        transcript_payload = {
            "text": "Customer jane@example.com said +65 8123 4567 is too expensive. Rep asked to meet tomorrow.",
            "segments": [
                {
                    "speaker": "rep",
                    "start": 0.0,
                    "end": 12.0,
                    "text": "Can you share what payroll issue is happening now?",
                },
                {
                    "speaker": "customer",
                    "start": 14.0,
                    "end": 17.0,
                    "text": "Too expensive. Email jane@example.com at +65 8123 4567.",
                },
                {
                    "speaker": "rep",
                    "start": 18.0,
                    "end": 25.0,
                    "text": "Can we meet tomorrow to review savings?",
                },
            ],
        }
        coaching_payload = self._valid_coaching_payload()
        coaching_payload["answer"] = "The customer was frustrated by pricing, but the rep recovered."

        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-openai-key"}, clear=True),
            patch.object(self.module, "_aircall_get", return_value=call_payload),
            patch.object(self.module, "_download_recording", return_value=(temp_path, 10, "audio/mpeg")),
            patch.object(self.module, "_openai_transcribe", return_value=transcript_payload),
            patch.object(self.module, "_openai_call_coach", return_value=coaching_payload) as coach,
        ):
            result = self.module.analyze_aircall_call_coaching(
                "kaiyi@staffany.com",
                "789",
                hubspot_company_id="12345",
                hubspot_call_id="67890",
            )

        coach.assert_called_once()
        self.assertFalse(temp_path.exists())
        self.assertEqual(result["confidence"], "verified")
        coaching = result["answer"]["coaching"]
        self.assertEqual(coaching["interaction_cues"]["status"], "Interaction cues checked from transcript/timing")
        self.assertEqual(coaching["interaction_cues"]["tone_audio_cues"], "audio-native tone not checked")
        self.assertFalse(result["answer"]["raw_transcript_returned"])
        self.assertFalse(result["answer"]["raw_audio_retained"])
        self.assertFalse(result["answer"]["raw_recording_url_returned"])
        self.assertNotIn("jane@example.com", str(result))
        self.assertNotIn("8123", str(result))
        self.assertNotIn("recordings.example", str(result))
        self.assertNotIn("frustrated", str(result).lower())


if __name__ == "__main__":
    unittest.main()
