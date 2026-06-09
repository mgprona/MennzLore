#!/usr/bin/env python3
"""
Phase 2 — Split & Clean
========================
Split raw full-text into per-chapter files + strip Gutenberg boilerplate.

Supports:
  - "Chapter N" / "CHAPTER N" headings  (e.g. Pride and Prejudice)
  - Standalone Roman numerals            (e.g. Voodoo Planet)
  - "Part N" / "PART N" headings

Heading is detected when:
  - Line matches pattern, AND
  - Both the line before and line after are blank (guards against prose false-positives)

Usage:
    python engine/split_chapters.py <project_dir> [prefix]
"""

import json
import os
import re
import sys

try:
    from pipeline_state import PipelineState
    _HAS_STATE = True
except ImportError:
    _HAS_STATE = False

# ── boilerplate markers (Gutenberg) ──────────────────────────────────────────

_START = re.compile(r'\*{3}\s*START OF THE PROJECT GUTENBERG', re.I)
_END   = re.compile(r'\*{3}\s*END OF THE PROJECT GUTENBERG', re.I)

# Inline editorial annotations that appear as bracketed lines inside chapters
# (e.g. "[Sidenote: ...]", "[Illustration: ...]", "[Frontispiece: ...]",
#        "[Footnote N: ...]", "[Transcriber's note: ...]", "[Translator: ...]").
# These are NOT narrative text — they are production/editorial metadata
# inserted by the Project Gutenberg transcriber. If not stripped, downstream
# LLM extraction will treat them as in-world facts and contaminate the lorebook.
#
# The trailing ":\s*" is intentionally minimal: footnoted entries often have
# a number after the keyword ("[Footnote 1: ...]"), so the colon is not
# required to be the very first non-space char after the keyword. The bracket
# must start the line (anchored ^\s*\[).
_INLINE_ANNOTATION = re.compile(
    r'^\s*\['
    r'(?:'
    r'sidenote|illustration|frontispiece|footnote|translator'
    r'|transcriber(?:\'s)?(?:\s+(?:note|change|comment|change[s]?))?'
    r')'
    r'\b[^]]*?:\s*',
    re.I,
)
# Footer block heading: from this line to end-of-file is the transcriber's
# typo-correction log, which is also non-narrative.
_TRANSCRIBER_FOOTER = re.compile(
    r'^\s*transcriber(?:\'s)?\s+changes\s*:?\s*$',
    re.I,
)

# ── chapter heading patterns ─────────────────────────────────────────────────

_HEADING_PATTERNS = [
    # "Chapter 1", "Chapter One", "Part II" — must be followed by a number,
    # Roman numeral, or spelled-out number-word (guards against TOC lines like
    # "CHAPTER            PAGE" where the trailing word is not an ordinal).
    re.compile(
        r'^(chapter|part)\s+'
        r'(\d+'
        r'|[ivxlcdm]+'
        r'|one|two|three|four|five|six|seven|eight|nine|ten'
        r'|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty'
        r'|thirty|forty|fifty|first|second|third|fourth|fifth|last)'
        r'\b',
        re.I,
    ),
    re.compile(r'^[IVXLC]+\.?\s*$'),                      # I  II  III  IV ...
]


def _is_heading(lines: list[str], i: int) -> bool:
    line = lines[i].strip()
    if not line:
        return False
    if not any(p.match(line) for p in _HEADING_PATTERNS):
        return False
    # Part-level headings ("PART I.", "PART II. _The Country of the Saints._")
    # are NOT chapter breaks. We do not split the book at "PART" boundaries —
    # they are preludes and the next "CHAPTER" inside the part begins the
    # actual episode. Without this guard, books like A Study in Scarlet (PG
    # #244) would produce empty/header-only files for EP001 ("PART I") and
    # EP009 ("PART II"), pushing the real chapter numbering off by one.
    if re.match(r'^\s*part\s+[ivxlcdm]+\.?\s*$', line, re.I):
        return False
    # require blank lines on both sides (prevents false positives mid-prose)
    before = lines[i - 1].strip() if i > 0 else ""
    after  = lines[i + 1].strip() if i < len(lines) - 1 else ""
    return before == "" and after == ""


# ── boilerplate stripping ────────────────────────────────────────────────────

def strip_boilerplate(lines: list[str]) -> list[str]:
    """Remove Gutenberg header/footer if markers present; else return as-is."""
    start, end = None, None
    for i, l in enumerate(lines):
        if _START.search(l) and start is None:
            start = i + 1
        if _END.search(l) and end is None:
            end = i
    if start is not None:
        lines = lines[start : end] if end else lines[start:]
    return lines


def strip_inline_annotations(lines: list[str]) -> list[str]:
    """Drop Gutenberg editorial annotations that appear inside chapter text.

    Handles two formats produced by Project Gutenberg transcribers:
      1. Single-line bracketed metadata, e.g. ``[Illustration: ...]``,
         ``[Sidenote: ...]``, ``[Frontispiece: ...]``. The bracket text may
         wrap to a continuation line; the line(s) are dropped until the
         closing ``]``.
      2. The ``Transcriber's Changes:`` footer block, which is a multi-line
         typo-correction log that is always at the end of the file. Once
         detected, the rest of the chapter is dropped.

    Returns the cleaned list with the metadata removed.
    """
    out: list[str] = []
    in_bracket = False
    in_footer = False
    for line in lines:
        if in_footer:
            # Transcriber's Changes block runs to end of file / end of chapter.
            continue
        if _TRANSCRIBER_FOOTER.match(line):
            in_footer = True
            continue
        if in_bracket:
            # Look for the closing bracket on this or subsequent lines.
            if "]" in line:
                in_bracket = False
                # Keep anything that followed the ']' on the same line —
                # the bracketed annotation always starts the line.
                tail = line.split("]", 1)[1].strip()
                if tail:
                    out.append(tail)
            continue
        if _INLINE_ANNOTATION.match(line):
            # Multi-line bracket: if this line has no ']', keep dropping until
            # we see one.
            if "]" not in line:
                in_bracket = True
            else:
                # Single-line bracket: discard this line entirely. If anything
                # follows the ']', drop it too (it's still part of the
                # annotation caption).
                tail = line.split("]", 1)[1].strip()
                if tail:
                    out.append(tail)
            continue
        out.append(line)
    return out


# ── clean chapter text ───────────────────────────────────────────────────────

def clean_text(lines: list[str]) -> str:
    """Collapse excessive blank lines (3+ → 2) and strip trailing whitespace."""
    out, blanks = [], 0
    for l in lines:
        s = l.rstrip()
        if s == "":
            blanks += 1
            if blanks <= 2:
                out.append("")
        else:
            blanks = 0
            out.append(s)
    return "\n".join(out).strip() + "\n"


# ── main ─────────────────────────────────────────────────────────────────────

def split_chapters(project_dir: str, prefix: str) -> list[dict]:
    raw_path = os.path.join(project_dir, "raw", f"{prefix}_full.txt")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw file not found: {raw_path}")

    with open(raw_path, encoding="utf-8", errors="replace") as f:
        raw = f.read()

    lines = strip_boilerplate(raw.splitlines())
    lines = strip_inline_annotations(lines)

    # find chapter heading line indices
    heading_indices = [i for i in range(len(lines)) if _is_heading(lines, i)]

    if not heading_indices:
        raise ValueError(
            f"No chapter headings detected in {raw_path}.\n"
            f"Checked patterns: 'Chapter N', Roman numerals (I II III...).\n"
            f"Check the raw file and adjust manually if needed."
        )

    # split into chunks: [heading_i .. next_heading_i)
    clean_dir = os.path.join(project_dir, "clean")
    os.makedirs(clean_dir, exist_ok=True)

    # clear stale EP files from a previous run so a shorter split can't leave
    # orphaned chapters that downstream phases would miscount
    import glob as _glob
    for stale in _glob.glob(os.path.join(clean_dir, f"{prefix}_EP*.txt")):
        os.remove(stale)

    chapters = []
    for ep_idx, hi in enumerate(heading_indices):
        ep_num  = ep_idx + 1
        hi_next = heading_indices[ep_idx + 1] if ep_idx + 1 < len(heading_indices) else len(lines)
        chapter_lines = lines[hi:hi_next]
        heading_text  = lines[hi].strip()
        content       = clean_text(chapter_lines)

        ep_id    = f"EP{ep_num:03d}"
        out_path = os.path.join(clean_dir, f"{prefix}_{ep_id}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        chapters.append({
            "ep_id":        ep_id,
            "ep_num":       ep_num,
            "heading":      heading_text,
            "line_start":   hi + 1,
            "line_end":     hi_next,
            "char_count":   len(content),
            "file":         f"clean/{prefix}_{ep_id}.txt",
        })
        print(f"  {ep_id}  {heading_text:<12}  {len(content):>7,} chars  -> {out_path}")

    # write manifest
    manifest = {
        "prefix":         prefix,
        "total_episodes": len(chapters),
        "ep_numbering":   "EP###",
        "chapters":       chapters,
    }
    manifest_path = os.path.join(project_dir, "verification", f"{prefix}_chapters.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n  {len(chapters)} chapters -> clean/")
    print(f"  Manifest: {manifest_path}")

    if _HAS_STATE:
        ps = PipelineState(project_dir, prefix)
        ps.set_phase("2_clean", "COMPLETE", files=len(chapters))

    return chapters


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python engine/split_chapters.py <project_dir> [prefix]")
        sys.exit(1)
    project_dir = sys.argv[1].rstrip("/\\")
    prefix = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(project_dir)
    print(f"\nPhase 2 — Split & Clean\n  Project: {project_dir}\n  Prefix:  {prefix}\n")
    split_chapters(project_dir, prefix)
    print("\nPhase 2 complete.")
