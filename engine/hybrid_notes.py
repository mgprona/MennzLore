#!/usr/bin/env python3
"""
MennzLore Hybrid Entity Notes
==============================
Phase 1.3 improvement: Generates structured per-entity notes inspired by
LoreGraph's Hybrid Note format.

For each entity (CHARACTER, LOCATION, ORGANIZATION, etc.) builds a note with:
  [CONTEXT]   — Role in story, chapter appearances, narrative significance
  [FACTS]     — Deterministic facts from micro_facts (connections, items owned)
  [INFERENCES] — LLM-inferred patterns (tagged clearly as inference)
  [BEHAVIOR]  — Behavioral patterns across all chapters
  [GAPS]      — What we don't know yet (missing information)
  [EVIDENCE]  — Literal quotes with line numbers from source text

Output: Markdown per entity + JSON registry + index file.
"""
import os
import sys
import json
import re
import glob
from collections import defaultdict, Counter
from typing import Dict, List, Optional


# ── Helpers ──────────────────────────────────────────────────────────────────

# ── Junk entity name filter (Fix: prevents cross-chapter connection
#     descriptions and other noise from being treated as valid entities) ──

KNOWN_JUNK_ENTITY_NAMES = {
    "blank", "unknown", "none", "n/a", "na", "unnamed", "mystery",
    "chapter_context", "connects_to", "connections", "all", "everyone",
    "various", "everybody", "somebody", "someone",
}

# Connection descriptions that look like "Chapter IV sets up the mystery"
# should never become entity names.  Covers the most common patterns.
CONNECTION_DESC_WORDS = {
    "sets_up", "continues", "follows", "establishes", "references",
    "introduces", "concludes", "resolves", "transitions", "builds",
    "develops", "reveals", "foreshadows", "parallels", "contrasts",
}


def _is_valid_entity_name(name: str | None) -> bool:
    """Return True if *name* is a plausible entity name, not junk.

    Filters out:
      - Known junk / placeholder names (Blank, Unknown, …)
      - Cross-chapter connection descriptions mistaken for entities
      - Overly short or purely numeric names
      - Names starting with a lowercase letter (likely a description)
    """
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    if not name:
        return False
    if len(name) < 3:
        return False

    # Check known junk names (case-insensitive)
    slug = name.lower().replace(" ", "_").replace("'", "").replace("-", "_")
    for junk in KNOWN_JUNK_ENTITY_NAMES:
        if slug == junk:
            return False

    # Check connection-description-style names like "chapter_iv_sets_up_..."
    if slug.startswith("chapter_"):
        return False
    # Words like "sets_up_the_mystery" → description, not entity
    first_word = slug.split("_")[0] if "_" in slug else slug.split()[0] if " " in slug else slug
    if first_word in CONNECTION_DESC_WORDS:
        return False

    # Pure numbers (e.g. "12345") are never entity names
    if name.isdigit():
        return False

    # Must start with uppercase letter or be proper-noun-like
    # (this catches descriptions like "a shadowy figure" sneaking in)
    if name[0].islower():
        return False

    return True


_ENTITY_VALIDATION_APPLIED = True  # marker for smoke-test detection


def _load_json_safe(path: str) -> dict:
    """Load a JSON file, return empty dict on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _entity_type(entity_name: str, global_lore: dict) -> str:
    """Determine entity type from global_lore or heuristics."""
    # Check global_lore characters list
    chars = global_lore.get("characters", [])
    if isinstance(chars, list):
        for c in chars:
            if isinstance(c, dict) and c.get("name", "").lower() == entity_name.lower():
                return "CHARACTER"
    
    # Check locations
    locations = global_lore.get("locations", [])
    if isinstance(locations, list):
        for loc in locations:
            if isinstance(loc, dict) and loc.get("name", "").lower() == entity_name.lower():
                return "LOCATION"
    
    # Fallback classification
    name_lower = entity_name.lower()
    location_kw = {'city', 'town', 'island', 'mountain', 'river', 'forest', 
                   'castle', 'palace', 'kingdom', 'empire', 'village', 'sea', 'lake'}
    org_kw = {'company', 'guild', 'army', 'council', 'order', 'society', 'clan', 'tribe'}
    item_kw = {'sword', 'ring', 'book', 'amulet', 'crown', 'stone', 'gem', 'weapon', 'scroll'}
    
    for word in name_lower.split():
        if word in location_kw:
            return "LOCATION"
        if word in org_kw:
            return "ORGANIZATION"
        if word in item_kw:
            return "ITEM"
    
    return "CHARACTER"  # Default


# ── Note Builder ─────────────────────────────────────────────────────────────

def build_hybrid_note(entity_name: str, entity_type: str, 
                      chapter_data: List[dict],
                      global_lore_excerpt: dict = None) -> dict:
    """Build a structured hybrid note for one entity from all chapter data.
    
    Args:
        entity_name: Canonical entity name
        entity_type: CHARACTER, LOCATION, ORGANIZATION, etc.
        chapter_data: List of per-chapter micro_facts dicts
        global_lore_excerpt: Optional global_lore excerpt for this entity
    
    Returns:
        dict with sections: context, facts, inferences, behavior, gaps, evidence
    """
    chapters_present = []
    connections_out = []
    connections_in = []
    behaviors = []
    items_owned = []
    states = []
    evidence_quotes = []
    lore_mentions = []
    
    for ch in chapter_data:
        ch_id = ch.get("chapter_id", "?")
        
        # Is this entity present?
        chars_present = [c.lower() for c in ch.get("characters_present", [])]
        if entity_name.lower() in chars_present:
            chapters_present.append(ch_id)
        
        # Cross-chapter connections involving this entity
        for conn in ch.get("cross_chapter_connections", []):
            from_e = conn.get("from_entity", "")
            to_e = conn.get("to_entity", "")
            if from_e.lower() == entity_name.lower():
                connections_out.append({
                    "target": to_e,
                    "type": conn.get("connection_type", "?"),
                    "description": conn.get("description", ""),
                    "chapter": ch_id,
                    "evidence": conn.get("evidence_quote", ""),
                })
            if to_e.lower() == entity_name.lower():
                connections_in.append({
                    "source": from_e,
                    "type": conn.get("connection_type", "?"),
                    "description": conn.get("description", ""),
                    "chapter": ch_id,
                    "evidence": conn.get("evidence_quote", ""),
                })
        
        # Behaviors
        for beh in ch.get("character_behaviors", []):
            if beh.get("character", "").lower() == entity_name.lower():
                behaviors.append({
                    "behavior": beh.get("behavior", ""),
                    "type": beh.get("behavior_type", ""),
                    "chapter": ch_id,
                    "scene": beh.get("in_scene_id", "?"),
                    "evidence": beh.get("evidence_quote", ""),
                })
        
        # Items owned
        for item in ch.get("items_of_interest", []):
            owner = item.get("owner", "")
            if owner and owner.lower() == entity_name.lower():
                items_owned.append({
                    "item": item.get("item", ""),
                    "description": item.get("description", ""),
                    "chapter": ch_id,
                })
        
        # Character states
        for cs in ch.get("character_states", []):
            if cs.get("character", "").lower() == entity_name.lower():
                states.append({
                    "state": cs.get("state", ""),
                    "description": cs.get("description", ""),
                    "chapter": ch_id,
                })
        
        # Lore discoveries mentioning this entity
        for disc in ch.get("lore_discoveries", []):
            desc = disc.get("description", "")
            if entity_name.lower() in desc.lower():
                lore_mentions.append({
                    "description": desc,
                    "chapter": ch_id,
                    "evidence_quote": disc.get("evidence_quote", ""),
                    "evidence_lines": f"{disc.get('evidence_start_line', '?')}-{disc.get('evidence_end_line', '?')}",
                    "verification": disc.get("verification_status", "UNVERIFIED"),
                })
        
        # Evidence quotes with line numbers
        for section in ["key_plot_points", "lore_discoveries", "character_behaviors"]:
            for item in ch.get(section, []):
                quote = item.get("evidence_quote", "")
                # Check if entity name (or any token of it) appears in item text
                text_to_check = (
                    item.get("description", "") + 
                    item.get("behavior", "") + 
                    item.get("character", "")
                ).lower()
                name_tokens = entity_name.lower().split()
                if quote and (
                    entity_name.lower() in text_to_check or
                    any(token in text_to_check for token in name_tokens if len(token) > 3)
                ):
                    if quote not in [e["quote"] for e in evidence_quotes]:
                        evidence_quotes.append({
                            "quote": quote[:300],
                            "start_line": item.get("evidence_start_line"),
                            "end_line": item.get("evidence_end_line"),
                            "confidence": item.get("match_confidence"),
                            "chapter": ch_id,
                        })
    
    # ── Compose note ──
    
    # CONTEXT
    context_lines = []
    if global_lore_excerpt:
        if "role" in global_lore_excerpt:
            context_lines.append(f"**Role:** {global_lore_excerpt.get('role', 'Unknown')}")
        if "description" in global_lore_excerpt:
            context_lines.append(global_lore_excerpt["description"])
    context_lines.append(f"**Entity Type:** {entity_type}")
    context_lines.append(f"**Appears in {len(chapters_present)} chapters:** {', '.join(chapters_present[:10])}")
    if len(chapters_present) > 10:
        context_lines.append(f"  …and {len(chapters_present) - 10} more")
    context_lines.append(f"**Total connections:** {len(connections_out) + len(connections_in)} "
                        f"({len(connections_out)} outgoing, {len(connections_in)} incoming)")
    if behaviors:
        context_lines.append(f"**Behaviors recorded:** {len(behaviors)}")
    if items_owned:
        context_lines.append(f"**Items owned:** {len(items_owned)}")
    
    # FACTS
    facts = []
    # Connections as facts
    for conn in connections_out[:10]:
        facts.append(f"- Connected to **{conn['target']}** ({conn['type']}): {conn['description'][:120]}")
    for conn in connections_in[:5]:
        if len(facts) < 15:
            facts.append(f"- Referenced by **{conn['source']}** ({conn['type']}): {conn['description'][:120]}")
    # Items owned
    for item in items_owned[:5]:
        facts.append(f"- Owns/possesses **{item['item']}**: {item['description'][:100]}")
    # States
    for st in states[:5]:
        facts.append(f"- State in {st['chapter']}: **{st['state']}** — {st['description'][:100]}")
    
    # BEHAVIOR
    behavior_lines = []
    for b in behaviors[:10]:
        behavior_lines.append(f"- [{b['type']}] {b['behavior'][:150]}")
        if b.get("evidence"):
            behavior_lines.append(f"  > *\"{b['evidence'][:120]}\"*")
    
    # GAPS
    gaps = []
    if not chapters_present:
        gaps.append("- No chapter appearances recorded — entity may be mentioned but not present")
    if not connections_out and not connections_in:
        gaps.append("- No direct connections to other entities in micro_facts")
    if not behaviors:
        gaps.append("- No specific behaviors recorded")
    if not evidence_quotes:
        gaps.append("- No evidence quotes anchored to source text")
    # Check if entity appears in global_lore but not in micro_facts
    if global_lore_excerpt and not chapters_present:
        gaps.append("- Entity defined in global_lore but never appears in chapter text — possible hallucination")
    
    # EVIDENCE
    evidence_lines = []
    for ev in evidence_quotes[:8]:
        status_icon = "✅" if (ev.get("confidence") or 0) >= 0.7 else "⚠️"
        evidence_lines.append(f"- {status_icon} [{ev['chapter']}, L{ev.get('start_line', '?')}-{ev.get('end_line', '?')}] "
                            f"(confidence: {ev.get('confidence', 'N/A')})")
        evidence_lines.append(f"  > *\"{ev['quote'][:200]}\"*")
    
    # Lore mentions
    for lm in lore_mentions[:5]:
        evidence_lines.append(f"- 📖 Lore mention [{lm['chapter']}, {lm['evidence_lines']}] "
                            f"({lm['verification']})")
        evidence_lines.append(f"  > *\"{lm['evidence_quote'][:200]}\"*")
    
    note = {
        "entity_name": entity_name,
        "entity_type": entity_type,
        "sections": {
            "CONTEXT": "\n".join(context_lines),
            "FACTS": "\n".join(facts) if facts else "_No deterministic facts extracted._",
            "BEHAVIOR": "\n".join(behavior_lines) if behavior_lines else "_No behaviors recorded._",
            "GAPS": "\n".join(gaps) if gaps else "_No significant gaps identified._",
            "EVIDENCE": "\n".join(evidence_lines) if evidence_lines else "_No evidence quotes anchored._",
        },
        "stats": {
            "chapters_present": len(chapters_present),
            "connections_out": len(connections_out),
            "connections_in": len(connections_in),
            "behaviors": len(behaviors),
            "items_owned": len(items_owned),
            "evidence_quotes": len(evidence_quotes),
            "lore_mentions": len(lore_mentions),
        },
        # Raw data for downstream processing
        "_raw": {
            "chapters": chapters_present,
            "connections": connections_out + connections_in,
            "behaviors": behaviors,
            "items_owned": items_owned,
            "evidence_quotes": evidence_quotes,
        }
    }
    
    return note


def _render_markdown(note: dict) -> str:
    """Render a hybrid note as a readable Markdown string."""
    s = note["sections"]
    lines = [
        f"# {note['entity_name']}",
        f"*{note['entity_type']}*",
        "",
        "## 📍 Context",
        s["CONTEXT"],
        "",
        "## 📋 Facts",
        s["FACTS"],
        "",
        "## 🎭 Behavior",
        s["BEHAVIOR"],
        "",
        "## ❓ Gaps & Unknowns",
        s["GAPS"],
        "",
        "## 🔍 Evidence",
        s["EVIDENCE"],
        "",
        "---",
        f"*Generated by MennzLore Hybrid Notes — Phase 1.3*",
        f"*Chapters: {note['stats']['chapters_present']} | "
        f"Connections: {note['stats']['connections_out'] + note['stats']['connections_in']} | "
        f"Behaviors: {note['stats']['behaviors']} | "
        f"Evidence: {note['stats']['evidence_quotes']}*",
    ]
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────────────

def generate_hybrid_notes(project_dir: str, prefix: str = "",
                          output_dir: str | None = None) -> dict:
    """Generate hybrid entity notes for all entities in a project.
    
    Args:
        project_dir: Path to project directory
        prefix: Project prefix (auto-detected if empty)
        output_dir: Output directory (default: project_dir/output/entities/)
    
    Returns:
        dict with stats and paths
    """
    if not prefix:
        prefix = os.path.basename(project_dir.rstrip("/\\"))
    
    if output_dir is None:
        output_dir = os.path.join(project_dir, "output", "entities")
    
    # Load global_lore for entity definitions
    verification_dir = os.path.join(project_dir, "verification")
    global_lore_path = os.path.join(verification_dir, f"{prefix}_global_lore.json")
    global_lore = _load_json_safe(global_lore_path)
    
    # Load all micro_facts
    mf_dir = os.path.join(project_dir, "micro_facts")
    if not os.path.isdir(mf_dir):
        mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
    
    if not os.path.isdir(mf_dir):
        raise FileNotFoundError(
            f"No micro_facts directory found. Run Phase 4 before Phase 1.3."
        )
    
    pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
    mf_files = sorted(glob.glob(pattern))
    
    if not mf_files:
        raise FileNotFoundError(f"No micro_facts files found matching {pattern}")
    
    chapter_data = []
    all_entities = set()
    
    for fpath in mf_files:
        data = _load_json_safe(fpath)
        if data:
            chapter_data.append(data)
            for char in data.get("characters_present", []):
                if _is_valid_entity_name(char):
                    all_entities.add(char)
            for conn in data.get("cross_chapter_connections", []):
                for key in ("from_entity", "to_entity"):
                    e = conn.get(key, "")
                    if _is_valid_entity_name(e):
                        all_entities.add(e)
    
    # Build global_lore lookup
    gl_chars = {}
    chars_list = global_lore.get("characters", [])
    if isinstance(chars_list, list):
        for c in chars_list:
            if isinstance(c, dict):
                name = c.get("name", "")
                if name:
                    gl_chars[name.lower()] = c
    
    gl_locations = {}
    locs_list = global_lore.get("locations", [])
    if isinstance(locs_list, list):
        for loc in locs_list:
            if isinstance(loc, dict):
                name = loc.get("name", "")
                if name:
                    gl_locations[name.lower()] = loc
    
    # Filter: only entities with enough data
    MIN_APPEARANCES = 1
    qualified_entities = []
    for entity in sorted(all_entities):
        # Quick count of chapters where entity appears
        count = sum(1 for ch in chapter_data 
                   if entity.lower() in [c.lower() for c in ch.get("characters_present", [])])
        # Also count connections
        conn_count = sum(1 for ch in chapter_data 
                        for conn in ch.get("cross_chapter_connections", [])
                        if entity.lower() in (conn.get("from_entity", "").lower(), 
                                             conn.get("to_entity", "").lower()))
        if count >= MIN_APPEARANCES or conn_count >= 1:
            qualified_entities.append((entity, count + conn_count))
    
    # Sort by importance (most appearances first)
    qualified_entities.sort(key=lambda x: -x[1])
    
    # Build notes
    os.makedirs(output_dir, exist_ok=True)
    notes = []
    entity_registry = []
    
    for entity_name, importance in qualified_entities[:50]:  # Cap at 50 top entities
        etype = _entity_type(entity_name, global_lore)
        gl_excerpt = gl_chars.get(entity_name.lower()) or gl_locations.get(entity_name.lower())
        
        note = build_hybrid_note(entity_name, etype, chapter_data, gl_excerpt)
        notes.append(note)
        
        # Write per-entity Markdown
        md = _render_markdown(note)
        safe_name = entity_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        safe_name = re.sub(r'["*:<>?|]', '', safe_name).strip('.')
        md_path = os.path.join(output_dir, f"{safe_name}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        
        entity_registry.append({
            "name": entity_name,
            "type": etype,
            "importance_score": importance,
            "stats": note["stats"],
            "note_path": md_path,
        })
    
    # Write registry JSON
    registry_path = os.path.join(output_dir, f"{prefix}_entity_registry.json")
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(entity_registry, f, indent=2, ensure_ascii=False)
    
    # Write index Markdown
    index_lines = [
        f"# {prefix} — Entity Index",
        "",
        f"**Total entities:** {len(entity_registry)}",
        "",
        "| Entity | Type | Chapters | Connections | Behaviors | Evidence |",
        "|--------|------|----------|-------------|-----------|----------|",
    ]
    for e in entity_registry:
        s = e["stats"]
        index_lines.append(
            f"| [{e['name']}]({e['name'].replace(' ', '_')}.md) | {e['type']} | "
            f"{s['chapters_present']} | {s['connections_out'] + s['connections_in']} | "
            f"{s['behaviors']} | {s['evidence_quotes']} |"
        )
    
    index_path = os.path.join(output_dir, "INDEX.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))
    
    # Type distribution
    type_dist = Counter(e["type"] for e in entity_registry)
    
    return {
        "status": "success",
        "total_entities": len(entity_registry),
        "entity_types": dict(type_dist),
        "registry_path": registry_path,
        "index_path": index_path,
        "output_dir": output_dir,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hybrid_notes.py <project_dir> [prefix]")
        sys.exit(1)
    
    proj = sys.argv[1]
    pfx = sys.argv[2] if len(sys.argv) > 2 else ""
    
    result = generate_hybrid_notes(proj, pfx)
    if result["status"] == "success":
        print(f"[OK] Hybrid notes generated: {result['total_entities']} entities")
        print(f"     Types: {result['entity_types']}")
        print(f"     Registry: {result['registry_path']}")
        print(f"     Index: {result['index_path']}")
    else:
        print(f"[ERROR] {result.get('message', 'Unknown error')}")
