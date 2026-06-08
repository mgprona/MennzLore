#!/usr/bin/env python3
"""
Pipeline State Manager
======================
Single source of truth for phase tracking across the MennzLore pipeline.

State file: <project_dir>/<prefix>_pipeline_state.json

Usage (from other scripts):
    from pipeline_state import PipelineState
    ps = PipelineState(project_dir, prefix)
    ps.set_phase("1_acquisition", "COMPLETE", source=url, chars=n)
    ps.set_phase("2_clean", "COMPLETE", files=8)
    info = ps.get_phase("1_acquisition")
"""

import json
import os
from datetime import datetime, timezone


PIPELINE_VERSION = "v2.1"


class PipelineState:
    def __init__(self, project_dir: str, prefix: str):
        self.project_dir = project_dir
        self.prefix = prefix
        self.path = os.path.join(project_dir, f"{prefix}_pipeline_state.json")
        self._state = self._load()

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        return {"_meta": {}, "phases": {}}

    def _save(self):
        os.makedirs(os.path.dirname(self.path) if os.path.dirname(self.path) else ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    # ── meta ─────────────────────────────────────────────────────────────────

    def init_meta(self, *, gutenberg_id: int, title: str, source: str):
        self._state["_meta"] = {
            "project":          self.prefix,
            "book_id":          gutenberg_id,
            "title":            title,
            "status":           "ACQUIRED",
            "source":           source,
            "created":          _now(),
            "pipeline_version": PIPELINE_VERSION,
        }
        self._save()

    # ── phases ────────────────────────────────────────────────────────────────

    def set_phase(self, phase_id: str, status: str, **kwargs):
        """Write or overwrite a phase entry. Extra kwargs become top-level fields."""
        entry = {"status": status}
        entry.update(kwargs)
        self._state.setdefault("phases", {})[phase_id] = entry
        self._save()

    def get_phase(self, phase_id: str) -> dict:
        return self._state.get("phases", {}).get(phase_id, {})

    def is_complete(self, phase_id: str) -> bool:
        return self.get_phase(phase_id).get("status") == "COMPLETE"

    # ── display ───────────────────────────────────────────────────────────────

    def summary(self) -> str:
        lines = [f"Pipeline: {self.prefix}  (v{self._state.get('_meta', {}).get('pipeline_version', '?')})"]
        for phase_id, data in self._state.get("phases", {}).items():
            lines.append(f"  {phase_id:<20} {data.get('status', '?')}")
        return "\n".join(lines)


# ── standalone backfill CLI ───────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def backfill(project_dir: str, prefix: str):
    """
    Read existing artefacts and write a pipeline_state.json that reflects
    what has already been completed (Phase 1 + Phase 2).
    """
    import glob as _glob

    ps = PipelineState(project_dir, prefix)

    # ── _meta from verification/source.json ──────────────────────────────────
    src_path = os.path.join(project_dir, "verification", f"{prefix}_source.json")
    if os.path.exists(src_path):
        with open(src_path, encoding="utf-8") as f:
            src = json.load(f)
        ps._state["_meta"] = {
            "project":          prefix,
            "book_id":          src.get("gutenberg_id", 0),
            "title":            src.get("title", prefix),
            "status":           "ACQUIRED",
            "source":           src.get("source", "gutenberg"),
            "created":          src.get("fetched_at", _now()),
            "pipeline_version": PIPELINE_VERSION,
        }
    else:
        # fallback: infer from raw file
        raw_path = os.path.join(project_dir, "raw", f"{prefix}_full.txt")
        raw_bytes = os.path.getsize(raw_path) if os.path.exists(raw_path) else 0
        ps._state["_meta"] = {
            "project":          prefix,
            "status":           "ACQUIRED",
            "source":           "gutenberg",
            "created":          _now(),
            "pipeline_version": PIPELINE_VERSION,
        }

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    raw_path = os.path.join(project_dir, "raw", f"{prefix}_full.txt")
    if os.path.exists(raw_path):
        ps.set_phase("1_acquisition", "COMPLETE",
                     file=f"raw/{prefix}_full.txt",
                     chars=os.path.getsize(raw_path))
        print(f"  Phase 1  COMPLETE  ({os.path.getsize(raw_path):,} bytes)")
    else:
        print(f"  Phase 1  MISSING raw file — skipped")

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    clean_files = sorted(_glob.glob(os.path.join(project_dir, "clean", f"{prefix}_EP*.txt")))
    if clean_files:
        chapter_sizes = {os.path.basename(p): os.path.getsize(p) for p in clean_files}
        ps.set_phase("2_clean", "COMPLETE",
                     files=len(clean_files),
                     chapter_chars={k: v for k, v in chapter_sizes.items()})
        print(f"  Phase 2  COMPLETE  ({len(clean_files)} files)")
    else:
        print(f"  Phase 2  no clean files found — skipped")

    ps._save()
    print(f"\n  State written: {ps.path}")
    return ps


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python engine/pipeline_state.py <project_dir> [prefix]")
        sys.exit(1)
    _dir = sys.argv[1].rstrip("/\\")
    _pfx = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(_dir)
    print(f"\nBackfilling pipeline state for: {_pfx}\n")
    _ps = backfill(_dir, _pfx)
    print()
    print(_ps.summary())
