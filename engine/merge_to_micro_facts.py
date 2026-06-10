#!/usr/bin/env python3
"""
Pass 1.4: Merge & Validate (Pydantic V2)
=========================================
Reads 3 JSON files (architect, profiler, chronicler) representing 3 analysis passes
of a single chapter, merges them, validates them against Pydantic models, and writes 
the final micro_facts JSON.

Phase 1.1 improvement: Evidence tracing — extracts literal quotes from clean chapter
text for every claim (KeyPlotPoint, CharacterBehavior, CrossChapterConnection,
LoreDiscovery) and computes match confidence scores.
"""
import os
import sys
import json
import re
from difflib import SequenceMatcher

# Ensure engine/ is importable whether run via MCP or standalone
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_ENGINE_DIR)
for _d in (_REPO_ROOT, _ENGINE_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from lore_models import MicroFactsFinal
from engine.utils import load_json, write_json


def normalize_sa_json(merged: dict) -> dict:
    """Fix common subagent field name mistakes before Pydantic validation."""
    # 1. scene_details[].order (missing integer)
    scenes = merged.get("scene_details", [])
    if isinstance(scenes, list):
        for i, scene in enumerate(scenes):
            if isinstance(scene, dict):
                if "order" not in scene or scene["order"] is None:
                    scene["order"] = i + 1

    # 2 & 3. dialogue_summaries (missing key_quotes, dialogue_id)
    dialogues = merged.get("dialogue_summaries", [])
    if isinstance(dialogues, list):
        for i, diag in enumerate(dialogues):
            if isinstance(diag, dict):
                if "key_quotes" not in diag or diag["key_quotes"] is None:
                    diag["key_quotes"] = []
                if "dialogue_id" not in diag or not diag["dialogue_id"]:
                    speaker = diag.get("speaker", "Unknown")
                    listener = diag.get("listener", "Unknown")
                    diag["dialogue_id"] = f"DI-{(i+1):03d}"
                    if "participants" not in diag:
                        diag["participants"] = [speaker, listener]

    # 4 & 5 & 7. lore_discoveries (discovery -> description, revealed_by -> source, missing evidence_quote)
    lores = merged.get("lore_discoveries", [])
    if isinstance(lores, list):
        for i, lore in enumerate(lores):
            if isinstance(lore, dict):
                # discovery -> description
                if "discovery" in lore and ("description" not in lore or not lore["description"]):
                    lore["description"] = lore.pop("discovery")
                # revealed_by -> source
                if "revealed_by" in lore and ("source" not in lore or not lore["source"]):
                    lore["source"] = lore.pop("revealed_by")
                # default empty fields
                if "discovery_id" not in lore or not lore["discovery_id"]:
                    lore["discovery_id"] = f"LD-{(i+1):03d}"
                if "description" not in lore or not lore["description"]:
                    lore["description"] = "No description provided"
                if "source" not in lore or not lore["source"]:
                    lore["source"] = "Unknown"
                if "significance" not in lore or not lore["significance"]:
                    lore["significance"] = "Unknown"
                if "evidence_quote" not in lore or lore["evidence_quote"] is None:
                    lore["evidence_quote"] = ""

    # 6. cross_chapter_connections[].connection_id (missing, use connection)
    connections = merged.get("cross_chapter_connections", [])
    if isinstance(connections, list):
        for i, conn in enumerate(connections):
            if isinstance(conn, dict):
                if "connection" in conn and ("connection_id" not in conn or not conn["connection_id"]):
                    conn["connection_id"] = conn.pop("connection")
                if "connection_id" not in conn or not conn["connection_id"]:
                    conn["connection_id"] = f"CC-{(i+1):03d}"
                if "description" not in conn or not conn["description"]:
                    conn["description"] = "No connection description"
                if "connection_type" not in conn or not conn["connection_type"]:
                    conn["connection_type"] = "Unknown"
                if "evidence_quote" not in conn or conn["evidence_quote"] is None:
                    conn["evidence_quote"] = ""

    return merged


def self_correct_micro_facts(merged: dict) -> dict:
    scenes = merged.get("scene_details", [])
    valid_scene_ids = [s.get("scene_id") for s in scenes if isinstance(s, dict) and s.get("scene_id")]
    
    if not valid_scene_ids:
        valid_scene_ids = ["SC-001"]
        scenes.append({
            "scene_id": "SC-001",
            "order": 1,
            "location": "Unknown Location",
            "description": "Auto-generated scene to prevent crash",
            "characters_present_in_scene": merged.get("characters_present", [])
        })
        merged["scene_details"] = scenes
        print("  [SELF-CORRECTION] No scenes found in architect pass. Auto-generated default scene 'SC-001'.")

    def normalize_scene_id(sid):
        if not sid or not isinstance(sid, str):
            return valid_scene_ids[0]
        sid_clean = sid.strip().upper()
        if sid_clean in valid_scene_ids:
            return sid_clean
            
        digits = "".join(c for c in sid_clean if c.isdigit())
        if digits:
            num = int(digits)
            for vsid in valid_scene_ids:
                vsid_digits = "".join(c for c in vsid if c.isdigit())
                if vsid_digits and int(vsid_digits) == num:
                    print(f"  [SELF-CORRECTION] Healed scene ID typo: '{sid}' -> '{vsid}'")
                    return vsid
                    
        for s in scenes:
            if str(s.get("order")) == sid_clean:
                print(f"  [SELF-CORRECTION] Healed scene order reference: '{sid}' -> '{s.get('scene_id')}'")
                return s.get("scene_id")
                
        print(f"  [SELF-CORRECTION] Scene '{sid}' not found. Falling back to default scene '{valid_scene_ids[0]}'")
        return valid_scene_ids[0]

    lists_to_clean = [
        "key_plot_points", "character_behaviors", "items_of_interest",
        "character_states", "dialogue_summaries", "cross_chapter_connections",
        "lore_discoveries"
    ]
    for key in lists_to_clean:
        items = merged.get(key, [])
        if not isinstance(items, list):
            merged[key] = []
            continue
        for item in items:
            if isinstance(item, dict) and "in_scene_id" in item:
                orig = item["in_scene_id"]
                normalized = normalize_scene_id(orig)
                item["in_scene_id"] = normalized

    present_chars = merged.get("characters_present", [])
    if isinstance(present_chars, list):
        cleaned_present = [c.strip() for c in present_chars if isinstance(c, str) and c.strip()]
        merged["characters_present"] = cleaned_present
        
        def normalize_char_name(cname):
            if not cname or not isinstance(cname, str):
                return cname
            cname_clean = cname.strip()
            if cname_clean in cleaned_present:
                return cname_clean
            for pc in cleaned_present:
                if pc.lower() == cname_clean.lower():
                    return pc
            for pc in cleaned_present:
                if cname_clean.lower() in pc.lower() or pc.lower() in cname_clean.lower():
                    print(f"  [SELF-CORRECTION] Aligned character name: '{cname_clean}' -> '{pc}'")
                    return pc
            return cname_clean

        for key in ["character_behaviors", "character_states"]:
            for item in merged.get(key, []):
                if isinstance(item, dict) and "character" in item:
                    item["character"] = normalize_char_name(item["character"])
                    
    return merged


def extract_evidence(merged: dict, clean_chapter_path: str | None = None) -> dict:
    """Extract literal evidence quotes from clean chapter text for every claim.
    
    For each evidence-bearing item (KeyPlotPoint, CharacterBehavior, 
    CrossChapterConnection, LoreDiscovery), attempts to find the literal quote
    in the clean chapter text using the description as a search anchor.
    
    Returns the merged dict with evidence fields populated.
    """
    if not clean_chapter_path or not os.path.exists(clean_chapter_path):
        return merged
    
    with open(clean_chapter_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    full_text = "".join(lines)
    
    def find_best_match(description: str, text: str, context_window: int = 30) -> dict | None:
        """Find the best literal match for a description in text using sliding window."""
        if not description or len(description) < 10:
            return None
        
        # Tokenize description into keywords for anchor search
        keywords = [w for w in re.findall(r'\w+', description.lower()) if len(w) > 3]
        if not keywords:
            return None
        
        # Also extract stems (first 4 chars) for fuzzy matching
        stems = set()
        for kw in keywords:
            stems.add(kw[:4])
        
        best_score = 0.0
        best_start = None
        best_quote = None
        
        # Search each line for keyword or stem matches
        for i, line in enumerate(lines):
            line_lower = line.lower()
            # Match if any keyword is a substring of the line, or any stem matches
            if any(kw in line_lower for kw in keywords) or \
               any(stem in line_lower for stem in stems):
                # Found a candidate — extract a window and compute similarity
                window_start = max(0, i - context_window // 2)
                window_end = min(len(lines), i + context_window // 2 + 1)
                window_text = "".join(lines[window_start:window_end])
                
                # Use SequenceMatcher for fuzzy match
                score = SequenceMatcher(None, description.lower(), window_text.lower()).ratio()
                if score > best_score:
                    best_score = score
                    best_start = window_start + 1  # 1-based
                    best_quote = window_text.strip()
        
        if best_score >= 0.10 and best_quote:
            return {
                "evidence_start_line": best_start,
                "evidence_end_line": best_start + len(best_quote.split('\n')) - 1,
                "evidence_quote": best_quote[:500],
                "match_confidence": round(best_score, 3)
            }
        return None
    
    # Annotate key_plot_points
    for kpp in merged.get("key_plot_points", []):
        if isinstance(kpp, dict):
            evidence = find_best_match(kpp.get("description", ""), full_text)
            if evidence:
                kpp.update(evidence)
    
    # Annotate character_behaviors
    for beh in merged.get("character_behaviors", []):
        if isinstance(beh, dict):
            evidence = find_best_match(beh.get("behavior", ""), full_text)
            if evidence:
                beh.update(evidence)
    
    # Annotate cross_chapter_connections
    for conn in merged.get("cross_chapter_connections", []):
        if isinstance(conn, dict):
            evidence = find_best_match(conn.get("description", ""), full_text)
            if evidence:
                conn.update(evidence)
    
    # Annotate lore_discoveries — verify existing evidence_quote against source
    for disc in merged.get("lore_discoveries", []):
        if isinstance(disc, dict):
            existing_quote = disc.get("evidence_quote", "")
            if existing_quote:
                # Try to locate the existing quote in source text
                escaped = re.escape(existing_quote[:100])
                match = re.search(escaped, full_text, re.IGNORECASE)
                if match:
                    # Count lines up to match position
                    text_before = full_text[:match.start()]
                    line_num = text_before.count('\n') + 1
                    quote_lines = existing_quote.count('\n') + 1
                    disc["evidence_start_line"] = line_num
                    disc["evidence_end_line"] = line_num + quote_lines - 1
                    disc["match_confidence"] = 0.95  # High confidence for direct match
                    disc["verification_status"] = "VERIFIED"
                else:
                    disc["verification_status"] = "NEEDS_REVIEW"
                    disc["match_confidence"] = 0.0
    
    return merged


def merge_to_micro_facts(prefix: str, ep_num: str, base_dir: str | None = None, 
                         clean_chapter_path: str | None = None):
    if base_dir is None:
        base_dir = os.getcwd()

    sa_raw = os.path.join(base_dir, "analysis", "sa_raw")
    micro_dir = os.path.join(base_dir, "micro_facts")

    paths = {
        "architect": os.path.join(sa_raw, f"{prefix}_{ep_num}_sa_architect.json"),
        "profiler": os.path.join(sa_raw, f"{prefix}_{ep_num}_sa_profiler.json"),
        "chronicler": os.path.join(sa_raw, f"{prefix}_{ep_num}_sa_chronicler.json"),
    }

    loaded = {}
    for role, path in paths.items():
        if not os.path.exists(path):
            # Raise instead of accumulating and calling sys.exit(1) later —
            # sys.exit() inside an MCP tool propagates SystemExit, which the
            # MCP tool wrapper does not catch, causing the call to hang
            # until the MCP timeout. Raising here gives a fast, clear error.
            raise FileNotFoundError(
                f"Missing 3-Pass input for {ep_num}: '{role}' not found at "
                f"{path}. Run the 3-Pass LLM extraction (architect / profiler "
                f"/ chronicler) before Phase 4 (merge)."
            )
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded[role] = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {role}: {e}") from e

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
        "character_states": prof.get("character_states", []),
        "dialogue_summaries": prof.get("dialogue_summaries", []),
        "cross_chapter_connections": chron.get("cross_chapter_connections", []),
        "lore_discoveries": chron.get("lore_discoveries", []),
        "tags": [],
        "total_events_count": len(arch.get("key_plot_points", [])),
        "total_scenes_count": len(arch.get("scene_details", [])),
        "total_dialogues_count": len(prof.get("dialogue_summaries", [])),
    }

    # Run Schema Normalization (Step 0)
    merged = normalize_sa_json(merged)

    # Run Self-Correction & Healing Agent
    merged = self_correct_micro_facts(merged)

    # Attempt to derive clean_chapter_path from project structure
    if clean_chapter_path is None:
        candidate1 = os.path.join(base_dir, "clean", f"{prefix}_{ep_num}.txt")
        candidate2 = os.path.join(base_dir, "clean", f"{prefix}_EP{ep_num}.txt" if not ep_num.startswith("EP") else f"{prefix}_{ep_num}.txt")
        if os.path.exists(candidate1):
            clean_chapter_path = candidate1
        elif os.path.exists(candidate2):
            clean_chapter_path = candidate2
    
    # Phase 1.1: Extract evidence quotes from clean chapter text
    if clean_chapter_path:
        merged = extract_evidence(merged, clean_chapter_path)

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