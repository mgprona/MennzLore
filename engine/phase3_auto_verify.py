#!/usr/bin/env python3
"""
Phase 3.2 — Auto Verify
========================
ตรวจสอบ name_map vs clean files โดยไม่ใช้ LLM
→ เขียน qa/validation/phase3_2_auto_verify_report.json
→ อัปเดต pipeline_state.json

Usage:
    python engine/phase3_auto_verify.py <project_dir> [prefix]
"""

import json
import os
import re
import sys
import glob as _glob
from datetime import datetime, timezone

try:
    from pipeline_state import PipelineState
    _HAS_STATE = True
except ImportError:
    _HAS_STATE = False


# ── helpers ───────────────────────────────────────────────────────────────────

_FANTASY_LORE_TYPES = {"fantasy_name", "in_world_language"}


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_clean_texts(project_dir: str, prefix: str) -> dict[str, str]:
    """Return {ep_id: text} for all clean files."""
    result = {}
    for p in sorted(_glob.glob(os.path.join(project_dir, "clean", f"{prefix}_EP*.txt"))):
        ep_id = os.path.basename(p).replace(f"{prefix}_", "").replace(".txt", "")
        with open(p, encoding="utf-8") as f:
            result[ep_id] = f.read()
    return result


def _as_list(value) -> list:
    """Coerce a value into a list of strings.

    Defensive against LLM output that may produce either a single string
    ("EP001") or a list (["EP001"]) for fields like ``aliases`` and
    ``episodes``. The MCP ``{"item": ...}`` unwrap can also collapse a
    one-element list into a bare string. Without this guard, the strict
    ``list + list`` concatenation in ``_check_name_in_texts`` raises
    ``TypeError: can only concatenate list (not "str") to list``.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(x) for x in value if x is not None]
    return [str(value)]


def _check_name_in_texts(name: str, aliases, texts: dict[str, str]) -> list[str]:
    """Return list of ep_ids where canonical name OR any alias appears."""
    found = []
    terms = [name] + _as_list(aliases)
    for ep_id, text in texts.items():
        for term in terms:
            if term and re.search(re.escape(term), text, re.IGNORECASE):
                found.append(ep_id)
                break
    return found


# ── main verify ───────────────────────────────────────────────────────────────

def run_auto_verify(project_dir: str, prefix: str) -> dict:
    print(f"\nPhase 3.2 — Auto Verify")
    print(f"  Project: {project_dir}  |  Prefix: {prefix}")

    # load name_map
    nm_path = os.path.join(project_dir, "verification", f"{prefix}_name_map.json")
    if not os.path.exists(nm_path):
        raise FileNotFoundError(f"name_map not found: {nm_path}")
    nm_data = _load_json(nm_path)
    name_map: dict = nm_data.get("name_map", {})

    # load clean texts
    texts = _load_clean_texts(project_dir, prefix)
    clean_files = len(texts)
    if not clean_files:
        raise FileNotFoundError(f"No clean files in {project_dir}/clean/")

    errors = []
    ellipsis_paths = []
    foreign_script_paths = []

    # ── check 1: JSON files valid (name_map loaded = valid) ──────────────────
    json_files_valid = True

    # ── check 2: ellipsis / truncation in name_map values ────────────────────
    nm_raw = json.dumps(nm_data)
    if "…" in nm_raw or "..." in nm_raw:
        ellipsis_paths.append(nm_path)

    # ── check 3: foreign script in clean files ────────────────────────────────
    _foreign = re.compile(r'[\u0e00-\u0e7f\u4e00-\u9fff\u0400-\u04ff]')  # Thai/CJK/Cyrillic
    for ep_id, text in texts.items():
        if _foreign.search(text):
            foreign_script_paths.append(f"clean/{prefix}_{ep_id}.txt")

    # ── check 4: name_map episodes declared vs actually found in text ─────────
    not_found_in_declared = []
    for canonical, data in name_map.items():
        declared_eps = set(_as_list(data.get("episodes", [])))
        aliases = data.get("aliases", [])
        found_eps = set(_check_name_in_texts(canonical, aliases, texts))
        # flag entries where declared episodes have ZERO hits at all
        if declared_eps and not found_eps:
            not_found_in_declared.append(canonical)
            errors.append(f"'{canonical}' declared in {sorted(declared_eps)} but found nowhere in clean texts")

    # ── stats ─────────────────────────────────────────────────────────────────
    total = len(name_map)
    fantasy_count = sum(
        1 for d in name_map.values()
        if d.get("lore_type") in _FANTASY_LORE_TYPES
    )
    fantasy_ratio = round(fantasy_count / total, 4) if total else 0.0

    # character count from global_lore if available
    gl_path = os.path.join(project_dir, "verification", f"{prefix}_global_lore.json")
    global_characters = 0
    if os.path.exists(gl_path):
        gl = _load_json(gl_path)
        global_characters = len(gl.get("characters", []))

    # timeline entries
    tl_path = os.path.join(project_dir, "verification", f"{prefix}_timeline_framework.json")
    timeline_entries = 0
    if os.path.exists(tl_path):
        tl = _load_json(tl_path)
        timeline_entries = len(tl.get("timeline_framework", []))

    # chapter_appearance entries
    ca_path = os.path.join(project_dir, "verification", f"{prefix}_chapter_appearance.json")
    chapter_appearance_entries = 0
    if os.path.exists(ca_path):
        ca = _load_json(ca_path)
        chapter_appearance_entries = len(ca.get("chapter_appearance", {}))

    status = "PASS" if not errors and not ellipsis_paths and not foreign_script_paths else "FAIL"

    report = {
        "status":                    status,
        "clean_files":               clean_files,
        "json_files_valid":          json_files_valid,
        "global_characters":         global_characters,
        "world_items":               total,
        "name_map_entries":          total,
        "fantasy_or_in_world_entries": fantasy_count,
        "fantasy_ratio":             fantasy_ratio,
        "timeline_entries":          timeline_entries,
        "chapter_appearance_entries": chapter_appearance_entries,
        "errors":                    errors,
        "ellipsis_paths":            ellipsis_paths,
        "foreign_script_paths":      foreign_script_paths,
        "verdict":                   "Phase 3.1/3.2 usable for Phase 4" if status == "PASS"
                                     else "REVIEW REQUIRED before Phase 4",
    }

    # write report
    qa_dir = os.path.join(project_dir, "qa", "validation")
    os.makedirs(qa_dir, exist_ok=True)
    report_path = os.path.join(qa_dir, "phase3_2_auto_verify_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  Report: {report_path}")

    # pipeline state
    if _HAS_STATE:
        ps = PipelineState(project_dir, prefix)
        ps.set_phase("3_auto_verify", status,
                     file=f"qa/validation/phase3_2_auto_verify_report.json",
                     name_map_entries=total,
                     fantasy_ratio=fantasy_ratio)

    print(f"  Status: {status}  |  {total} name_map entries  |  fantasy_ratio={fantasy_ratio}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")

    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python engine/phase3_auto_verify.py <project_dir> [prefix]")
        sys.exit(1)
    _dir = sys.argv[1].rstrip("/\\")
    _pfx = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(_dir)
    report = run_auto_verify(_dir, _pfx)
    print(f"\nVerdict: {report['verdict']}")
