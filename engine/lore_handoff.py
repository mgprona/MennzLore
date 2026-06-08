import os
import re
import json
from datetime import datetime
from typing import Dict, Any, List
from engine.utils import load_json, write_json, build_variant_lookup, normalize_name, normalize_location

def export_lore_snapshot(volume_dir: str, prefix: str, vol_num: int) -> dict:
    """
    Collects facts from name maps, global lore, and micro_facts of a volume,
    and returns a structured lore snapshot dictionary.
    """
    verification_dir = os.path.join(volume_dir, "verification")
    micro_dir = os.path.join(volume_dir, "micro_facts")
    if not os.path.isdir(micro_dir):
        micro_dir = os.path.join(volume_dir, "analysis", "micro_facts")

    # Load name map and global lore
    name_map = load_json(os.path.join(verification_dir, f"{prefix}_name_map.json"))
    global_lore = load_json(os.path.join(verification_dir, f"{prefix}_global_lore.json"))
    variant_lookup = build_variant_lookup(name_map)

    # Scan all micro_facts files
    mf_files = []
    if os.path.isdir(micro_dir):
        for f in os.listdir(micro_dir):
            m = re.match(rf'{prefix}_EP(\d+)_micro_facts\.json', f)
            if m:
                mf_files.append((int(m.group(1)), f))
    
    mf_files.sort(key=lambda x: x[0])

    characters: Dict[str, Any] = {}
    locations: Dict[str, Any] = {}
    world_rules: List[str] = []
    open_threads: List[str] = []

    # Initialize characters from name map
    chars_in_map = name_map.get("characters", {})
    for canon, c_data in chars_in_map.items():
        if canon.startswith("_"):
            continue
        characters[canon] = {
            "status": "unknown",
            "first_appeared": None,
            "last_appeared": None,
            "key_facts": [],
            "relationships": {},
            "roles": []
        }
        if c_data.get("aliases"):
            characters[canon]["aliases"] = c_data["aliases"]

    # Scan episodes to populate lore details
    for ep, filename in mf_files:
        ep_label = f"vol{vol_num}_EP{ep:03d}"
        fpath = os.path.join(micro_dir, filename)
        ep_data = load_json(fpath)
        if not ep_data:
            continue

        # 1. Track character appearances, states, and behaviors
        present_chars = ep_data.get("characters_present", [])
        for char_name_raw in present_chars:
            if not isinstance(char_name_raw, str):
                continue
            canon = normalize_name(char_name_raw, variant_lookup)
            if canon not in characters:
                characters[canon] = {
                    "status": "unknown",
                    "first_appeared": ep_label,
                    "last_appeared": ep_label,
                    "key_facts": [],
                    "relationships": {},
                    "roles": []
                }
            else:
                if characters[canon]["first_appeared"] is None:
                    characters[canon]["first_appeared"] = ep_label
                characters[canon]["last_appeared"] = ep_label

        # Character States (status tracking)
        states = ep_data.get("character_states", [])
        for cs in states:
            if not isinstance(cs, dict):
                continue
            char = normalize_name(cs.get("character", ""), variant_lookup)
            state = cs.get("state", "").strip().lower()
            desc = cs.get("description", "")
            
            if char in characters:
                if state in ["deceased", "dead", "killed", "died"]:
                    characters[char]["status"] = "deceased"
                elif state in ["active", "alive"]:
                    characters[char]["status"] = "active"
                
                if desc and desc not in characters[char]["key_facts"]:
                    characters[char]["key_facts"].append(f"{ep_label}: {desc}")

        # Character Behaviors (facts mapping)
        behaviors = ep_data.get("character_behaviors", [])
        for cb in behaviors:
            if not isinstance(cb, dict):
                continue
            char = normalize_name(cb.get("character", ""), variant_lookup)
            beh = cb.get("behavior", "")
            b_type = cb.get("behavior_type", "")
            if char in characters and beh:
                fact = f"{ep_label} ({b_type}): {beh}"
                if fact not in characters[char]["key_facts"]:
                    characters[char]["key_facts"].append(fact)

        # Connections (relationships)
        connections = ep_data.get("cross_chapter_connections", [])
        for conn in connections:
            if not isinstance(conn, dict):
                continue
            from_ent = normalize_name(conn.get("from_entity", ""), variant_lookup)
            to_ent = normalize_name(conn.get("to_entity", ""), variant_lookup)
            c_type = conn.get("connection_type", "")
            desc = conn.get("description", "")

            if from_ent in characters and to_ent:
                # Add relationship details
                characters[from_ent]["relationships"][to_ent] = f"{c_type} ({desc})"

        # 2. Track locations
        scenes = ep_data.get("scene_details", [])
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            raw_loc = scene.get("location", "")
            if raw_loc:
                loc = normalize_location(raw_loc)
                mood = scene.get("mood", "")
                desc = scene.get("description", "")
                if loc not in locations:
                    locations[loc] = {
                        "first_seen": ep_label,
                        "atmospheres": [mood] if mood else [],
                        "key_events": [f"{ep_label}: {desc}"] if desc else []
                    }
                else:
                    if mood and mood not in locations[loc]["atmospheres"]:
                        locations[loc]["atmospheres"].append(mood)
                    if desc:
                        locations[loc]["key_events"].append(f"{ep_label}: {desc}")

        # 3. Track discoveries & world rules
        discoveries = ep_data.get("lore_discoveries", [])
        for disc in discoveries:
            if not isinstance(disc, dict):
                continue
            desc = disc.get("description", "")
            evidence = disc.get("evidence_quote", "")
            rule_entry = f"{desc} (Evidence: '{evidence}')"
            if rule_entry not in world_rules:
                world_rules.append(rule_entry)

    # Pull mysteries/clues from global_lore as open threads
    if global_lore and "mystery_and_clues_tracker" in global_lore:
        for clue in global_lore["mystery_and_clues_tracker"]:
            if not clue.get("is_resolved"):
                desc = clue.get("description", "")
                introduced = clue.get("introduced_in_chapter", "")
                clue_entry = f"{desc} (Planted in: Ch.{introduced})"
                if clue_entry not in open_threads:
                    open_threads.append(clue_entry)

    # Clean up empty key_facts lists to keep it compact
    for char in characters:
        # Cap key facts to top 15 entries to save tokens
        if len(characters[char]["key_facts"]) > 15:
            characters[char]["key_facts"] = characters[char]["key_facts"][:15]

    return {
        "accumulated_through": f"vol{vol_num}",
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "characters": characters,
        "locations": locations,
        "world_rules": world_rules,
        "open_threads": open_threads,
        "conflicts": []
    }

def build_lore_context_prompt(prior_lore: dict) -> str:
    """
    Formats the accumulated prior lore snapshot into a markdown block
    suitable for injecting as context in the extraction prompts.
    """
    if not prior_lore:
        return ""

    lines = [
        "=================================================================",
        "PRIOR LORE CONTEXT (From Previous Volumes - Maintain Consistency)",
        "=================================================================",
        ""
    ]

    # Characters Section
    lines.append("### KNOWN CHARACTERS:")
    chars = prior_lore.get("characters", {})
    if chars:
        for name, data in sorted(chars.items()):
            status_str = f" [Status: {data.get('status', 'unknown')}]"
            lines.append(f"* **{name}**{status_str}")
            if data.get("first_appeared"):
                lines.append(f"  - Appears: {data.get('first_appeared')} to {data.get('last_appeared', 'unknown')}")
            
            # Key Facts
            facts = data.get("key_facts", [])
            if facts:
                # Limit context size by picking a few key facts
                sample_facts = facts[-5:] # get last 5 key behaviors/facts
                lines.append("  - Key Facts/Behaviors:")
                for fact in sample_facts:
                    lines.append(f"    * {fact}")
            
            # Relationships
            rels = data.get("relationships", {})
            if rels:
                lines.append("  - Relationships:")
                for target, r_type in rels.items():
                    lines.append(f"    * with {target}: {r_type}")
    else:
        lines.append("*(No known characters)*")
    lines.append("")

    # Locations Section
    lines.append("### KNOWN LOCATIONS:")
    locs = prior_lore.get("locations", {})
    if locs:
        for name, data in sorted(locs.items()):
            atm = ", ".join(data.get("atmospheres", []))
            lines.append(f"* **{name}** (First seen: {data.get('first_seen', 'unknown')})")
            if atm:
                lines.append(f"  - Atmosphere: {atm}")
    else:
        lines.append("*(No known locations)*")
    lines.append("")

    # World Rules
    lines.append("### WORLD LAWS, MAGIC SYSTEMS, & RULES:")
    rules = prior_lore.get("world_rules", [])
    if rules:
        for idx, rule in enumerate(rules, 1):
            lines.append(f"{idx}. {rule}")
    else:
        lines.append("*(No custom world laws recorded)*")
    lines.append("")

    # Open Threads
    lines.append("### UNRESOLVED MYSTERIES & OPEN PLOT THREADS:")
    threads = prior_lore.get("open_threads", [])
    if threads:
        for thread in threads:
            lines.append(f"* {thread}")
    else:
        lines.append("*(No open mysteries recorded)*")
    
    lines.append("\n=================================================================\n")
    return "\n".join(lines)

def detect_conflicts(base_snap: dict, new_snap: dict) -> list:
    """
    Compares the new volume snapshot against the accumulated base snapshot
    to flag discrepancies or consistency issues.
    """
    conflicts = []
    base_chars = base_snap.get("characters", {})
    new_chars = new_snap.get("characters", {})

    for name, new_data in new_chars.items():
        if name in base_chars:
            base_data = base_chars[name]
            
            # 1. Deceased character resurrected conflict
            if base_data.get("status") == "deceased" and new_data.get("status") == "active":
                conflicts.append({
                    "type": "character_resurrection",
                    "entity": name,
                    "description": f"Character was marked DECEASED in previous volumes but appears ACTIVE in this volume."
                })

            # 2. Relationship shift conflict (e.g. from wife to enemy, might be story element, but flag it)
            base_rels = base_data.get("relationships", {})
            new_rels = new_data.get("relationships", {})
            for target, new_rel in new_rels.items():
                if target in base_rels:
                    # If relation name matches, look for strong words like enemy vs ally
                    b_rel = base_rels[target].lower()
                    n_rel = new_rel.lower()
                    if ("wife" in b_rel and "enemy" in n_rel) or ("husband" in b_rel and "enemy" in n_rel):
                        conflicts.append({
                            "type": "relationship_anomaly",
                            "entity": f"{name} -> {target}",
                            "description": f"Relationship shifted dramatically: '{base_rels[target]}' to '{new_rel}'."
                        })

    return conflicts

def merge_lore_snapshot(base_snap: dict, new_snap: dict) -> dict:
    """
    Merges a new volume lore snapshot into the base accumulated snapshot.
    Resolves conflicts and appends updates.
    """
    merged = {
        "accumulated_through": new_snap.get("accumulated_through", base_snap.get("accumulated_through")),
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "characters": {},
        "locations": {},
        "world_rules": list(base_snap.get("world_rules", [])),
        "open_threads": list(base_snap.get("open_threads", [])),
        "conflicts": list(base_snap.get("conflicts", []))
    }

    # Merge Characters
    base_chars = base_snap.get("characters", {})
    new_chars = new_snap.get("characters", {})
    all_char_names = set(base_chars.keys()).union(new_chars.keys())

    for name in all_char_names:
        if name in base_chars and name in new_chars:
            bc = base_chars[name]
            nc = new_chars[name]
            
            # Deceased state persists unless updated explicitly
            status = nc.get("status", bc.get("status", "unknown"))
            if bc.get("status") == "deceased" and nc.get("status") != "deceased":
                # Resurrected check, keep deceased or new status but flag
                status = nc.get("status")
            
            # Combine facts
            facts = list(bc.get("key_facts", []))
            for f in nc.get("key_facts", []):
                if f not in facts:
                    facts.append(f)
            
            # Merge relationships
            rels = dict(bc.get("relationships", {}))
            rels.update(nc.get("relationships", {}))

            # Merge roles
            roles = list(set(bc.get("roles", []) + nc.get("roles", [])))

            merged["characters"][name] = {
                "status": status,
                "first_appeared": bc.get("first_appeared") or nc.get("first_appeared"),
                "last_appeared": nc.get("last_appeared") or bc.get("last_appeared"),
                "key_facts": facts,
                "relationships": rels,
                "roles": roles
            }
            if "aliases" in bc or "aliases" in nc:
                merged["characters"][name]["aliases"] = list(set(bc.get("aliases", []) + nc.get("aliases", [])))

        elif name in base_chars:
            merged["characters"][name] = base_chars[name]
        else:
            merged["characters"][name] = new_chars[name]

    # Merge Locations
    base_locs = base_snap.get("locations", {})
    new_locs = new_snap.get("locations", {})
    all_locs = set(base_locs.keys()).union(new_locs.keys())

    for loc in all_locs:
        if loc in base_locs and loc in new_locs:
            bl = base_locs[loc]
            nl = new_locs[loc]
            merged["locations"][loc] = {
                "first_seen": bl.get("first_seen") or nl.get("first_seen"),
                "atmospheres": list(set(bl.get("atmospheres", []) + nl.get("atmospheres", []))),
                "key_events": list(set(bl.get("key_events", []) + nl.get("key_events", [])))
            }
        elif loc in base_locs:
            merged["locations"][loc] = base_locs[loc]
        else:
            merged["locations"][loc] = new_locs[loc]

    # Merge world rules
    for rule in new_snap.get("world_rules", []):
        if rule not in merged["world_rules"]:
            merged["world_rules"].append(rule)

    # Merge open threads (remove ones that are solved or keep updated)
    # Simple strategy: append new ones
    for thread in new_snap.get("open_threads", []):
        if thread not in merged["open_threads"]:
            merged["open_threads"].append(thread)

    # Detect conflicts and add to the conflict log
    new_conflicts = detect_conflicts(base_snap, new_snap)
    merged["conflicts"].extend(new_conflicts)

    return merged

def save_lore_snapshot(saga_dir: str, vol_num: int, snapshot: dict):
    """Save the lore snapshot to the shared directory in saga_dir."""
    shared_dir = os.path.join(saga_dir, "shared")
    os.makedirs(shared_dir, exist_ok=True)
    snapshot_path = os.path.join(shared_dir, f"lore_universe_v{vol_num}.json")
    write_json(snapshot_path, snapshot)
    print(f"[SUCCESS] Saved lore snapshot v{vol_num} to {snapshot_path}")

def load_lore_snapshot(saga_dir: str, vol_num: int) -> dict:
    """Load the lore snapshot from the shared directory in saga_dir."""
    shared_dir = os.path.join(saga_dir, "shared")
    snapshot_path = os.path.join(shared_dir, f"lore_universe_v{vol_num}.json")
    if not os.path.exists(snapshot_path):
        return {}
    return load_json(snapshot_path)
