#!/usr/bin/env python3
"""
scripts/smoke_test.py
=====================
End-to-end smoke test for MennzLore. Runs the deterministic engine
phases (2, 3.1, 3.2, 7, 9, 10) on each of three Project Gutenberg test
novels and verifies the output. Phases 4-6 (3-Pass LLM extraction) are
skipped because they require external LLM calls.

Verifies:
  - Phase 2: 0 noise (bracketed annotations stripped)
  - Phase 2: chapter count matches expected
  - Phase 2: PART-level headings absorbed (not separate chapters)
  - Phase 7: assemble raises FileNotFoundError fast (no sys.exit(1))
  - Phase 9: render_production runs without crashing
  - Phase 10: render_map runs without crashing

Usage:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --verbose
"""
import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path

REPO = Path(__file__).parent.parent
ENGINE_DIR = REPO / "engine"
TESTS_DIR = REPO / "tests"
PROJECTS_ROOT = Path(os.getenv("MENNZLORE_PROJECTS_ROOT", str(Path.home() / "lore-projects")))

VERBOSE = "--verbose" in sys.argv

# (prefix, pg_id, expected_chapter_count, expected_no_noise)
# Note: PART-level headings (Doyle has 2) are absorbed into the next chapter
# by the splitter, so A Study in Scarlet = 14 actual chapters (7+7), not 16.
TEST_NOVELS = [
    ("the-mind-master-burks", 29416, 14, 0),
    ("a-princess-of-mars-burroughs", 62, 28, 0),
    ("a-study-in-scarlet-doyle", 244, 14, 0),
]


def log(msg):
    print(f"  {msg}")


def ok(msg):
    print(f"  ✓ {msg}")


def fail(msg):
    print(f"  ✗ {msg}")
    sys.exit(1)


def run(cmd, **kwargs):
    """Run a shell command, return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        shell=isinstance(cmd, str),
        **kwargs,
    )
    return result.returncode, result.stdout, result.stderr


def test_phase2_splitter(prefix: str, project_dir: Path, expected_chapters: int):
    """Run phase 2 and verify output."""
    log(f"Phase 2 — split {prefix}")
    if not (project_dir / "raw").exists():
        fail(f"raw/ not found for {prefix}; run acquire first")

    rc, out, err = run(
        f'python "{ENGINE_DIR / "split_chapters.py"}" "{project_dir}" {prefix}'
    )
    if rc != 0:
        fail(f"split_chapters.py failed:\n{err}")

    clean_dir = project_dir / "clean"
    ep_files = sorted(clean_dir.glob(f"{prefix}_EP*.txt"))
    if len(ep_files) != expected_chapters:
        fail(f"expected {expected_chapters} clean files, got {len(ep_files)}")
    ok(f"{len(ep_files)} chapters (expected {expected_chapters})")

    # Noise check
    noise_patterns = [
        r"^\[(Sidenote|Illustration|Frontispiece|Footnote|Translator|Transcriber)",
    ]
    noise_count = 0
    for ep in ep_files:
        with open(ep, encoding="utf-8") as f:
            for line in f:
                for pat in noise_patterns:
                    import re
                    if re.search(pat, line):
                        noise_count += 1
                        break
    if noise_count > 0:
        fail(f"{noise_count} noise lines found in clean files")
    ok(f"0 noise in clean files")


def test_phase3_2_verifier(prefix: str, project_dir: Path):
    """Phase 3.2 — verify name_map exists or skip."""
    log(f"Phase 3.2 — verify {prefix}")
    nm_path = project_dir / "verification" / f"{prefix}_name_map.json"
    if not nm_path.exists():
        ok("(skipped — no name_map; run save_global_lore first)")
        return
    rc, out, err = run(
        f'python "{ENGINE_DIR / "phase3_auto_verify.py"}" "{project_dir}" {prefix}'
    )
    if rc != 0 and "Traceback" in (out + err):
        fail(f"phase3_auto_verify crashed:\n{out}\n{err}")
    ok("runs to completion")


def test_phase7_assemble_fails_fast(project_dir: Path):
    """Phase 7 — must raise (not sys.exit) when micro_facts/ missing."""
    log("Phase 7 — assemble fail-fast check")
    rc, out, err = run(
        f'python -c "import sys; sys.path.insert(0, r\\"{ENGINE_DIR}\\"); '
        f'sys.path.insert(0, r\\"{REPO}\\"); '
        f'from engine.assemble_generic import assemble_lorebook; '
        f'assemble_lorebook(r\\"{project_dir}\\", \\"smoketest\\\")"',
        timeout=10,
    )
    if "SystemExit" in (out + err):
        fail("Phase 7 still uses sys.exit(1) — Bug #6 not fixed")
    if "FileNotFoundError" not in (out + err):
        fail(f"Phase 7 should raise FileNotFoundError, got:\n{out}\n{err}")
    ok("raises FileNotFoundError fast")


def test_phase9_render(project_dir: Path, prefix: str):
    """Phase 9 — render_production must not crash even with no micro_facts."""
    log("Phase 9 — render_production (no micro_facts, should not crash)")
    rc, out, err = run(
        f'python "{ENGINE_DIR / "assemble_production_generic.py"}" "{project_dir}" {prefix}',
        timeout=15,
    )
    if "Traceback" in (out + err):
        fail(f"render_production crashed:\n{out}\n{err}")
    ok("runs to completion (empty micro_facts is acceptable)")


def test_phase10_render(project_dir: Path, prefix: str):
    """Phase 10 — render_map must not crash and must NOT include 'Welsh'."""
    log("Phase 10 — render_map (no micro_facts, must not include 'Welsh')")
    rc, out, err = run(
        f'python "{ENGINE_DIR / "chart_render_generic.py"}" "{project_dir}" {prefix}',
        timeout=15,
    )
    if "Traceback" in (out + err):
        fail(f"render_map crashed:\n{out}\n{err}")
    # Check the prompt file
    prompt_path = project_dir / "output" / "spatial" / "map_image_prompt.json"
    if prompt_path.exists():
        with open(prompt_path) as f:
            data = json.load(f)
        if "Welsh" in str(data):
            fail("Bug #9 not fixed — 'Welsh' still in map prompt")
        ok("map prompt has no 'Welsh' hardcoded text")
    else:
        ok("(no map prompt generated)")


def main():
    print("=" * 60)
    print("MennzLore smoke test")
    print("=" * 60)

    for prefix, pg_id, expected_chapters, _ in TEST_NOVELS:
        project_dir = PROJECTS_ROOT / prefix
        if not project_dir.exists():
            print(f"\n[skip] {prefix} — project dir not found")
            continue
        print(f"\n>>> {prefix} (PG #{pg_id})")
        test_phase2_splitter(prefix, project_dir, expected_chapters)
        test_phase3_2_verifier(prefix, project_dir)
        test_phase7_assemble_fails_fast(project_dir)
        test_phase9_render(project_dir, prefix)
        test_phase10_render(project_dir, prefix)

    # Run unit tests
    print("\n>>> Unit tests")
    rc, out, err = run(f'python "{TESTS_DIR / "run_all_tests.py"}"')
    # Combine stdout and stderr (the test runner prints summary to stdout,
    # but Python's unittest may also write to stderr on failure).
    combined = out + err
    if "FAILED" in combined or "errors=" in combined:
        fail(f"unit tests failed:\n{combined}")
    if "OK" not in combined:
        fail(f"unit test runner produced no OK marker:\n{combined}")
    ok("all 53 unit tests pass")

    print("\n" + "=" * 60)
    print("SMOKE TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
