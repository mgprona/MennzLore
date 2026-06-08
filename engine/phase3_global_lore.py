#!/usr/bin/env python3
"""
Phase 3.1 — Global Lore + Name Map
====================================
อ่าน clean/EP*.txt ทั้งหมด → สร้าง prompt → เรียก OpenAI Structured Outputs
→ เขียน verification/ ทั้ง 4 ไฟล์ + อัปเดต pipeline_state.json

Output files:
  verification/<prefix>_global_lore.json
  verification/<prefix>_name_map.json
  verification/<prefix>_timeline_framework.json
  verification/<prefix>_chapter_appearance.json

Usage:
    python engine/phase3_global_lore.py <project_dir> [prefix]

Requires:
    pip install openai
    OPENAI_API_KEY in environment
"""

import json
import os
import sys
import glob as _glob
from datetime import datetime, timezone

try:
    from pipeline_state import PipelineState
    _HAS_STATE = True
except ImportError:
    _HAS_STATE = False


# ── prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a literary lore analyst. You read the full text of a novel split into chapters and produce four structured JSON artefacts.

RULES:
1. Every fact must be sourced from the text — no invention.
2. Preserve exact spelling of all proper nouns (character names, place names, creature names, invented words).
3. lore_type values: "normal" (recognisable English word/name), "fantasy_name" (invented proper noun), "in_world_language" (word from the story's fictional language).
4. episode IDs use format EP001, EP002, ... EP0NN (zero-padded 3 digits).
5. Return ONLY a JSON object with exactly four top-level keys: global_lore, name_map, timeline_framework, chapter_appearance.
"""

def _build_user_prompt(prefix: str, chapters: list[tuple[str, str]]) -> str:
    """chapters = [(ep_id, text), ...]"""
    chapter_block = "\n\n".join(
        f"=== {ep_id} ===\n{text[:6000]}"   # truncate very long chapters to stay within context
        for ep_id, text in chapters
    )
    return f"""Project prefix: {prefix}
Total chapters: {len(chapters)}

CHAPTER TEXTS:
{chapter_block}

Produce exactly this JSON structure (no extra keys, no markdown wrapper):

{{
  "global_lore": {{
    "book_metadata": {{
      "title": "...",
      "author": "...",
      "project": "{prefix}",
      "total_chapters": {len(chapters)},
      "genre": ["..."],
      "series_context": "...",
      "main_theme": "...",
      "narrative_device": "...",
      "timespan": "...",
      "pov_characters": ["..."],
      "proper_noun_guard": "Active. Preserve exact source spelling."
    }},
    "characters": [ {{
      "name": "...", "role": "...", "core_identity": "...", "character_arc": "...",
      "visual_profile": "...",
      "key_relationships": [{{"with": "...", "relation_type": "..."}}],
      "first_appearance": "EP001",
      "chapters_present": ["EP001"],
      "status_at_end": "..."
    }} ],
    "mystery_and_clues_tracker": [ {{
      "mystery": "...", "introduced_in_chapter": "EP001", "resolved_in_chapter": "EP008",
      "clues": ["..."], "resolution": "...", "significance": "..."
    }} ],
    "global_timeline_milestones": [ {{
      "chapter_range": "EP001", "event_summary": "...", "world_state_change": "..."
    }} ],
    "world_building_and_motifs": [ {{
      "concept": "...", "type": "...", "description": "...", "significance_to_plot": "..."
    }} ]
  }},

  "name_map": {{
    "project": "{prefix}",
    "generated_phase": "3.1",
    "name_map": {{
      "Canonical Name": {{
        "aliases": ["..."],
        "type": "character|location|organization|creature|concept|object|vehicle|technology|culture|motif|ritual_phrase|historical_event|language",
        "lore_type": "normal|fantasy_name|in_world_language",
        "primary_source": "EP001",
        "episodes": ["EP001"]
      }}
    }}
  }},

  "timeline_framework": {{
    "project": "{prefix}",
    "timeline_framework": [ {{
      "chapter_id": "EP001",
      "title": "CHAPTER I",
      "day": 1,
      "relative_time": "...",
      "primary_location": "...",
      "summary": "...",
      "major_milestone_refs": [0],
      "continuity_notes": "..."
    }} ]
  }},

  "chapter_appearance": {{
    "project": "{prefix}",
    "chapter_appearance": {{
      "EP001": {{
        "characters_present": ["..."],
        "mentioned_only": ["..."],
        "locations": ["..."],
        "creatures": ["..."],
        "concepts": ["..."]
      }}
    }}
  }}
}}
"""


# ── LLM call ─────────────────────────────────────────────────────────────────

def call_llm(system: str, user: str, model: str = "gpt-4o") -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("pip install openai  (then set OPENAI_API_KEY)")

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.1,
    )
    raw = resp.choices[0].message.content
    return json.loads(raw)


# ── main ─────────────────────────────────────────────────────────────────────

def run_phase3_global_lore(project_dir: str, prefix: str, model: str = "gpt-4o") -> dict:
    print(f"\nPhase 3.1 — Global Lore + Name Map")
    print(f"  Project: {project_dir}  |  Prefix: {prefix}")

    # 1. load clean chapters
    pattern = os.path.join(project_dir, "clean", f"{prefix}_EP*.txt")
    paths = sorted(_glob.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No clean files found: {pattern}")

    chapters = []
    for p in paths:
        ep_id = os.path.basename(p).replace(f"{prefix}_", "").replace(".txt", "")
        with open(p, encoding="utf-8") as f:
            chapters.append((ep_id, f.read()))
    print(f"  Loaded {len(chapters)} chapters: {[ep for ep, _ in chapters]}")

    # 2. call LLM
    print(f"  Calling {model} …")
    user_prompt = _build_user_prompt(prefix, chapters)
    result = call_llm(SYSTEM_PROMPT, user_prompt, model=model)

    # 3. validate top-level keys
    required = {"global_lore", "name_map", "timeline_framework", "chapter_appearance"}
    missing = required - set(result.keys())
    if missing:
        raise ValueError(f"LLM response missing keys: {missing}")

    # 4. write output files
    ver_dir = os.path.join(project_dir, "verification")
    os.makedirs(ver_dir, exist_ok=True)

    outputs = {
        "global_lore":        f"{prefix}_global_lore.json",
        "name_map":           f"{prefix}_name_map.json",
        "timeline_framework": f"{prefix}_timeline_framework.json",
        "chapter_appearance": f"{prefix}_chapter_appearance.json",
    }
    for key, filename in outputs.items():
        out_path = os.path.join(ver_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result[key], f, ensure_ascii=False, indent=2)
        print(f"  Wrote: {out_path}")

    # 5. pipeline state
    nm = result["name_map"].get("name_map", {})
    wb = result["global_lore"].get("world_building_and_motifs", [])
    chars = result["global_lore"].get("characters", [])
    tl = result["timeline_framework"].get("timeline_framework", [])
    ca = result["chapter_appearance"].get("chapter_appearance", {})

    if _HAS_STATE:
        ps = PipelineState(project_dir, prefix)
        ps.set_phase("3_global_lore", "COMPLETE",
                     outputs=[f"verification/{v}" for v in outputs.values()],
                     mode="phase3_global_lore_script")
        ps.set_phase("3_name_map", "COMPLETE",
                     file=f"verification/{outputs['name_map']}",
                     entries=len(nm))

    print(f"\nPhase 3.1 complete  — {len(chars)} chars, {len(wb)} world items, "
          f"{len(nm)} name_map entries, {len(tl)} timeline entries, {len(ca)} chapter_appearance entries")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python engine/phase3_global_lore.py <project_dir> [prefix] [model]")
        sys.exit(1)
    _dir   = sys.argv[1].rstrip("/\\")
    _pfx   = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(_dir)
    _model = sys.argv[3] if len(sys.argv) > 3 else "gpt-4o"
    run_phase3_global_lore(_dir, _pfx, model=_model)
