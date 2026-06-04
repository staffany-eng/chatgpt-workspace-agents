from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from test_helpers import load_mcp_module


LOOM_URL = "https://www.loom.com/share/e63d65ea325b4408abd9a756564e36f6?sid=unsafe"
SIGNED_VTT_URL = (
    "https://cdn.loom.com/mediametadata/captions/e63d65ea325b4408abd9a756564e36f6.vtt?"
    "Expires=1770000000&Signature=abc123&Key-Pair-Id=unsafe"
)


class DemoSourcesNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("demo_sources_nurtureany_server.py", "demo_sources_nurtureany_server_test")

    def _loom_html(self, vtt_url: str = SIGNED_VTT_URL) -> str:
        escaped_url = vtt_url.replace("&", "\\u0026").replace("/", "\\/")
        return f"""
        <html>
          <head>
            <meta property="og:title" content="15052026 Sales Meeting - Jeremy | Loom">
          </head>
          <body>
            <script>window.__data = {{"captions":"{escaped_url}"}}</script>
          </body>
        </html>
        """

    def _vtt(self) -> str:
        return """WEBVTT

1
00:00:01.000 --> 00:00:04.000
Hi Jane, can you share what is broken in scheduling? Email jane.customer@example.com.

2
00:00:05.000 --> 00:00:08.500
Call me at +65 9123 4567; pricing is my concern.

3
00:00:09.000 --> 00:00:12.000
Rep: Let me show the before and after value, not every feature.
"""

    def test_extract_loom_caption_evidence_returns_safe_segments(self):
        def fake_fetch(url, max_bytes=self.module.MAX_FETCH_BYTES):
            if url.endswith("/share/e63d65ea325b4408abd9a756564e36f6"):
                return self._loom_html()
            if ".vtt" in url:
                return self._vtt()
            raise AssertionError(f"unexpected fetch: {url}")

        with patch.object(self.module, "_fetch_text", side_effect=fake_fetch):
            result = self.module.extract_demo_transcript_evidence(
                "kaiyi@staffany.com",
                LOOM_URL,
            )

        self.assertEqual(result["confidence"], "verified")
        answer = result["answer"]
        self.assertEqual(answer["source_permalink"], "https://www.loom.com/share/e63d65ea325b4408abd9a756564e36f6")
        self.assertEqual(answer["source_type"], "loom")
        self.assertEqual(answer["cue_count"], 3)
        self.assertGreater(answer["word_count"], 20)
        self.assertEqual(answer["timing_metadata"]["duration_seconds"], 12.0)
        self.assertEqual(len(answer["segments"]), 3)
        self.assertFalse(answer["raw_transcript_returned"])
        self.assertFalse(answer["signed_loom_media_urls_returned"])
        self.assertFalse(answer["video_audio_bytes_returned"])
        result_text = str(result)
        self.assertIn("[email]", result_text)
        self.assertIn("[phone]", result_text)
        self.assertNotIn("jane.customer@example.com", result_text)
        self.assertNotIn("9123", result_text)
        self.assertNotIn(".vtt", result_text)
        self.assertNotIn("Signature=", result_text)

    def test_extract_loom_blocks_when_no_captions(self):
        with patch.object(self.module, "_fetch_text", return_value="<title>Private demo | Loom</title>"):
            result = self.module.extract_demo_transcript_evidence("kaiyi@staffany.com", LOOM_URL)

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["blocker_reason"], "captions_unavailable")
        self.assertFalse(result["answer_details"]["caption_available"])
        self.assertNotIn(".vtt", str(result))

    def test_extract_loom_blocks_private_or_login_page_without_caption(self):
        private_html = "<html><title>Log in | Loom</title><body>Please log in to view this video.</body></html>"
        with patch.object(self.module, "_fetch_text", return_value=private_html):
            result = self.module.extract_demo_transcript_evidence("kaiyi@staffany.com", LOOM_URL)

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["blocker_reason"], "captions_unavailable")
        self.assertIn("private", result["answer"].lower())

    def test_extract_blocks_malformed_or_unsupported_url_without_network(self):
        with patch.object(self.module, "_fetch_text", side_effect=AssertionError("should not fetch")):
            bad = self.module.extract_demo_transcript_evidence("kaiyi@staffany.com", "not-a-url")
            unsupported = self.module.extract_demo_transcript_evidence(
                "kaiyi@staffany.com",
                "https://example.com/demo",
            )

        self.assertEqual(bad["confidence"], "blocked")
        self.assertEqual(unsupported["confidence"], "blocked")
        self.assertIn("Loom", unsupported["answer"])

    def test_parse_vtt_redacts_and_bounds_segments(self):
        many_cues = "WEBVTT\n\n" + "\n\n".join(
            f"{index}\n00:00:{index:02d}.000 --> 00:00:{index:02d}.500\nContact lead{index}@example.com at +65 8000 {index:04d}."
            for index in range(1, 30)
        )

        cues = self.module._parse_vtt(many_cues)
        segments = self.module._safe_segments(cues)

        self.assertEqual(len(cues), 29)
        self.assertEqual(len(segments), self.module.MAX_SAFE_SEGMENTS)
        self.assertTrue(all("[email]" in segment["text"] for segment in segments))
        self.assertTrue(all("[phone]" in segment["text"] for segment in segments))
        self.assertNotIn("lead1@example.com", str(segments))
        self.assertNotIn("+65", str(segments))

    def test_demo_grade_contract_has_nine_dimensions_and_bounds(self):
        self.assertEqual(
            self.module.DEMO_GRADE_DIMENSIONS,
            [
                "Control and conversational opening",
                "Discovery and I-C-BANT",
                "Consultative/contextual demo",
                "Before/after value framing",
                "Benefits over features",
                "Product knowledge accuracy",
                "Objection and negotiation handling",
                "Customer engagement and interaction cues",
                "Next step and post-demo follow-up quality",
            ],
        )
        self.assertEqual(self.module.DEMO_GRADE_SCORE_VALUES, (0, 1, 2))
        for field in [
            "Answer",
            "Overall grade",
            "Scorecard",
            "Coachable moments",
            "Better talk tracks",
            "Manager coaching note",
            "Next practice",
            "Source",
            "Scope",
            "Confidence",
            "Caveat",
        ]:
            self.assertIn(field, self.module.DEMO_GRADE_OUTPUT_FIELDS)


if __name__ == "__main__":
    unittest.main()
