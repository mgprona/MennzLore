"""
tests/test_failfast.py
======================
Bug #6 + Bug #10 — engine must raise FileNotFoundError quickly when
upstream inputs are missing (not sys.exit(1) which hangs the MCP tool
until the 120s timeout).
"""
import os
import sys
import time
import unittest
import tempfile
import shutil
from pathlib import Path

ENGINE_DIR = Path(__file__).parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))  # for `from lore_models import ...` in engine/*.py
sys.path.insert(0, str(ENGINE_DIR.parent))  # for `from engine.X import ...`


class TestMergeFailFast(unittest.TestCase):
    """Bug #10 — merge_to_micro_facts must raise fast, not exit."""

    def test_missing_3pass_files_raises_fast(self):
        from engine.merge_to_micro_facts import merge_to_micro_facts

        with tempfile.TemporaryDirectory() as tmpdir:
            # No analysis/sa_raw/ files at all
            start = time.time()
            with self.assertRaises(FileNotFoundError) as ctx:
                merge_to_micro_facts("test-prefix", "EP001", base_dir=tmpdir)
            elapsed = time.time() - start
            self.assertLess(elapsed, 2.0, f"Took {elapsed}s, should be <2s")
            # Message should be informative
            self.assertIn("Missing 3-Pass input", str(ctx.exception))
            self.assertIn("architect", str(ctx.exception))


class TestAssembleFailFast(unittest.TestCase):
    """Bug #6 — assemble_lorebook must raise fast when micro_facts/ missing."""

    def test_missing_micro_facts_raises_fast(self):
        from engine.assemble_generic import assemble_lorebook

        with tempfile.TemporaryDirectory() as tmpdir:
            start = time.time()
            with self.assertRaises(FileNotFoundError) as ctx:
                assemble_lorebook(tmpdir, "test-prefix")
            elapsed = time.time() - start
            self.assertLess(elapsed, 2.0, f"Took {elapsed}s, should be <2s")
            self.assertIn("micro_facts", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
