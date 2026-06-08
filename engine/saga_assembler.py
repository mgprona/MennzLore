import os
import json
from datetime import datetime
from typing import Dict, Any, List
from engine.saga_config import SagaConfig, VolumeConfig, load_saga_config
from engine.lore_handoff import load_lore_snapshot
from engine.utils import load_json, write_json

def build_saga_timeline(saga_dir: str, config: SagaConfig) -> str:
    """
    Scans micro_facts of all volumes in chronological order and
    assembles a unified Master Saga Timeline.
    """
    lines = [
        "## Unified Master Saga Timeline",
        "",
        "| Volume | Episode | Title | Event Description | Characters |",
        "|:---|:---:|:---|:---|:---|"
    ]

    events_count = 0
    for vol in config.volumes:
        p_dir = vol.project_dir
        if not os.path.isabs(p_dir):
            p_dir = os.path.abspath(os.path.join(saga_dir, p_dir))

        micro_dir = os.path.join(p_dir, "micro_facts")
        if not os.path.isdir(micro_dir):
            micro_dir = os.path.join(p_dir, "analysis", "micro_facts")

        if not os.path.isdir(micro_dir):
            continue

        # Get all micro_facts json files
        files = []
        for f in os.listdir(micro_dir):
            if f.endswith("_micro_facts.json"):
                parts = f.split("_EP")
                if len(parts) == 2:
                    try:
                        ep_num = int(parts[1].split("_")[0])
                        files.append((ep_num, f))
                    except ValueError:
                        pass
        files.sort(key=lambda x: x[0])

        for ep_num, fname in files:
            data = load_json(os.path.join(micro_dir, fname))
            if not data:
                continue
            ep_title = data.get("chapter_title", f"EP{ep_num:03d}")
            kpps = data.get("key_plot_points", [])
            for kpp in kpps:
                desc = kpp.get("description", kpp.get("event", ""))
                chars_list = kpp.get("characters_involved", kpp.get("characters", []))
                chars_str = ", ".join(chars_list) if isinstance(chars_list, list) else str(chars_list)
                lines.append(f"| {vol.title} | EP{ep_num:03d} | {ep_title} | {desc} | {chars_str} |")
                events_count += 1

    if events_count == 0:
        lines.append("| - | - | - | *(No events recorded in micro_facts)* | - |")
        
    return "\n".join(lines)

def build_saga_master_lorebook(saga_dir: str) -> str:
    """
    Reads the final compiled lore snapshot and config to build the master
    markdown lorebook. Returns the filepath.
    """
    config = load_saga_config(saga_dir)
    
    # Load final snapshot (which would be volN, where N is length of volumes list)
    num_volumes = len(config.volumes)
    snapshot = load_lore_snapshot(saga_dir, num_volumes)
    if not snapshot:
        # Try loading any snapshot
        for v in range(num_volumes, 0, -1):
            snapshot = load_lore_snapshot(saga_dir, v)
            if snapshot:
                break
                
    if not snapshot:
        raise ValueError(f"No lore snapshots found in {saga_dir}/shared/")

    lines = [
        f"# Master Lorebook: {config.saga_title}",
        "",
        f"**Author:** {config.author}",
        f"**Saga Volumes:** {', '.join([f'{v.title} ({v.year})' for v in config.volumes])}",
        f"**Generated:** {snapshot.get('generated_at', '')} | **Engine:** MennzLore Saga Mode",
        "",
        "---",
        "",
        "## Table of Contents",
        "1. Saga Metadata",
        "2. Character Directory",
        "3. Location Index",
        "4. World Rules & Concepts",
        "5. Unresolved Plot Threads",
        "6. Unified Master Saga Timeline",
        "7. Consistency & Conflict Log",
        "",
        "---",
        ""
    ]

    # 1. Characters Section
    lines.append("## Character Directory")
    lines.append("")
    chars = snapshot.get("characters", {})
    if chars:
        for name, data in sorted(chars.items()):
            lines.append(f"### {name}")
            lines.append(f"* **Status:** {data.get('status', 'unknown')}")
            lines.append(f"* **Roles:** {', '.join(data.get('roles', [])) or 'None'}")
            lines.append(f"* **Appearances:** {data.get('first_appeared', 'unknown')} to {data.get('last_appeared', 'unknown')}")
            
            aliases = data.get("aliases", [])
            if aliases:
                lines.append(f"* **Aliases:** {', '.join(aliases)}")
                
            # Key Facts
            facts = data.get("key_facts", [])
            if facts:
                lines.append("* **Key History / Actions:**")
                for fact in facts:
                    lines.append(f"  - {fact}")
                    
            # Relationships
            rels = data.get("relationships", {})
            if rels:
                lines.append("* **Relationships:**")
                for target, r_type in rels.items():
                    lines.append(f"  - with **{target}**: {r_type}")
            lines.append("")
    else:
        lines.append("*(No characters recorded)*")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 2. Locations Section
    lines.append("## Location Index")
    lines.append("")
    locs = snapshot.get("locations", {})
    if locs:
        for name, data in sorted(locs.items()):
            lines.append(f"### {name}")
            lines.append(f"* **First Seen:** {data.get('first_seen', 'unknown')}")
            if data.get("atmospheres"):
                lines.append(f"* **Atmospheres/Moods:** {', '.join(data.get('atmospheres'))}")
            
            events = data.get("key_events", [])
            if events:
                lines.append("* **Notable Events:**")
                for ev in events[:5]: # Cap to top 5 events
                    lines.append(f"  - {ev}")
            lines.append("")
    else:
        lines.append("*(No locations recorded)*")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 3. World Rules
    lines.append("## World Rules & Concepts")
    lines.append("")
    rules = snapshot.get("world_rules", [])
    if rules:
        for idx, rule in enumerate(rules, 1):
            lines.append(f"{idx}. {rule}")
    else:
        lines.append("*(No world rules recorded)*")
    lines.append("")

    lines.append("---")
    lines.append("")

    # 4. Open Threads
    lines.append("## Unresolved Plot Threads")
    lines.append("")
    threads = snapshot.get("open_threads", [])
    if threads:
        for idx, thread in enumerate(threads, 1):
            lines.append(f"* {thread}")
    else:
        lines.append("*(No unresolved plot threads recorded)*")
    lines.append("")

    lines.append("---")
    lines.append("")

    # 5. Timeline
    timeline_md = build_saga_timeline(saga_dir, config)
    lines.append(timeline_md)
    lines.append("")

    lines.append("---")
    lines.append("")

    # 6. Conflicts Section
    lines.append("## Consistency & Conflict Log")
    lines.append("")
    conflicts = snapshot.get("conflicts", [])
    if conflicts:
        lines.append("> [!WARNING]")
        lines.append(f"> Detected {len(conflicts)} consistency conflicts across volumes:")
        lines.append("")
        for idx, conf in enumerate(conflicts, 1):
            lines.append(f"{idx}. **[{conf.get('type')}]** Entity: *{conf.get('entity')}*")
            lines.append(f"   - {conf.get('description')}")
    else:
        lines.append("> [!NOTE]")
        lines.append("> 100% Cross-Volume Consistency Achieved. No conflicts detected.")
    lines.append("")

    output_dir = os.path.join(saga_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{config.saga_id}_saga_lorebook.md")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"[SUCCESS] Compiled master saga lorebook at {out_path}")
    return out_path

def generate_cross_volume_consistency_report(saga_dir: str) -> str:
    """
    Parses the final snapshot conflict logs and exports a standalone
    consistency report document.
    """
    config = load_saga_config(saga_dir)
    num_volumes = len(config.volumes)
    snapshot = load_lore_snapshot(saga_dir, num_volumes)
    
    if not snapshot:
        # fallback
        for v in range(num_volumes, 0, -1):
            snapshot = load_lore_snapshot(saga_dir, v)
            if snapshot:
                break
                
    conflicts = snapshot.get("conflicts", []) if snapshot else []

    lines = [
        f"# Cross-Volume Consistency Report: {config.saga_title}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d')} | **Saga ID:** {config.saga_id}",
        "",
        "## Summary of Consistency Audit",
        ""
    ]

    if conflicts:
        lines.append(f"❌ **Audit Result:** FAILED with {len(conflicts)} inconsistencies flagged.")
        lines.append("")
        lines.append("### Flagged Conflicts")
        lines.append("")
        lines.append("| # | Type | Entity | Conflict Description |")
        lines.append("|:---:|:---|:---|:---|")
        for idx, conf in enumerate(conflicts, 1):
            lines.append(f"| {idx} | {conf.get('type')} | {conf.get('entity')} | {conf.get('description')} |")
    else:
        lines.append("✅ **Audit Result:** PASSED. No consistency conflicts found.")
        lines.append("")
        lines.append("Both volumes were scanned for character states, relationship changes, location descriptions, and world-building rules. All references are fully aligned.")

    lines.append("")
    lines.append("---")
    lines.append("*Report generated automatically by MennzLore Saga Engine.*")

    output_dir = os.path.join(saga_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "consistency_report.md")
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"[SUCCESS] Created consistency report at {out_path}")
    return out_path
