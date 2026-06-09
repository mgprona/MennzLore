#!/usr/bin/env python3
"""
Generic Lore Pipeline Assembler v3.2

Reads micro_facts + pass2 batches + global_lore → chapters/ + entities/ + output/
"""
import os, sys, json, re
from datetime import datetime
from collections import defaultdict

# Ensure engine/ is importable whether run via MCP or standalone
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_ENGINE_DIR)
for _d in (_REPO_ROOT, _ENGINE_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from engine.utils import build_variant_lookup, normalize_name, normalize_location, load_json

def build_metadata_block(prefix, global_lore, all_eps, total_chars=0):
    meta = global_lore.get("book_metadata", {}) if global_lore else {}
    title = meta.get("title", prefix)
    author = meta.get("author", "")
    theme = meta.get("main_theme", "")
    genre = ", ".join(meta.get("genre", []))
    device = meta.get("narrative_device", "")
    lines = ["---"]
    lines.append(f"Title: {title}")
    if author: lines.append(f"Author: {author}")
    if theme: lines.append(f"Theme: {theme}")
    if genre: lines.append(f"Genre: {genre}")
    if device: lines.append(f"Narrative: {device}")
    if all_eps:
        lines.append(f"Chapters: {len(all_eps)} (EP{all_eps[0]:03d}-EP{all_eps[-1]:03d})")
    if total_chars:
        lines.append(f"Total: {total_chars:,} chars")
    lines.append(f"Pipeline: v3.2 | Generated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("---")
    return "\n".join(lines)

def build_toc(all_eps, char_count, loc_count, concept_count, has_visual):
    lines = ["## Table of Contents", ""]
    sections = [
        "1. Project Metadata", "2. Character Name Map", "3. Timeline Table",
        "4. Master Timeline", "5. Foreshadowing Cross-Reference",
        "6. Character Arc Table", "7. Production -- Pillar 5 (Cinematography)",
        "8. Spatial -- Pillar 6 (Locations & Routes)",
        "9. Map Generation Prompt",
        "10. World State Ledger",
    ]
    ep_range = f"EP{all_eps[0]:03d}-EP{all_eps[-1]:03d}" if all_eps else "?"
    sections.append(f"11. Chapter Summaries ({ep_range})")
    sections.append("12. Entity Directory")
    sections.append(f"   - Characters ({char_count})")
    sections.append(f"   - Locations ({loc_count})")
    sections.append(f"   - Concepts ({concept_count})")
    if has_visual:
        sections.append("   - Visual Style Guide")
    sections.append(f"   - Storyboard ({len(all_eps)} episodes)")
    for s in sections:
        lines.append(s)
    return "\n".join(lines)

def build_world_state_ledger(all_eps, p1data):
    lines = ["## World State Ledger", ""]
    
    # Character states
    lines.append("### Character Status Timeline")
    lines.append("")
    lines.append("| Episode | Scene | Character | State | Description |")
    lines.append("|:---:|:---:|:---|:---:|:---|")
    
    char_rows = 0
    for ep in all_eps:
        data = p1data.get(ep, {})
        states = data.get("character_states", [])
        for cs in states:
            if not isinstance(cs, dict): continue
            scene = cs.get("in_scene_id", "")
            char = cs.get("character", "")
            state = cs.get("state", "")
            desc = cs.get("description", "")
            lines.append(f"| EP{ep:02d} | {scene} | {char} | **{state}** | {desc} |")
            char_rows += 1
            
    if char_rows == 0:
        lines.append("| - | - | - | - | No character status updates recorded |")
        
    lines.append("")
    
    # Items/Props states
    lines.append("### Props & Items Possession Log")
    lines.append("")
    lines.append("| Episode | Scene | Item | Current Owner | Location | Role / Description |")
    lines.append("|:---:|:---:|:---|:---|:---|:---|")
    
    item_rows = 0
    for ep in all_eps:
        data = p1data.get(ep, {})
        items = data.get("items_of_interest", [])
        for item in items:
            if not isinstance(item, dict): continue
            scene = item.get("in_scene_id", "")
            name = item.get("item", "")
            owner = item.get("owner", "") or "n/a"
            loc = item.get("location", "") or "n/a"
            desc = item.get("role_in_chapter", item.get("description", ""))
            lines.append(f"| EP{ep:02d} | {scene} | {name} | {owner} | {loc} | {desc} |")
            item_rows += 1
            
    if item_rows == 0:
        lines.append("| - | - | - | - | - | No items/props recorded |")
        
    lines.append("")
    return "\n".join(lines)

def build_name_map_table(name_map, all_chars):
    lines = ["## Character Name Map", ""]
    chars = name_map.get("characters", name_map.get("name_map", {}))
    if not chars:
        lines.append("*(No name map data)*")
        return "\n".join(lines)
    for canon, data in chars.items():
        standard = data.get("standard", data.get("en", canon))
        aliases = data.get("aliases", [])
        arc = data.get("arc_target", "")
        importance = data.get("importance", "")
        char_eps = all_chars.get(standard, {}).get("eps", [])
        eps_str = f"{char_eps[0]}-{char_eps[-1]}" if len(char_eps) > 1 else (char_eps[0] if char_eps else "?")
        lines.append(f"### {standard}")
        if importance: lines.append(f"- Importance: {importance}")
        if arc: lines.append(f"- Arc: {arc[:120]}")
        if aliases: lines.append(f"- Aliases: {', '.join(aliases)}")
        if char_eps: lines.append(f"- Appears: {eps_str} ({len(char_eps)} episodes)")
        lines.append("")
    return "\n".join(lines)

def build_timeline_table(all_eps, p1data, p2batches):
    lines = ["## Timeline Table", ""]
    lines.append("| EP | Events |")
    lines.append("|:--:|:--------|")
    for ep in all_eps:
        data = p1data.get(ep, {})
        pts = data.get("key_plot_points", [])
        count = len(pts)
        title = data.get("chapter_title", f"EP{ep:02d}")
        lines.append(f"| EP{ep:02d}: {title[:40]} | {count} events |")
    return "\n".join(lines)

def build_master_timeline(all_eps, p1data):
    lines = ["## Master Timeline", ""]
    lines.append("| EP | Event |")
    lines.append("|:--:|:------|")
    rows = []
    for ep in all_eps:
        data = p1data.get(ep, {})
        pts = data.get("key_plot_points", [])
        if pts:
            for i, pt in enumerate(pts):
                desc = pt.get("description", pt.get("event", str(pt))) if isinstance(pt, dict) else str(pt)
                rows.append((ep, i, desc))
        else:
            rows.append((ep, 0, "(no events)"))
    for ep, _, event in rows:
        event_short = event[:100] + "..." if len(event) > 100 else event
        title = data.get("chapter_title", f"EP{ep:02d}") if 'data' in dir() else f"EP{ep:02d}"
        lines.append(f"| EP{ep:02d} | {event_short} |")
    return "\n".join(lines)

def build_foreshadowing_table(global_lore, p2batches):
    lines = ["## Foreshadowing Cross-Reference", ""]
    lines.append("| ID | Planted | Resolved | Description | Status |")
    lines.append("|:---|:--------|:---------|:------------|:------:|")
    if global_lore:
        for clue in global_lore.get("mystery_and_clues_tracker", []):
            cid = clue.get("clue_id", "?")
            planted = f"Ch.{clue.get('introduced_in_chapter', '?')}"
            resolved = f"Ch.{clue.get('resolved_in_chapter')}" if clue.get("resolved_in_chapter") else "-"
            desc = clue.get("description", "")[:70]
            status = "***" if clue.get("is_resolved") else "???"
            lines.append(f"| {cid} | {planted} | {resolved} | {desc} | {status} |")
    if len(lines) <= 2:
        lines.append("| - | - | - | *(No foreshadowing data)* | - |")
    return "\n".join(lines)

def build_char_arc_table(all_chars, p1data, p2batches, global_lore):
    lines = ["## Character Arc Table", ""]
    if not all_chars:
        lines.append("*(No character data)*")
        return "\n".join(lines)
    gl_arcs = {}
    if global_lore:
        for c in global_lore.get("characters", []):
            gl_arcs[c.get("name", "")] = c.get("character_arc", "")
    for char_name in sorted(all_chars.keys()):
        char_data = all_chars[char_name]
        eps = sorted(char_data.get("eps", []), key=lambda x: int(x[2:]))
        arcs = char_data.get("arcs", {})
        lines.append(f"### {char_name}")
        gl_arc = gl_arcs.get(char_name, "")
        if gl_arc:
            lines.append(f"*Global Arc: {gl_arc[:100]}*")
            lines.append("")
        sample_eps = set()
        if eps:
            sample_eps.update([eps[0], eps[-1]])
        for ep_str in eps:
            ep_num = int(ep_str[2:])
            if ep_num % 5 == 0:
                sample_eps.add(ep_str)
        for ep_str in sorted(sample_eps, key=lambda x: int(x[2:])):
            ep_num = int(ep_str[2:])
            arc = arcs.get(ep_str, "")
            day = p1data.get(ep_num, {}).get("timeline", {}).get("day", "")
            lines.append(f"* **{ep_str}** (Day {day}): {arc[:80]}")
        lines.append("")
    return "\n".join(lines)

def build_production_section(p2batches):
    lines = ["## Production -- Pillar 5", ""]
    total_shots = 0
    for batch_id, batch in sorted(p2batches.items()):
        p5 = batch.get("pillar_5_production", {})
        if not p5:
            p5 = batch.get("pillar_5_production_pipeline", {})
        if not p5:
            continue
        # Handle both string and list batch_range
        br = batch.get("batch_range", batch.get("chapters_covered", ""))
        if isinstance(br, list):
            br_str = f"{br[0]}-{br[-1]}"
        elif isinstance(br, str):
            br_str = br
        else:
            br_str = f"Batch {batch_id}"
        shots = p5.get("cinematography_shot_list", [])
        if shots:
            lines.append(f"### Batch {batch_id}: {br_str}")
            lines.append("")
            lines.append("| # | Duration | Type | Size | Movement | Description | Source |")
            lines.append("|:--|:---------|:-----|:-----|:---------|:------------|:-------|")
            for shot in shots:
                if isinstance(shot, dict):
                    sid = shot.get("shot_id", "?")
                    dur = shot.get("duration_sec", "?")
                    stype = shot.get("type", "?")
                    ssize = shot.get("shot_size", "?")
                    move = shot.get("camera_movement", "?")
                    desc = shot.get("description", "")[:60]
                    src = shot.get("source_scene", "")
                    lines.append(f"| {sid} | {dur}s | {stype} | {ssize} | {move} | {desc} | {src} |")
                    total_shots += 1
            lines.append("")
    if total_shots == 0:
        lines.append("*No cinematography shot data available*")
    else:
        lines.append(f"**Total shots:** {total_shots}")
    lines.append("")
    return "\n".join(lines)

def build_spatial_section(p2batches):
    lines = ["## Spatial -- Pillar 6", ""]
    all_locations = []
    for batch_id, batch in sorted(p2batches.items()):
        p6 = batch.get("pillar_6_spatial", {})
        if not p6:
            p6 = batch.get("pillar_6_spatial_intelligence", {})
        if not p6:
            continue
        # Handle both string and dict batch_range
        br = batch.get("batch_range", batch.get("chapters_covered", ""))
        if isinstance(br, list):
            br_str = f"{br[0]}-{br[-1]}"
        elif isinstance(br, str):
            br_str = br
        else:
            br_str = f"Batch {batch_id}"
        batch_label = f"Batch {batch_id} ({br_str})"
        concepts = p6.get("visual_concepts", [])
        if concepts:
            lines.append(f"### {batch_label} - Visual Concepts ({len(concepts)})")
            lines.append("")
            for vc in concepts:
                if isinstance(vc, dict):
                    scene = vc.get("scene", "?")
                    desc = vc.get("description", "")[:100]
                    archetype = vc.get("archetype", "")
                    tone = vc.get("emotional_tone", "")
                    lines.append(f"- **{scene}** [{archetype}] - {tone}")
                    if desc:
                        lines.append(f"  - {desc}")
                    all_locations.append(vc)
            lines.append("")
    if not all_locations:
        lines.append("*No spatial data available*")
    else:
        lines.append(f"**Totals:** {len(all_locations)} visual concepts")
    lines.append("")
    return "\n".join(lines)

def build_map_prompt_section(project_dir, prefix):
    lines = ["## Map Generation Prompt", ""]
    prompt_path = os.path.join(project_dir, "output", "spatial", "map_image_prompt.json")
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lines.append("Use these prompts in AI image generators to create a tangible fantasy map of the story world:")
            lines.append("")
            lines.append("**Midjourney Prompt:**")
            lines.append(f"```text\n{data.get('prompt_midjourney', '')}\n```")
            lines.append("")
            lines.append("**Stable Diffusion Prompt:**")
            lines.append(f"```text\n{data.get('prompt_stable_diffusion', '')}\n```")
        except Exception as e:
            lines.append(f"*(Error loading map prompt: {e})*")
    else:
        lines.append("*(No map generation prompt found)*")
    lines.append("")
    return "\n".join(lines)

def assemble_lorebook(project_dir, prefix, prior_lore_context: str = None):
    PROJECT = project_dir.rstrip("/\\")
    PREFIX = prefix
    MF_DIR = os.path.join(PROJECT, "micro_facts")
    if not os.path.isdir(MF_DIR):
        MF_DIR = os.path.join(PROJECT, "analysis", "micro_facts")
    P2_DIR = os.path.join(PROJECT, "analysis", "pass2")
    CHAPTERS = os.path.join(PROJECT, "chapters")
    ENTITIES = os.path.join(PROJECT, "entities")
    OUTPUT = os.path.join(PROJECT, "output")
    VERIFICATION = os.path.join(PROJECT, "verification")
    for d in [CHAPTERS, ENTITIES, OUTPUT]:
        os.makedirs(d, exist_ok=True)
    
    global_lore = None
    gl_path = os.path.join(VERIFICATION, f"{PREFIX}_global_lore.json")
    if os.path.exists(gl_path):
        with open(gl_path, encoding="utf-8") as f:
            global_lore = json.load(f)
        print("Loaded global_lore.json")
    
    name_map = {}
    nm_path = os.path.join(VERIFICATION, f"{PREFIX}_name_map.json")
    if os.path.exists(nm_path):
        with open(nm_path, encoding="utf-8") as f:
            name_map = json.load(f)
    title = name_map.get("_meta", {}).get("title", "")
    author = name_map.get("_meta", {}).get("author", "")
    if not title and global_lore:
        title = global_lore.get("book_metadata", {}).get("title", PREFIX)
    if not author and global_lore:
        author = global_lore.get("book_metadata", {}).get("author", "")
    variant_lookup = build_variant_lookup(name_map)
    
    mf_files = {}
    if os.path.isdir(MF_DIR):
        for f in os.listdir(MF_DIR):
            m = re.match(rf'{PREFIX}_EP(\d+)_micro_facts\.json', f)
            if m: mf_files[int(m.group(1))] = f
    
    p2_files = {}
    if os.path.isdir(P2_DIR):
        for f in os.listdir(P2_DIR):
            m = re.match(rf'{PREFIX}_batch_(\d+)_pass2\.json', f)
            if m: p2_files[int(m.group(1))] = f
    
    all_eps = sorted(mf_files.keys())
    if not all_eps:
        # Raise instead of sys.exit(1) so the MCP tool wrapper sees a normal
        # exception and returns a fast [ERROR] message. Calling sys.exit()
        # inside an MCP tool would propagate a SystemExit that the wrapper
        # does not catch, causing the call to spin until the MCP timeout.
        raise FileNotFoundError(
            f"No micro_facts files found in {MF_DIR}. Run Phase 4 (3-Pass "
            f"analysis + merge) before Phase 7 (assemble)."
        )
    print(f"Found: {len(all_eps)} micro_facts, {len(p2_files)} pass2 batches")
    
    p1data = {}
    p2data = {}
    p2batches = {}
    for ep in all_eps:
        fpath = os.path.join(MF_DIR, f"{PREFIX}_EP{ep:03d}_micro_facts.json")
        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as f:
                p1data[ep] = json.load(f)
    for batch_id in sorted(p2_files):
        fpath = os.path.join(P2_DIR, p2_files[batch_id])
        with open(fpath, encoding="utf-8") as f:
            batch = json.load(f)
        p2batches[batch_id] = batch
        
        # Detect structure: new-style (with "chapters_covered" + "pillars") or old-style (flat pillar keys)
        if "chapters_covered" in batch and isinstance(batch["chapters_covered"], list):
            # New structure (from skill's assemble script)
            chapters = batch["chapters_covered"]
            from_ch = int(chapters[0].replace("EP", ""))
            to_ch = int(chapters[-1].replace("EP", ""))
            pillars = batch.get("pillars", {})
            p3 = pillars.get("pillar_3_entity_and_world_intelligence", {})
            p4 = pillars.get("pillar_4_literary_texture", {})
        else:
            # Old structure (from delegate_task subagents)
            br = batch.get("batch_range", "")
            if "EP" in str(br):
                parts = str(br).split("-")
                from_ch = int(parts[0].replace("EP", "").replace("EP", ""))
                to_ch = int(parts[-1].replace("EP", "").replace("EP", ""))
            else:
                from_ch = batch_id * 5 - 4
                to_ch = batch_id * 5
            p3 = batch.get("pillar_3_entity_world", {})
            p4 = batch.get("pillar_4_literary_texture", {})
        for ep in range(from_ch, to_ch + 1):
            if ep in all_eps:
                chars = {}
                # Batch 1: core_cast (list) + supporting_cast (list) directly in p3
                # Batch 2: characters dict with core_cast list inside
                
                # Try flat core_cast first (Batch 1 style)
                core_list = p3.get("core_cast", [])
                chars_field = p3.get("characters")
                if not core_list and isinstance(chars_field, dict):
                    # Batch 2 style: characters = {"core_cast": [...], ...}
                    core_list = chars_field.get("core_cast", [])
                    # voodoo style: characters = {"<name>": {...}, ...}
                    if not core_list and not any(
                        k in chars_field for k in ("core_cast", "supporting_cast")
                    ):
                        core_list = [
                            {**v, "name": v.get("name", name)}
                            for name, v in chars_field.items()
                            if isinstance(v, dict)
                        ]
                
                # Get characters actually present in this episode from micro_facts
                ep_p1 = p1data.get(ep, {})
                present_chars = set()
                for c in ep_p1.get("characters_present", []):
                    if isinstance(c, str):
                        present_chars.add(c.strip())
                    elif isinstance(c, dict):
                        present_chars.add(c.get("name", "").strip())
                
                if isinstance(core_list, list):
                    for item in core_list:
                        if isinstance(item, dict):
                            name = item.get("name", "")
                            # Only include if this character is in the episode
                            if name and (name in present_chars or not present_chars):
                                chars[name] = item
                    # If no chars matched, include all core cast (fallback)
                    if not chars and core_list:
                        for item in core_list:
                            if isinstance(item, dict) and item.get("name"):
                                chars[item["name"]] = item
                
                # Also capture supporting_cast if present (Batch 1) - same filter
                supp_list = p3.get("supporting_cast", [])
                if isinstance(supp_list, list):
                    for item in supp_list:
                        if isinstance(item, dict):
                            name = item.get("name", "")
                            if name and name not in chars and (name in present_chars or not present_chars):
                                chars[name] = item
                setting_entries = []
                # Handle batch 1: key_locations list, batch 2: locations dict
                key_locs = p3.get("key_locations", [])
                if isinstance(key_locs, list):
                    for s in key_locs:
                        if isinstance(s, dict):
                            setting_entries.append(s)
                # Batch 2 style: locations dict
                locs_dict = p3.get("locations", {})
                if isinstance(locs_dict, dict):
                    for loc_name, loc_desc in locs_dict.items():
                        if loc_desc:
                            setting_entries.append({"location": loc_name, "description": str(loc_desc)[:200]})
                p2data[ep] = {
                    "characters": chars,
                    "setting": setting_entries or [{}],
                    "essential_lore": p3.get("essential_lore", []),
                    "world_building_elements": p3.get("world_building_elements", []),
                    "emotional_arc": p4.get("emotional_arc", {}),
                    "tone": p4.get("tone", {}),
                    "symbolism": p4.get("symbolism", []),
                    "themes": p4.get("themes", []),
                    "key_quotes": p4.get("key_quotes", []),
                    "cinematic_tags": p4.get("cinematic_tags", {}),
                }
    
    # Fallback for episodes not covered by pass2 batches (e.g. if pass2 is empty)
    for ep in all_eps:
        if ep not in p2data:
            ep_p1 = p1data.get(ep, {})
            chars = {}
            present_chars = set()
            for c in ep_p1.get("characters_present", []):
                if isinstance(c, str):
                    present_chars.add(c.strip())
                elif isinstance(c, dict):
                    present_chars.add(c.get("name", "").strip())
            
            for cb in ep_p1.get("character_behaviors", []):
                if isinstance(cb, dict):
                    cname = cb.get("character", cb.get("name", ""))
                    if cname: present_chars.add(cname.strip())
            for cs in ep_p1.get("character_states", []):
                if isinstance(cs, dict):
                    cname = cs.get("character", "")
                    if cname: present_chars.add(cname.strip())
                    
            for cname in present_chars:
                canon = normalize_name(cname, variant_lookup)
                if canon:
                    nm_chars = name_map.get("characters", name_map.get("name_map", {}))
                    char_meta = nm_chars.get(canon, {})
                    
                    arc_this = ""
                    for cs in ep_p1.get("character_states", []):
                        if isinstance(cs, dict) and normalize_name(cs.get("character", ""), variant_lookup) == canon:
                            arc_this = cs.get("description", "")
                            break
                    
                    chars[canon] = {
                        "name": canon,
                        "role": char_meta.get("importance", "Supporting"),
                        "arc_this_chapter": arc_this
                    }
            
            setting_entries = []
            for s in ep_p1.get("scene_details", []):
                if isinstance(s, dict):
                    raw_loc = s.get("location", "")
                    if raw_loc:
                        setting_entries.append({"location": raw_loc, "description": s.get("description", "")[:200]})
            
            essential_lore = []
            for disc in ep_p1.get("lore_discoveries", []):
                if isinstance(disc, dict):
                    desc = disc.get("description", "")
                    if desc:
                        essential_lore.append({"concept": desc, "type": "discovery"})
            
            p2data[ep] = {
                "characters": chars,
                "setting": setting_entries or [{}],
                "essential_lore": essential_lore,
                "world_building_elements": [],
                "emotional_arc": {},
                "tone": {},
                "symbolism": [],
                "themes": [],
                "key_quotes": [],
                "cinematic_tags": {},
            }
    
    print("\n--- Chapter Summaries ---")
    for ep in all_eps:
        p1 = p1data.get(ep, {})
        p2 = p2data.get(ep, {})
        # Use chapter_title from micro_facts
        raw_title = p1.get("chapter_title", p1.get("title", f"EP{ep:02d}"))
        if isinstance(raw_title, dict):
            en_title = raw_title.get("en", f"EP{ep:02d}")
        else:
            en_title = str(raw_title) if raw_title else f"EP{ep:02d}"
        md = []
        md.append("---")
        md.append(f'chapter_id: "EP{ep:02d}"')
        md.append(f'title: "{en_title}"')
        tl = p1.get("timeline", {})
        md.append(f'timeline_day: {tl.get("day", "?")}')
        md.append("---")
        md.append("")
        md.append(f"## {en_title}")
        md.append("")
        pts = p1.get("key_plot_points", [])
        if pts:
            md.append("### Key Plot Points")
            for pt in pts:
                if not isinstance(pt, dict): continue
                ev = pt.get("event", pt.get("description", str(pt)))
                md.append(f"* **{ev}**")
            md.append("")
        chars = p2.get("characters", {})
        if chars:
            md.append("### Characters")
            for name, data in chars.items():
                role = data.get("role", "")
                arc = data.get("arc_this_chapter", "")
                md.append(f"* **{name}**: {role}" + (f" -- {arc}" if arc else ""))
            md.append("")
        scenes = p1.get("scene_details", [])
        if isinstance(scenes, list) and scenes:
            md.append("### Scenes")
            for s in scenes[:3]:
                if isinstance(s, dict):
                    loc = s.get("location", "")
                    atmos = s.get("mood", s.get("atmosphere", ""))
                    md.append(f"* **{loc}** - {atmos}")
            if len(scenes) > 3:
                md.append(f"* ... ({len(scenes)} scenes total)")
            md.append("")
        dial = p1.get("dialogue_summaries", [])
        if isinstance(dial, list) and dial:
            md.append("### Key Dialogue")
            for d in dial[:3]:
                if isinstance(d, dict):
                    sp = d.get("participants", d.get("speaker", ""))
                    topic = d.get("topic", d.get("summary", ""))[:100]
                    if isinstance(sp, list):
                        sp = ", ".join(sp)
                    md.append(f"* **{sp}**: {topic}")
            md.append("")
        outpath = os.path.join(CHAPTERS, f"{PREFIX}_EP{ep:02d}_summary.md")
        with open(outpath, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        print(f"  EP{ep:02d}: {en_title[:40]} ({os.path.getsize(outpath):,} bytes)")
    
    print("\n--- Entities ---")
    all_chars = {}
    all_locs = {}
    all_concepts = {}
    char_visuals = defaultdict(list)
    char_relationships = defaultdict(list)
    norm_log = []
    
    for ep in all_eps:
        p1 = p1data.get(ep, {})
        p2 = p2data.get(ep, {})
        for raw_name, data in p2.get("characters", {}).items():
            canon = normalize_name(raw_name, variant_lookup)
            if canon != raw_name:
                norm_log.append(f'  EP{ep:02d}: "{raw_name}" -> "{canon}"')
            if canon not in all_chars:
                all_chars[canon] = {"eps": [], "roles": [], "arcs": {}}
            all_chars[canon]["eps"].append(f"EP{ep:02d}")
            if data.get("role"):
                all_chars[canon]["roles"].append(data["role"])
            arc = data.get("arc_this_chapter") or data.get("arc_progress", "")
            if arc:
                all_chars[canon]["arcs"][f"EP{ep:02d}"] = arc
            for rel_name, rel_type in data.get("relationships", {}).items():
                char_relationships[canon].append({
                    "ep": f"EP{ep:02d}", "target": rel_name, "type": rel_type
                })
            vp = data.get("visual_profile", {})
            if vp and any(vp.values()):
                char_visuals[canon].append({
                    "ep": f"EP{ep:02d}",
                    "day": p1.get("timeline", {}).get("day", ""),
                    "appearance": vp.get("physical_appearance", ""),
                    "clothing": vp.get("signature_clothing", ""),
                    "props": vp.get("props_and_weapons", []),
                })
        behaviors = p1.get("character_behaviors", [])
        if isinstance(behaviors, list):
            for cb in behaviors:
                if not isinstance(cb, dict): continue
                cname_raw = cb.get("character", cb.get("name", ""))
                if not cname_raw: continue
                cname = normalize_name(cname_raw, variant_lookup)
                if cname and cname not in char_visuals:
                    clothing = cb.get("clothing", "")
                    if clothing:
                        char_visuals[cname].append({
                            "ep": f"EP{ep:02d}",
                            "day": p1.get("timeline", {}).get("day", ""),
                            "appearance": cb.get("physical_description", ""),
                            "clothing": clothing,
                            "props": cb.get("props_held", []),
                        })
        for s in p1.get("scene_details", []):
            if not isinstance(s, dict): continue
            raw_loc = s.get("location", "")
            if raw_loc:
                base = normalize_location(raw_loc)
                if base not in all_locs:
                    all_locs[base] = {"eps": [], "atmospheres": []}
                all_locs[base]["eps"].append(f"EP{ep:02d}")
                atmos = s.get("mood", s.get("atmosphere", ""))
                if atmos:
                    all_locs[base]["atmospheres"].append(atmos)
        for l_item in p2.get("essential_lore", []):
            if not l_item: continue
            # Handle both string list and dict list; also check world_building_elements
            if isinstance(l_item, str):
                c = l_item
                l_type = "uncategorized"
            elif isinstance(l_item, dict):
                c = l_item.get("concept", l_item.get("element", ""))
                l_type = l_item.get("type", "uncategorized")
            else:
                continue
            if c and c not in all_concepts:
                all_concepts[c] = {"eps": [], "type": l_type}
            if c:
                all_concepts[c]["eps"].append(f"EP{ep:02d}")
        
        # Also check world_building_elements (Batch 1 style)
        wb = p2.get("world_building_elements", [])
        if isinstance(wb, list):
            for item in wb:
                if isinstance(item, str):
                    if item not in all_concepts:
                        all_concepts[item] = {"eps": [], "type": "world_building"}
                    all_concepts[item]["eps"].append(f"EP{ep:02d}")
                elif isinstance(item, dict):
                    c = item.get("concept", item.get("element", ""))
                    if c and c not in all_concepts:
                        all_concepts[c] = {"eps": [], "type": "world_building"}
                    if c:
                        all_concepts[c]["eps"].append(f"EP{ep:02d}")
    
    if norm_log:
        print(f"  Name normalizations ({len(norm_log)}):")
        for log in norm_log[:10]:
            print(log)
    
    lines = [f"# Characters - {title}", ""]
    for name, data in sorted(all_chars.items()):
        eps_list = sorted(set(data["eps"]), key=lambda x: int(x[2:]))
        roles = list(set(data["roles"]))
        lines.append(f"## {name}")
        lines.append(f"**Appears:** {eps_list[0]}-{eps_list[-1]} ({len(eps_list)} episodes)")
        if roles: lines.append(f"**Roles:** {'; '.join(roles)}")
        if global_lore:
            for c in global_lore.get("characters", []):
                if c.get("name") == name and c.get("character_arc"):
                    lines.append(f"**Global Arc:** {c['character_arc'][:120]}")
                    break
        lines.append("")
        arcs = data.get("arcs", {})
        if arcs:
            lines.append("### Arc Timeline")
            for ep_str in sorted(arcs.keys(), key=lambda x: int(x[2:])):
                lines.append(f"* **{ep_str}**: {arcs[ep_str][:80]}")
            lines.append("")
        rels = char_relationships.get(name, [])
        if rels:
            lines.append("### Relationships")
            seen = {}
            for r in rels:
                t = normalize_name(r["target"], variant_lookup)
                if t not in seen:
                    seen[t] = {"types": [], "eps": []}
                seen[t]["types"].append(r["type"])
                seen[t]["eps"].append(r["ep"])
            for target, info in sorted(seen.items()):
                ut = list(set(info["types"]))
                ep_r = f"{info['eps'][0]}-{info['eps'][-1]}" if len(info['eps']) > 1 else info['eps'][0]
                lines.append(f"* **{target}** - {'; '.join(ut)} ({ep_r})")
            lines.append("")
    with open(os.path.join(ENTITIES, f"{PREFIX}_characters.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    lines = [f"# Locations - {title}", ""]
    for loc, data in sorted(all_locs.items()):
        eps_list = sorted(set(data["eps"]), key=lambda x: int(x[2:]))
        atmos = list(set(data["atmospheres"]))
        lines.append(f"* **{loc}** ({', '.join(eps_list[:10])}): {'; '.join(atmos[:3])}")
    with open(os.path.join(ENTITIES, f"{PREFIX}_locations.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    lines = [f"# Concepts - {title}", ""]
    by_type = defaultdict(list)
    for c, data in sorted(all_concepts.items()):
        t = data.get("type", "uncategorized") or "uncategorized"
        by_type[t].append((c, data))
    for t in sorted(by_type.keys()):
        lines.append(f"## {t.title()}")
        for c, data in by_type[t]:
            eps_list = sorted(set(data["eps"]), key=lambda x: int(x[2:]))
            lines.append(f"* **{c}** ({', '.join(eps_list[:10])})")
        lines.append("")
    with open(os.path.join(ENTITIES, f"{PREFIX}_concepts.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Entities: {len(all_chars)} chars, {len(all_locs)} locs, {len(all_concepts)} concepts")
    
    lines = [f"# Visual Style Guide - {title}", ""]
    for char_name in sorted(char_visuals.keys()):
        entries = char_visuals[char_name]
        lines.append(f"## {char_name}")
        for v in entries:
            parts = []
            if v["appearance"]: parts.append(f"Appearance: {v['appearance']}")
            if v["clothing"]: parts.append(f"Clothing: {v['clothing']}")
            props = v["props"]
            props_str = ", ".join(str(p) for p in props if p) if isinstance(props, list) else str(props)
            if props_str: parts.append(f"Props: {props_str}")
            day_str = f" (Day {v['day']})" if v["day"] else ""
            lines.append(f"* **{v['ep']}**{day_str}: {' | '.join(parts) if parts else '-'}")
        lines.append("")
    vsp = os.path.join(ENTITIES, f"{PREFIX}_visual_style.md")
    with open(vsp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Visual style: {len(char_visuals)} characters")
    
    lines = [f"# Storyboard - {title}", ""]
    for ep in all_eps:
        p1 = p1data.get(ep, {})
        raw_title = p1.get("title", "")
        if isinstance(raw_title, dict):
            en_title = raw_title.get("en", f"EP{ep:02d}")
        else:
            en_title = str(raw_title) if raw_title else f"EP{ep:02d}"
        tl = p1.get("timeline", {})
        day = tl.get("day", "")
        lines.append(f"## EP{ep:02d}: {en_title}")
        lines.append(f"*Day {day}*")
        lines.append("")
        for pt in p1.get("key_plot_points", [])[:5]:
            if isinstance(pt, dict):
                lines.append(f"- {pt.get('event', pt.get('description', str(pt)))}")
        lines.append("")
    sbp = os.path.join(ENTITIES, f"{PREFIX}_storyboard.md")
    with open(sbp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    master = []
    master.append(title)
    master.append("")
    master.append(f"**Author:** {author} | **Chapters:** {len(all_eps)}")
    master.append("")
    master.append("## Chapters")
    for ep in all_eps:
        en = ""
        raw = p1data.get(ep, {}).get("title", "")
        if isinstance(raw, dict): en = raw.get("en", "")
        elif isinstance(raw, str): en = raw
        master.append(f"* [EP{ep:02d}: {en}](chapters/{PREFIX}_EP{ep:02d}_summary.md)")
    master.append("")
    master.append("## Entities")
    for label, fname in [("Characters", "characters"), ("Locations", "locations"),
                         ("Concepts", "concepts"), ("Visual Style", "visual_style"),
                         ("Storyboard", "storyboard")]:
        path = os.path.join(ENTITIES, f"{PREFIX}_{fname}.md")
        if os.path.exists(path):
            master.append(f"* [{label}](entities/{PREFIX}_{fname}.md)")
    master.append("")
    with open(os.path.join(OUTPUT, f"{PREFIX}_master_lorebook.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(master))
    print("  Master lorebook (modular)")
    
    total_chars = sum(os.path.getsize(os.path.join(MF_DIR, mf_files[ep]))
                      for ep in all_eps if os.path.exists(os.path.join(MF_DIR, mf_files[ep])))
    full = []
    full.append(build_metadata_block(PREFIX, global_lore, all_eps, total_chars))
    if prior_lore_context:
        full.append(f"# Prior Lore Context\n\n{prior_lore_context}")
    full.append(build_toc(all_eps, len(all_chars), len(all_locs), len(all_concepts), bool(char_visuals)))
    full.append(build_name_map_table(name_map, all_chars))
    full.append(build_timeline_table(all_eps, p1data, p2batches))
    full.append(build_master_timeline(all_eps, p1data))
    full.append(build_foreshadowing_table(global_lore, p2batches))
    full.append(build_char_arc_table(all_chars, p1data, p2batches, global_lore))
    full.append(build_production_section(p2batches))
    full.append(build_spatial_section(p2batches))
    full.append(build_map_prompt_section(PROJECT, PREFIX))
    full.append(build_world_state_ledger(all_eps, p1data))
    summaries = ["# Chapter Summaries"]
    for ep in all_eps:
        ch_path = os.path.join(CHAPTERS, f"{PREFIX}_EP{ep:02d}_summary.md")
        if os.path.exists(ch_path):
            with open(ch_path, encoding="utf-8") as f:
                content = f.read()
            content = re.sub(r'^---\n.*?\n---\n+', '', content, flags=re.DOTALL)
            summaries.append(content)
    full.append("\n".join(summaries))
    for fname, label in [("characters", "Characters"), ("locations", "Locations"),
                         ("concepts", "Concepts")]:
        fp = os.path.join(ENTITIES, f"{PREFIX}_{fname}.md")
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                c = f.read()
            c = re.sub(r'^# .*?\n+', '', c)
            full.append(f"# {label}\n{c}")
    for fname, label in [("visual_style", "Visual Style Guide"), ("storyboard", "Storyboard")]:
        fp = os.path.join(ENTITIES, f"{PREFIX}_{fname}.md")
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as f:
                c = f.read()
            c = re.sub(r'^# .*?\n+', '', c)
            full.append(f"# {label}\n{c}")
            
    # Check if translation state exists (TET Pipeline)
    translation_state_path = os.path.join(PROJECT, f"{PREFIX}_translation_state.json")
    if os.path.exists(translation_state_path):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if api_key:
            print(f"\n[TET Pipeline] Translation state detected. Translating master lorebook sections to Thai...")
            try:
                # Add engine to path just in case
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from translate_raw import translate_english_to_thai
                
                # Write English version first
                english_text = "\n\n---\n\n".join(full)
                fp_en = os.path.join(OUTPUT, f"{PREFIX}_master_lorebook_en.md")
                with open(fp_en, "w", encoding="utf-8") as f:
                    f.write(english_text)
                print(f"  [TET] Saved English master lorebook reference to: {fp_en}")
                
                # Translate each section
                thai_full = []
                for idx, section in enumerate(full):
                    if idx == 0:
                        # Keep metadata block unchanged
                        thai_full.append(section)
                        continue
                    
                    print(f"  Translating section {idx+1}/{len(full)} to Thai...")
                    # Translate using high-quality model (Gemini 2.5 Pro)
                    thai_section = translate_english_to_thai(api_key, section)
                    thai_full.append(thai_section)
                
                full_text = "\n\n---\n\n".join(thai_full)
            except Exception as e:
                print(f"  [WARNING] TET translation back to Thai failed: {e}. Falling back to English version.")
                full_text = "\n\n---\n\n".join(full)
        else:
            print("  [WARNING] OPENROUTER_API_KEY not set. Cannot translate back to Thai. Using English.")
            full_text = "\n\n---\n\n".join(full)
    else:
        full_text = "\n\n---\n\n".join(full)
        
    fp_full = os.path.join(OUTPUT, f"{PREFIX}_master_lorebook_full.md")
    with open(fp_full, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"  Full lorebook: {len(full_text):,} chars")

    
    print(f"\n{'='*60}")
    print(f"ASSEMBLY COMPLETE")
    print(f"{'='*60}")
    print(f"Output: chapters/, entities/, output/")
    print(f"Full lorebook: {fp_full} ({len(full_text):,} chars)")
    return fp_full

def main():
    if len(sys.argv) < 3:
        print("Usage: python assemble_generic.py <project_dir> <prefix>")
        sys.exit(1)
    assemble_lorebook(sys.argv[1], sys.argv[2])

if __name__ == "__main__":
    main()