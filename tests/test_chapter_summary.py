"""
tests/test_chapter_summary.py
=============================
Unit tests for engine/utils.generate_previous_chapters_summary.
Tests auto-generation of prior chapter contexts for subagents.

Run:
    python -m pytest tests/ -v
or:
    python tests/test_chapter_summary.py
"""
import sys
import unittest
import tempfile
import shutil
import os
from pathlib import Path

ENGINE_DIR = Path(__file__).parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR.parent))

from engine.utils import generate_previous_chapters_summary, write_json

class TestChapterSummary(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure
        self.test_dir = tempfile.mkdtemp()
        self.prefix = "testbook"
        self.micro_dir = os.path.join(self.test_dir, "micro_facts")
        os.makedirs(self.micro_dir)
        
        # Write EP001 facts
        write_json(
            os.path.join(self.micro_dir, f"{self.prefix}_EP001_micro_facts.json"),
            {
                "chapter_id": "EP001",
                "chapter_title": "First Chapter",
                "key_plot_points": [
                    {"description": "Hero is born."},
                    {"description": "Hero learns magic."},
                    {"description": "Hero leaves village."}
                ],
                "characters_present": ["Hero", "Mother", "Teacher"]
            }
        )
        
        # Write EP002 facts
        write_json(
            os.path.join(self.micro_dir, f"{self.prefix}_EP002_micro_facts.json"),
            {
                "chapter_id": "EP002",
                "chapter_title": "Second Chapter",
                "key_plot_points": [
                    {"description": "Hero enters forest."},
                    {"description": "Hero fights goblin."}
                ],
                "characters_present": ["Hero", "Goblin"]
            }
        )

    def tearDown(self):
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)

    def test_generate_summary_for_first_chapter(self):
        # EP001 should have no previous chapter summaries
        summaries = generate_previous_chapters_summary(self.test_dir, self.prefix, "EP001")
        self.assertEqual(summaries, [])

    def test_generate_summary_for_second_chapter(self):
        # EP002 should have EP001 in summary
        summaries = generate_previous_chapters_summary(self.test_dir, self.prefix, "EP002")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["chapter"], "EP001")
        self.assertEqual(summaries[0]["chapter_title"], "First Chapter")
        self.assertEqual(summaries[0]["key_events"], ["Hero is born.", "Hero learns magic.", "Hero leaves village."])
        self.assertEqual(summaries[0]["characters_present"], ["Hero", "Mother", "Teacher"])
        self.assertEqual(summaries[0]["new_characters_introduced"], ["Hero", "Mother", "Teacher"])

    def test_generate_summary_for_third_chapter(self):
        # EP003 should have EP001 and EP002 in summary
        summaries = generate_previous_chapters_summary(self.test_dir, self.prefix, "EP003")
        self.assertEqual(len(summaries), 2)
        # EP001
        self.assertEqual(summaries[0]["chapter"], "EP001")
        # EP002
        self.assertEqual(summaries[1]["chapter"], "EP002")
        self.assertEqual(summaries[1]["key_events"], ["Hero enters forest.", "Hero fights goblin."])
        # Goblin is new in EP002 because Hero was already seen in EP001
        self.assertEqual(summaries[1]["new_characters_introduced"], ["Goblin"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
