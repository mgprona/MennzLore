"""
tests/test_splitter.py
=======================
Unit tests for engine/split_chapters.py strip_inline_annotations and
heading detection (Bug #1, Bug #15).

Run:
    python -m pytest tests/ -v
or:
    python tests/test_splitter.py
"""
import os
import sys
import re
import unittest
from pathlib import Path

# Make engine/ importable
ENGINE_DIR = Path(__file__).parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR.parent))

from engine.split_chapters import (
    _INLINE_ANNOTATION,
    _TRANSCRIBER_FOOTER,
    strip_inline_annotations,
    _is_heading,
)


class TestInlineAnnotationRegex(unittest.TestCase):
    """Bug #1 + Bug #15 — regex must match all known annotation shapes."""

    def test_sidenote(self):
        m = _INLINE_ANNOTATION.match("[Sidenote: this is a side comment]")
        self.assertIsNotNone(m)

    def test_illustration(self):
        m = _INLINE_ANNOTATION.match("[Illustration: title page with decorative border]")
        self.assertIsNotNone(m)

    def test_frontispiece(self):
        m = _INLINE_ANNOTATION.match("[Frontispiece: engraving of London]")
        self.assertIsNotNone(m)

    def test_footnote_plain(self):
        m = _INLINE_ANNOTATION.match("[Footnote: explanation follows]")
        self.assertIsNotNone(m)

    def test_footnote_with_number(self):
        """Bug #15 — the original regex did not match '[Footnote 1: ...]'"""
        m = _INLINE_ANNOTATION.match("[Footnote 1: explanation follows]")
        self.assertIsNotNone(m, "Must match [Footnote N: ...] pattern")

    def test_footnote_with_large_number(self):
        m = _INLINE_ANNOTATION.match("[Footnote 22: 'FORMERLY': F,S,L,C in caps, ...]")
        self.assertIsNotNone(m)

    def test_translator(self):
        m = _INLINE_ANNOTATION.match("[Translator: Note from the translator]")
        self.assertIsNotNone(m)

    def test_transcriber_note(self):
        m = _INLINE_ANNOTATION.match("[Transcriber's note: original text had typo]")
        self.assertIsNotNone(m)

    def test_leading_whitespace(self):
        m = _INLINE_ANNOTATION.match("   [Footnote 5: small caps]")
        self.assertIsNotNone(m)

    def test_narrative_brackets_preserved(self):
        """The regex must NOT match brackets in middle of prose."""
        self.assertIsNone(_INLINE_ANNOTATION.match("She said \"[hello]\" to me."))
        self.assertIsNone(_INLINE_ANNOTATION.match("His [wounded] arm hung limp."))

    def test_brackets_start_of_line_only(self):
        """Only lines *starting with* an annotation are stripped."""
        self.assertIsNone(_INLINE_ANNOTATION.match("The footnote was [Sidenote: ...] but..."))


class TestTranscriberFooter(unittest.TestCase):
    """Bug #1 — Transcriber's Changes: footer must be detected."""

    def test_standard_footer(self):
        m = _TRANSCRIBER_FOOTER.match("Transcriber's Changes:")
        self.assertIsNotNone(m)

    def test_no_apostrophe(self):
        m = _TRANSCRIBER_FOOTER.match("Transcribers Changes:")
        self.assertIsNotNone(m)

    def test_no_colon(self):
        m = _TRANSCRIBER_FOOTER.match("Transcriber's Changes")
        self.assertIsNotNone(m)

    def test_case_insensitive(self):
        m = _TRANSCRIBER_FOOTER.match("transcriber's changes:")
        self.assertIsNotNone(m)

    def test_mid_body_should_not_match(self):
        """Only at the start of a line; mid-prose must not trigger."""
        # _TRANSCRIBER_FOOTER is tested by re.match which anchors ^, so
        # mid-line text does not match.
        self.assertIsNone(_TRANSCRIBER_FOOTER.match("the transcriber's changes were minimal."))


class TestStripInlineAnnotations(unittest.TestCase):
    """Integration: strip_inline_annotations should remove and preserve correctly."""

    def test_single_line_stripped(self):
        lines = [
            "The sun rose over the hill.",
            "[Illustration: title page]",
            "It was a fine morning.",
        ]
        out = strip_inline_annotations(lines)
        self.assertNotIn("[Illustration: title page]", out)
        self.assertIn("The sun rose over the hill.", out)
        self.assertIn("It was a fine morning.", out)

    def test_footnote_with_number_stripped(self):
        lines = [
            "A complex sentence here.",
            "[Footnote 1: This is the first footnote]",
            "Another sentence.",
        ]
        out = strip_inline_annotations(lines)
        self.assertNotIn("[Footnote 1: This is the first footnote]", out)
        self.assertIn("Another sentence.", out)

    def test_transcriber_footer_clears_to_end(self):
        lines = [
            "Real narrative line.",
            "",
            "Transcriber's Changes:",
            "Typo fix: chapter X had a misspelling",
            "Another typo: word 'colour' was changed to 'color'",
        ]
        out = strip_inline_annotations(lines)
        # Footer + everything after it should be gone
        joined = "\n".join(out)
        self.assertNotIn("Transcriber", joined)
        self.assertNotIn("Typo fix", joined)
        # The narrative line BEFORE the footer should be kept
        self.assertIn("Real narrative line.", joined)

    def test_narrative_brackets_preserved(self):
        lines = [
            "The note said '[read this]' on the cover.",
            "She exclaimed \"[not again]!\" to her friend.",
        ]
        out = strip_inline_annotations(lines)
        # Both lines should still be present (no annotations to strip)
        self.assertEqual(len(out), 2)

    def test_empty_input(self):
        self.assertEqual(strip_inline_annotations([]), [])

    def test_only_annotations(self):
        lines = [
            "[Illustration: pic 1]",
            "[Sidenote: as noted]",
            "[Footnote 2: typo fix]",
        ]
        out = strip_inline_annotations(lines)
        self.assertEqual(out, [])


class TestHeadingDetection(unittest.TestCase):
    """Bug #15 — PART-level headings should NOT be chapter breaks."""

    def test_chapter_heading_yes(self):
        lines = ["", "CHAPTER I.", "", "First paragraph."]
        self.assertTrue(_is_heading(lines, 1))

    def test_part_heading_no(self):
        """Bug #15 — 'PART I.' must not be treated as chapter break."""
        lines = ["", "PART I.", "", "First paragraph."]
        self.assertFalse(_is_heading(lines, 1))

    def test_part_with_subtitle_no(self):
        lines = ["", "PART I. _The Country of the Saints._", "", "First paragraph."]
        self.assertFalse(_is_heading(lines, 1))

    def test_chapter_with_subtitle_yes(self):
        lines = ["", "CHAPTER I. MR. SHERLOCK HOLMES.", "", "First paragraph."]
        self.assertTrue(_is_heading(lines, 1))

    def test_no_blank_around_no(self):
        """Heading must be blank-line guarded."""
        lines = ["Previous text.", "CHAPTER I.", "Continued text."]
        self.assertFalse(_is_heading(lines, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
