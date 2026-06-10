"""
tests/test_phase3_refactoring.py
================================
Unit tests for engine/phase3_global_lore.py improvements:
  - extract_name_candidates (Phase 3.1a pattern candidates regex scan)
  - write_global_lore_outputs skeleton generation (Phase 3.1c)

Run:
    python -m pytest tests/ -v
or:
    python tests/test_phase3_refactoring.py
"""
import sys
import unittest
import tempfile
import shutil
import os
import json
from pathlib import Path

ENGINE_DIR = Path(__file__).parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR.parent))

from engine.phase3_global_lore import extract_name_candidates, write_global_lore_outputs

class TestPhase3Refactoring(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.prefix = "testrefactor"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_extract_name_candidates(self):
        chapters = [
            ("EP001", "This is a story about Mr. Sherlock Holmes and his companion Dr. Watson. Watson was there. Watson was helpful. Holmes was thinking."),
            ("EP002", "We met Sir Arthur in the park. Arthur was walking. Arthur was talking. Miss Adler was also present in London.")
        ]
        candidates = extract_name_candidates(chapters)
        
        # Sherlock Holmes matched via prefix Mr.
        # Watson matched because appearing 3 times (Watson, Watson, Watson)
        # Arthur matched because appearing 3 times
        # Adler matched via Miss
        self.assertIn("Mr. Sherlock Holmes", candidates)
        self.assertIn("Dr. Watson", candidates)
        self.assertIn("Sir Arthur", candidates)
        self.assertIn("Miss Adler", candidates)
        self.assertIn("Watson", candidates)
        self.assertIn("Arthur", candidates)
        # Stopwords like 'This', 'We', 'The' should be filtered out
        self.assertNotIn("This", candidates)
        self.assertNotIn("We", candidates)

    def test_write_global_lore_outputs_skeleton_generation(self):
        # Input only contains name_map and chapter_appearance (optimized names-only LLM output)
        result = {
            "name_map": {
                "project": self.prefix,
                "generated_phase": "3.1",
                "name_map": {
                    "Sherlock Holmes": {
                        "aliases": ["Holmes"],
                        "type": "character",
                        "lore_type": "normal",
                        "primary_source": "EP001",
                        "episodes": ["EP001", "EP002"]
                    },
                    "Dr. Watson": {
                        "aliases": ["Watson"],
                        "type": "character",
                        "lore_type": "normal",
                        "primary_source": "EP001",
                        "episodes": ["EP001"]
                    }
                }
            },
            "chapter_appearance": {
                "project": self.prefix,
                "chapter_appearance": {
                    "EP001": {
                        "characters_present": ["Sherlock Holmes", "Dr. Watson"]
                    },
                    "EP002": {
                        "characters_present": ["Sherlock Holmes"]
                    }
                }
            }
        }
        
        stats = write_global_lore_outputs(self.test_dir, self.prefix, result)
        
        # Verify return values
        self.assertEqual(stats["characters"], 2)
        self.assertEqual(stats["name_map_entries"], 2)
        self.assertEqual(stats["timeline_entries"], 2)
        self.assertEqual(stats["chapter_appearance_entries"], 2)
        
        # Verify files generated in verification/
        ver_dir = os.path.join(self.test_dir, "verification")
        
        # Check global_lore skeleton
        gl_path = os.path.join(ver_dir, f"{self.prefix}_global_lore.json")
        self.assertTrue(os.path.exists(gl_path))
        with open(gl_path, "r", encoding="utf-8") as f:
            gl = json.load(f)
        self.assertEqual(gl["book_metadata"]["project"], self.prefix)
        self.assertEqual(len(gl["characters"]), 2)
        self.assertEqual(gl["characters"][0]["name"], "Sherlock Holmes")
        self.assertEqual(gl["characters"][0]["role"], "Character")
        self.assertEqual(gl["characters"][1]["name"], "Dr. Watson")
        
        # Check timeline skeleton
        tl_path = os.path.join(ver_dir, f"{self.prefix}_timeline_framework.json")
        self.assertTrue(os.path.exists(tl_path))
        with open(tl_path, "r", encoding="utf-8") as f:
            tl = json.load(f)
        self.assertEqual(len(tl["timeline_framework"]), 2)
        self.assertEqual(tl["timeline_framework"][0]["chapter_id"], "EP001")
        self.assertEqual(tl["timeline_framework"][0]["title"], "CHAPTER 1")
        self.assertEqual(tl["timeline_framework"][1]["chapter_id"], "EP002")

if __name__ == "__main__":
    unittest.main(verbosity=2)
