#!/usr/bin/env python3
"""
Pass 1.4: Merge & Validate (Pydantic V2)
=========================================
Reads 3 JSON files (architect, profiler, chronicler) representing 3 analysis passes
of a single chapter, merges them, validates them against Pydantic models, and writes 
the final micro_facts JSON.
"""
import os
import sys
import json

from lore_models import MicroFactsFinal

try:
    from engine.utils import load_json, write_json
except ImportError:
    from utils import load_json, write_json


def merge_to_micro_facts(prefix: str, ep_num: str, base_dir: str | None = None):
    if base_dir is None:
        base_dir = os.getcwd()

    sa_raw = os.path.join(base_dir, "analysis", "sa_raw")
    micro_dir = os.path.join(base_dir, "micro_facts")

    paths = {
        "architect": os.path.join(sa_raw, f"{prefix}_{ep_num}_sa_architect.json"),
        "profiler": os.path.join(sa_raw, f"{prefix}_{ep_num}_sa_profiler.json"),
        "chronicler": os.path.join(sa_raw, f"{prefix}_{ep_num}_sa_chronicler.json"),
    }

    errors = []
    loaded = {}
    for role, path in paths.items():
        if not os.path.exists(path):
            errors.append(f"Missing {role}: {path}")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded[role] = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in {role}: {e}")

    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
        sys.exit(1)

    arch = loaded["architect"]
    prof = loaded["profiler"]
    chron = loaded["chronicler"]

    merged = {
        "chapter_id": arch.get("chapter_id", ep_num),
        "chapter_title": arch.get("chapter_title", ""),
        "key_plot_points": arch.get("key_plot_points", []),
        "scene_details": arch.get("scene_details", []),
        "characters_present": prof.get("characters_present", []),
        "character_behaviors": prof.get("character_behaviors", []),
        "items_of_interest": prof.get("items_of_interest", []),
        "dialogue_summaries": prof.get("dialogue_summaries", []),
        "cross_chapter_connections": chron.get("cross_chapter_connections", []),
        "lore_discoveries": chron.get("lore_discoveries", []),
        "tags": [],
        "total_events_count": len(arch.get("key_plot_points", [])),
        "total_scenes_count": len(arch.get("scene_details", [])),
        "total_dialogues_count": len(prof.get("dialogue_summaries", [])),
    }

    # Validate with Pydantic (raises ValueError on hallucinated scene refs)
    final_model = MicroFactsFinal(**merged)

    os.makedirs(micro_dir, exist_ok=True)
    out_path = os.path.join(micro_dir, f"{prefix}_{ep_num}_micro_facts.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_model.model_dump_json(indent=2, ensure_ascii=False))

    print(f"[OK] {ep_num}_micro_facts.json written")
    print(f"      Events: {final_model.total_events_count} | Scenes: {final_model.total_scenes_count} | Dialogues: {final_model.total_dialogues_count}")
    print(f"      Chars: {len(final_model.characters_present)} | Behaviors: {len(final_model.character_behaviors)}")
    print(f"      Items: {len(final_model.items_of_interest)} | Connections: {len(final_model.cross_chapter_connections)} | Lore: {len(final_model.lore_discoveries)}")
    
    return final_model


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python merge_to_micro_facts.py <prefix> <ep_num> [base_dir]")
        sys.exit(1)
    merge_to_micro_facts(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)