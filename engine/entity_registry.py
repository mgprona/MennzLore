#!/usr/bin/env python3
"""
MennzLore Structured Entity Registry
=====================================
Phase 2.1: Builds a typed, normalized entity registry from micro_facts + global_lore.

Entity Types:
  CHARACTER    — Named individuals with agency
  LOCATION     — Places, buildings, geographic features
  ORGANIZATION — Groups, factions, families, institutions
  ITEM         — Objects, artifacts, weapons, documents
  EVENT        — Significant occurrences (wars, ceremonies, discoveries)
  CONCEPT      — Abstract ideas, philosophies, forces

Relation Types (directed):
  resides_in      — Character lives/stays at Location
  belongs_to      — Character is member of Organization
  owns            — Character possesses Item
  allied_with     — Mutual cooperation
  opposes         — Conflict or rivalry
  influences      — One entity affects another
  mentions        — Entity references another
  located_at      — Item/Event at Location
  part_of         — Entity is sub-component of another

Output:
  output/entities/<prefix>_entity_registry.json  — Full typed registry
  output/entities/<prefix>_relation_graph.json   — Typed relations with evidence
"""
import os
import sys
import json
import glob
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple

# ── Constants ────────────────────────────────────────────────────────────────

ENTITY_TYPES = ["CHARACTER", "LOCATION", "ORGANIZATION", "ITEM", "EVENT", "CONCEPT"]

RELATION_TYPES = [
    "resides_in", "belongs_to", "owns", "allied_with", "opposes",
    "influences", "mentions", "located_at", "part_of"
]

# Keywords for type classification
TYPE_KEYWORDS = {
    "LOCATION": {
        "city", "town", "village", "island", "mountain", "river", "forest",
        "castle", "palace", "house", "room", "street", "road", "kingdom",
        "empire", "land", "country", "world", "sea", "ocean", "lake",
        "desert", "valley", "cave", "tower", "garden", "bridge", "port",
        "harbor", "inn", "tavern", "temple", "church", "cathedral", "shrine",
        "station", "platform", "dungeon", "prison", "fortress", "citadel",
    },
    "ORGANIZATION": {
        "company", "corporation", "guild", "army", "navy", "police",
        "government", "council", "order", "society", "clan", "tribe",
        "family", "agency", "bureau", "department", "regiment", "legion",
        "fleet", "syndicate", "cartel", "cult", "church", "academy",
        "institute", "league", "federation", "alliance",
    },
    "ITEM": {
        "sword", "ring", "book", "amulet", "crown", "stone", "gem",
        "weapon", "armor", "potion", "scroll", "map", "key", "staff",
        "wand", "orb", "blade", "shield", "bow", "arrow", "dagger",
        "spear", "axe", "helm", "cloak", "boots", "necklace", "bracelet",
        "coin", "treasure", "chest", "letter", "diary", "journal",
        "painting", "statue", "relic", "artifact", "machine", "device",
    },
    "EVENT": {
        "war", "battle", "ceremony", "wedding", "funeral", "festival",
        "meeting", "conference", "revolution", "coronation", "feast",
        "trial", "execution", "duel", "tournament", "expedition", "voyage",
        "plague", "disaster", "storm", "fire", "flood", "earthquake",
        "celebration", "ritual", "sacrifice", "banquet", "ball",
    },
    "CONCEPT": {
        "magic", "power", "prophecy", "curse", "legend", "myth", "religion",
        "faith", "science", "technology", "law", "rule", "philosophy",
        "destiny", "fate", "honor", "justice", "freedom", "truth", "lie",
        "secret", "knowledge", "wisdom", "madness", "dream", "nightmare",
    },
}


# ── Classification ───────────────────────────────────────────────────────────

def classify_entity(name: str, global_lore: dict = None) -> str:
    """Classify an entity string into one of the 6 types."""
    name_lower = name.lower().strip()
    
    # Check global_lore first (authoritative)
    if global_lore:
        chars = global_lore.get("characters", [])
        if isinstance(chars, list):
            for c in chars:
                cname = (c.get("name", "") if isinstance(c, dict) else str(c)).lower()
                if cname == name_lower:
                    return "CHARACTER"
        locs = global_lore.get("locations", [])
        if isinstance(locs, list):
            for loc in locs:
                lname = (loc.get("name", "") if isinstance(loc, dict) else str(loc)).lower()
                if lname == name_lower:
                    return "LOCATION"
    
    # Tokenize
    tokens = set(name_lower.split())
    tokens.update(name_lower.replace("-", " ").replace("_", " ").replace("'s", "").split())
    
    # Priority: LOCATION > ORGANIZATION > EVENT > ITEM > CONCEPT > CHARACTER (default)
    for token in tokens:
        if token in TYPE_KEYWORDS["LOCATION"]:
            return "LOCATION"
    for token in tokens:
        if token in TYPE_KEYWORDS["ORGANIZATION"]:
            return "ORGANIZATION"
    for token in tokens:
        if token in TYPE_KEYWORDS["EVENT"]:
            return "EVENT"
    for token in tokens:
        if token in TYPE_KEYWORDS["ITEM"]:
            return "ITEM"
    for token in tokens:
        if token in TYPE_KEYWORDS["CONCEPT"]:
            return "CONCEPT"
    
    # Default: proper names are CHARACTERS
    if name[0].isupper() and len(name.split()) <= 4:
        return "CHARACTER"
    return "CONCEPT"


def classify_relation(connection_type: str, description: str = "") -> str:
    """Normalize a free-text connection type into a standard relation type."""
    ct = connection_type.lower().strip()
    desc = (description or "").lower()
    
    # Direct mappings
    if any(w in ct for w in ("reside", "live", "dwell", "stay", "home", "house")):
        return "resides_in"
    if any(w in ct for w in ("belong", "member", "join", "serve")):
        return "belongs_to"
    if any(w in ct for w in ("own", "possess", "hold", "carry", "wield")):
        return "owns"
    if any(w in ct for w in ("ally", "friend", "partner", "love", "marriage", "family")):
        return "allied_with"
    if any(w in ct for w in ("oppos", "enemy", "rival", "conflict", "fight", "battle", "hate", "war")):
        return "opposes"
    if any(w in ct for w in ("influence", "control", "manipulate", "command", "lead", "rule")):
        return "influences"
    if any(w in ct for w in ("mention", "reference", "quote", "speak", "talk", "refer")):
        return "mentions"
    if any(w in ct for w in ("locate", "place", "sit", "stand", "found at", "inside")):
        return "located_at"
    if any(w in ct for w in ("part of", "component", "sub", "division", "branch")):
        return "part_of"
    
    # Description-based fallback
    if any(w in desc for w in ("fight", "kill", "attack", "battle", "war")):
        return "opposes"
    if any(w in desc for w in ("friend", "ally", "love", "marry")):
        return "allied_with"
    if any(w in desc for w in ("give", "gift", "receive", "take", "steal")):
        return "owns"
    
    return "mentions"  # Default


# ── Main Builder ─────────────────────────────────────────────────────────────

def build_entity_registry(project_dir: str, prefix: str = "",
                          output_dir: str | None = None) -> dict:
    """Build a typed, normalized entity registry from micro_facts + global_lore.
    
    Args:
        project_dir: Path to project directory
        prefix: Project prefix (auto-detected if empty)
        output_dir: Output directory (default: project_dir/output/entities/)
    
    Returns:
        dict with stats and output paths
    """
    if not prefix:
        prefix = os.path.basename(project_dir.rstrip("/\\"))
    
    if output_dir is None:
        output_dir = os.path.join(project_dir, "output", "entities")
    
    # ── Load global_lore ──
    verification_dir = os.path.join(project_dir, "verification")
    gl_path = os.path.join(verification_dir, f"{prefix}_global_lore.json")
    global_lore = {}
    try:
        with open(gl_path, "r", encoding="utf-8") as f:
            global_lore = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    # ── Load all micro_facts ──
    mf_dir = os.path.join(project_dir, "micro_facts")
    if not os.path.isdir(mf_dir):
        mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
    
    if not os.path.isdir(mf_dir):
        raise FileNotFoundError("No micro_facts directory found. Run Phase 4 first.")
    
    pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
    mf_files = sorted(glob.glob(pattern))
    
    if not mf_files:
        raise FileNotFoundError(f"No micro_facts files matching {pattern}")
    
    # ── Collect entities ──
    entity_data = defaultdict(lambda: {
        "type": None,
        "chapters": set(),
        "aliases": set(),
        "connections": [],
        "items_owned": [],
        "behaviors": [],
        "states": [],
        "mentions": [],
        "evidence_count": 0,
        "importance": 0,
    })
    
    all_relations = []
    entity_name_map = {}  # lowercase → canonical name
    
    for fpath in mf_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        ch_id = data.get("chapter_id", "?")
        
        # Characters present
        for char in data.get("characters_present", []):
            if not char or not isinstance(char, str):
                continue
            canonical = entity_name_map.get(char.lower(), char)
            entity_name_map[char.lower()] = canonical
            entity_data[canonical]["chapters"].add(ch_id)
            entity_data[canonical]["importance"] += 2  # Presence = high signal
        
        # Scene locations
        for scene in data.get("scene_details", []):
            loc = scene.get("location", "")
            if loc and isinstance(loc, str) and loc.lower() not in ("unknown location", "unknown", ""):
                canonical = entity_name_map.get(loc.lower(), loc)
                entity_name_map[loc.lower()] = canonical
                entity_data[canonical]["chapters"].add(ch_id)
                entity_data[canonical]["importance"] += 1
        
        # Cross-chapter connections → relations
        for conn in data.get("cross_chapter_connections", []):
            from_e = conn.get("from_entity", "")
            to_e = conn.get("to_entity", "")
            if not from_e or not to_e:
                continue
            
            # Normalize names
            f_canon = entity_name_map.get(from_e.lower(), from_e)
            t_canon = entity_name_map.get(to_e.lower(), to_e)
            entity_name_map[from_e.lower()] = f_canon
            entity_name_map[to_e.lower()] = t_canon
            
            rel_type = classify_relation(
                conn.get("connection_type", ""),
                conn.get("description", "")
            )
            
            # Store on both entities
            entity_data[f_canon]["connections"].append({
                "target": t_canon,
                "relation": rel_type,
                "description": conn.get("description", ""),
                "chapter": ch_id,
            })
            entity_data[t_canon]["connections"].append({
                "target": f_canon,
                "relation": rel_type,
                "description": conn.get("description", ""),
                "chapter": ch_id,
            })
            
            entity_data[f_canon]["importance"] += 1
            entity_data[t_canon]["importance"] += 1
            
            all_relations.append({
                "source": f_canon,
                "target": t_canon,
                "relation": rel_type,
                "description": conn.get("description", ""),
                "chapter": ch_id,
                "evidence_quote": conn.get("evidence_quote", ""),
            })
        
        # Items → ownership relations
        for item in data.get("items_of_interest", []):
            owner = item.get("owner", "")
            item_name = item.get("item", "")
            if owner and item_name:
                o_canon = entity_name_map.get(owner.lower(), owner)
                i_canon = entity_name_map.get(item_name.lower(), item_name)
                entity_name_map[owner.lower()] = o_canon
                entity_name_map[item_name.lower()] = i_canon
                
                entity_data[o_canon]["items_owned"].append({
                    "item": i_canon,
                    "description": item.get("description", ""),
                    "chapter": ch_id,
                })
                entity_data[i_canon]["importance"] += 1
                
                all_relations.append({
                    "source": o_canon,
                    "target": i_canon,
                    "relation": "owns",
                    "description": f"Possesses {i_canon}",
                    "chapter": ch_id,
                })
        
        # Behaviors
        for beh in data.get("character_behaviors", []):
            char = beh.get("character", "")
            if char:
                c_canon = entity_name_map.get(char.lower(), char)
                entity_name_map[char.lower()] = c_canon
                entity_data[c_canon]["behaviors"].append({
                    "behavior": beh.get("behavior", ""),
                    "type": beh.get("behavior_type", ""),
                    "chapter": ch_id,
                })
                entity_data[c_canon]["importance"] += 1
        
        # States
        for st in data.get("character_states", []):
            char = st.get("character", "")
            if char:
                c_canon = entity_name_map.get(char.lower(), char)
                entity_data[c_canon]["states"].append({
                    "state": st.get("state", ""),
                    "description": st.get("description", ""),
                    "chapter": ch_id,
                })
        
        # Evidence count
        for section in ["key_plot_points", "lore_discoveries"]:
            for item in data.get(section, []):
                if item.get("evidence_quote"):
                    # Attribute to entities mentioned in description
                    desc = item.get("description", "").lower()
                    for ename in list(entity_name_map.keys()):
                        if ename in desc:
                            canonical = entity_name_map[ename]
                            entity_data[canonical]["evidence_count"] += 1
    
    # ── Classify types ──
    for ename, edata in entity_data.items():
        if edata["type"] is None:
            edata["type"] = classify_entity(ename, global_lore)
    
    # ── Build registry ──
    os.makedirs(output_dir, exist_ok=True)
    
    registry = []
    for ename, edata in sorted(entity_data.items(), 
                                key=lambda x: -x[1]["importance"]):
        registry.append({
            "name": ename,
            "type": edata["type"],
            "chapters": sorted(edata["chapters"]),
            "chapter_count": len(edata["chapters"]),
            "connections": edata["connections"][:20],  # Top 20
            "connection_count": len(edata["connections"]),
            "items_owned": edata["items_owned"],
            "behaviors": edata["behaviors"][:10],
            "behavior_count": len(edata["behaviors"]),
            "states": edata["states"][:10],
            "evidence_count": edata["evidence_count"],
            "importance_score": edata["importance"],
        })
    
    # ── Type distribution ──
    type_dist = Counter(e["type"] for e in registry)
    relation_dist = Counter(r["relation"] for r in all_relations)
    
    # ── Top relations ──
    top_relations = sorted(all_relations, 
                          key=lambda r: len(r.get("description", "")), 
                          reverse=True)[:50]
    
    # ── Write outputs ──
    registry_path = os.path.join(output_dir, f"{prefix}_entity_registry.json")
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump({
            "project_prefix": prefix,
            "total_entities": len(registry),
            "type_distribution": dict(type_dist),
            "relation_distribution": dict(relation_dist),
            "entities": registry,
        }, f, indent=2, ensure_ascii=False)
    
    relations_path = os.path.join(output_dir, f"{prefix}_relation_graph.json")
    with open(relations_path, "w", encoding="utf-8") as f:
        json.dump({
            "project_prefix": prefix,
            "total_relations": len(all_relations),
            "relation_types": dict(relation_dist),
            "relations": top_relations,
        }, f, indent=2, ensure_ascii=False)
    
    return {
        "status": "success",
        "total_entities": len(registry),
        "total_relations": len(all_relations),
        "type_distribution": dict(type_dist),
        "relation_distribution": dict(relation_dist),
        "registry_path": registry_path,
        "relations_path": relations_path,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python entity_registry.py <project_dir> [prefix]")
        sys.exit(1)
    
    proj = sys.argv[1]
    pfx = sys.argv[2] if len(sys.argv) > 2 else ""
    
    result = build_entity_registry(proj, pfx)
    if result["status"] == "success":
        print(f"[OK] Entity registry built: {result['total_entities']} entities, "
              f"{result['total_relations']} relations")
        print(f"     Types: {result['type_distribution']}")
        print(f"     Registry: {result['registry_path']}")
    else:
        print(f"[ERROR] {result.get('message', 'Unknown error')}")
