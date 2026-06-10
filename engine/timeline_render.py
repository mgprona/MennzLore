#!/usr/bin/env python3
"""
MennzLore Timeline Renderer
============================
Phase 3.1: Generates an interactive SVG timeline from timeline_framework.json
and chapter_appearance.json.

Features:
  - Horizontal chapter timeline with day markers
  - Character appearance heatmap (who appears in which chapter)
  - Location tracking across chapters
  - Major milestone markers
  - Dark theme, pure Python SVG generation

Data sources:
  verification/<prefix>_timeline_framework.json
  verification/<prefix>_chapter_appearance.json
"""
import os
import sys
import json
import glob
from collections import defaultdict
from typing import List, Dict, Optional


# ── Color Palette ────────────────────────────────────────────────────────────

CHAPTER_COLORS = [
    "#4a9eff", "#e8a838", "#ff6b6b", "#34d399", "#a855f7",
    "#f472b6", "#22d3ee", "#fb923c", "#818cf8", "#fbbf24",
]


# ── Data Loading ─────────────────────────────────────────────────────────────

def _load_json_safe(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _unwrap(data, key: str):
    """Unwrap {'item': [...]} or {'item': {'item': ...}} wrappers."""
    while isinstance(data, dict) and "item" in data and len(data) == 1:
        data = data["item"]
    if isinstance(data, dict) and key in data:
        return data[key]
    return data


# ── SVG Builder ──────────────────────────────────────────────────────────────

def _render_svg_timeline(timeline: List[dict], chapter_appearance: dict,
                         prefix: str) -> str:
    """Render a full SVG timeline."""
    if not timeline:
        return _empty_svg("No timeline data found")
    
    width = 1400
    header_height = 80
    chapter_row_height = 50
    char_row_height = 20
    margin = 40
    
    # Compute heights
    n_chapters = len(timeline)
    
    # Collect all characters across all chapters
    all_characters = set()
    chapter_chars = {}
    for ch in timeline:
        ch_id = ch.get("chapter_id", "?")
        ca = chapter_appearance.get(ch_id, {})
        present = ca.get("characters_present", [])
        if isinstance(present, list):
            chapter_chars[ch_id] = [c for c in present if isinstance(c, str)]
            all_characters.update(chapter_chars[ch_id])
    
    all_characters = sorted(all_characters)
    n_chars = len(all_characters)
    
    total_height = header_height + chapter_row_height + 30 + (n_chars * char_row_height) + margin * 2
    if n_chars == 0:
        total_height = header_height + chapter_row_height + margin * 2
    
    # Calculate layout
    chart_width = width - margin * 2
    chapter_width = chart_width / max(n_chapters, 1)
    
    # ── SVG header ──
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_height}" '
        f'width="{width}" height="{total_height}">',
        f'<rect width="100%" height="100%" fill="#0d1117"/>',
        f'<text x="{margin}" y="30" fill="#c9d1d9" font-family="monospace" font-size="16" font-weight="bold">'
        f'📅 {prefix} — Story Timeline</text>',
        f'<text x="{margin}" y="52" fill="#8b949e" font-family="monospace" font-size="11">'
        f'{n_chapters} chapters · {n_chars} characters</text>',
    ]
    
    # ── Day axis ──
    y_axis = header_height
    max_day = max((ch.get("day", 0) or 0) for ch in timeline)
    if max_day == 0:
        max_day = n_chapters
    
    # Day markers
    parts.append(f'<line x1="{margin}" y1="{y_axis}" x2="{width - margin}" y2="{y_axis}" '
                 f'stroke="#30363d" stroke-width="2"/>')
    
    for i, ch in enumerate(timeline):
        x = margin + i * chapter_width + chapter_width / 2
        parts.append(f'<line x1="{x:.0f}" y1="{y_axis - 5}" x2="{x:.0f}" y2="{y_axis + 5}" '
                     f'stroke="#484f58" stroke-width="1"/>')
        
        day = ch.get("day", i + 1) or i + 1
        parts.append(f'<text x="{x:.0f}" y="{y_axis - 12}" text-anchor="middle" '
                     f'fill="#8b949e" font-family="monospace" font-size="9">Day {day}</text>')
    
    # ── Chapter row ──
    y_chapter = y_axis + 20
    for i, ch in enumerate(timeline):
        x = margin + i * chapter_width
        color = CHAPTER_COLORS[i % len(CHAPTER_COLORS)]
        ch_id = ch.get("chapter_id", f"CH{i+1}")
        title = ch.get("title", ch_id)
        location = ch.get("primary_location", "")
        
        # Chapter block
        bw = chapter_width - 4
        parts.append(f'<rect x="{x + 2:.0f}" y="{y_chapter:.0f}" width="{bw:.0f}" '
                     f'height="{chapter_row_height - 4:.0f}" fill="{color}" opacity="0.15" '
                     f'stroke="{color}" stroke-width="1" rx="3"/>')
        
        # Chapter label
        parts.append(f'<text x="{x + chapter_width/2:.0f}" y="{y_chapter + 18:.0f}" '
                     f'text-anchor="middle" fill="{color}" font-family="monospace" font-size="10">'
                     f'{ch_id}</text>')
        
        # Title truncation
        short_title = title[:15] + ("…" if len(title) > 15 else "")
        parts.append(f'<text x="{x + chapter_width/2:.0f}" y="{y_chapter + 34:.0f}" '
                     f'text-anchor="middle" fill="#8b949e" font-family="sans-serif" font-size="8">'
                     f'{short_title}</text>')
    
    # ── Character heatmap ──
    if n_chars > 0:
        y_char = y_chapter + chapter_row_height + 10
        
        # Character labels
        max_label_width = 120
        parts.append(f'<text x="{margin}" y="{y_char + 12}" fill="#8b949e" '
                     f'font-family="monospace" font-size="9">Characters</text>')
        
        char_y_positions = {}
        for ci, char in enumerate(all_characters):
            cy = y_char + 20 + ci * char_row_height
            char_y_positions[char] = cy + char_row_height / 2
            
            # Truncate long names
            label = char[:20] + ("…" if len(char) > 20 else "")
            parts.append(f'<text x="{margin}" y="{cy + 12:.0f}" fill="#c9d1d9" '
                         f'font-family="sans-serif" font-size="9" text-anchor="end">{label}</text>')
        
        # Grid lines
        for ci in range(n_chars + 1):
            gy = y_char + 20 + ci * char_row_height
            parts.append(f'<line x1="{margin + 5}" y1="{gy:.0f}" '
                         f'x2="{width - margin}" y2="{gy:.0f}" '
                         f'stroke="#21262d" stroke-width="1"/>')
        
        # Heatmap dots
        for i, ch in enumerate(timeline):
            ch_id = ch.get("chapter_id", "?")
            x = margin + i * chapter_width + chapter_width / 2
            color = CHAPTER_COLORS[i % len(CHAPTER_COLORS)]
            
            for char in chapter_chars.get(ch_id, []):
                if char in char_y_positions:
                    cy = char_y_positions[char]
                    parts.append(f'<circle cx="{x:.0f}" cy="{cy:.0f}" r="4" '
                                  f'fill="{color}" opacity="0.8"/>')
    
    # ── Locations summary ──
    all_locations = set()
    for ch in timeline:
        loc = ch.get("primary_location", "")
        if loc:
            all_locations.add(loc)
    
    if all_locations:
        loc_y = y_chapter + chapter_row_height + 30 + (n_chars * char_row_height) + 20
        parts.append(f'<text x="{margin}" y="{loc_y}" fill="#8b949e" '
                     f'font-family="monospace" font-size="9">📍 Locations: '
                     f'{", ".join(sorted(all_locations)[:10])}</text>')
    
    # ── Legend ──
    legend_x = width - margin - 200
    legend_y = 10
    parts.append(f'<rect x="{legend_x}" y="{legend_y}" width="200" height="40" '
                 f'fill="rgba(13,17,23,0.9)" stroke="#30363d" stroke-width="1" rx="4"/>')
    parts.append(f'<text x="{legend_x + 10}" y="{legend_y + 18}" fill="#c9d1d9" '
                 f'font-family="monospace" font-size="9">● = character appears · colors = chapters</text>')
    parts.append(f'<text x="{legend_x + 10}" y="{legend_y + 33}" fill="#8b949e" '
                 f'font-family="monospace" font-size="8">MennzLore Timeline Renderer</text>')
    
    parts.append('</svg>')
    return '\n'.join(parts)


def _empty_svg(message: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 100" width="400" height="100">
<rect width="100%" height="100%" fill="#0d1117"/>
<text x="200" y="50" text-anchor="middle" fill="#8b949e" font-family="monospace" font-size="12">{message}</text>
</svg>'''


# ── Public API ───────────────────────────────────────────────────────────────

def render_timeline(project_dir: str, prefix: str = "",
                    output_dir: str | None = None) -> dict:
    """Render an SVG timeline from project data.
    
    Args:
        project_dir: Path to project directory
        prefix: Project prefix (auto-detected if empty)
        output_dir: Output directory (default: project_dir/output/spatial/)
    
    Returns:
        dict with output paths and stats
    """
    if not prefix:
        prefix = os.path.basename(project_dir.rstrip("/\\"))
    
    if output_dir is None:
        output_dir = os.path.join(project_dir, "output", "spatial")
    
    verification_dir = os.path.join(project_dir, "verification")
    
    # Load timeline_framework
    tf_path = os.path.join(verification_dir, f"{prefix}_timeline_framework.json")
    tf_data = _load_json_safe(tf_path)
    timeline = _unwrap(tf_data, "timeline_framework")
    if not isinstance(timeline, list):
        timeline = []
    
    # Load chapter_appearance
    ca_path = os.path.join(verification_dir, f"{prefix}_chapter_appearance.json")
    ca_data = _load_json_safe(ca_path)
    chapter_appearance = _unwrap(ca_data, "chapter_appearance")
    if not isinstance(chapter_appearance, dict):
        chapter_appearance = {}
    
    # If no timeline data from verification, try building from micro_facts
    if not timeline:
        mf_dir = os.path.join(project_dir, "micro_facts")
        if not os.path.isdir(mf_dir):
            mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
        
        if os.path.isdir(mf_dir):
            pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
            for fpath in sorted(glob.glob(pattern)):
                data = _load_json_safe(fpath)
                ch_id = data.get("chapter_id", os.path.basename(fpath))
                timeline.append({
                    "chapter_id": ch_id,
                    "title": data.get("chapter_title", ch_id),
                    "day": len(timeline) + 1,
                    "primary_location": "",
                    "summary": "",
                })
                
                # Build chapter_appearance from characters_present
                chars = data.get("characters_present", [])
                if isinstance(chars, list):
                    chapter_appearance[ch_id] = {
                        "characters_present": [c for c in chars if isinstance(c, str)],
                        "mentioned_only": [],
                        "locations": [],
                    }
    
    # Render SVG
    os.makedirs(output_dir, exist_ok=True)
    svg_content = _render_svg_timeline(timeline, chapter_appearance, prefix)
    
    svg_path = os.path.join(output_dir, f"{prefix}_timeline.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    
    # Write JSON data
    json_path = os.path.join(output_dir, f"{prefix}_timeline_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "project_prefix": prefix,
            "chapters": timeline,
            "chapter_appearance": chapter_appearance,
            "total_chapters": len(timeline),
            "total_characters": len(set(
                c for ch in chapter_appearance.values()
                for c in ch.get("characters_present", [])
                if isinstance(c, str)
            )),
            "day_span": max((ch.get("day", 0) or 0) for ch in timeline) if timeline else 0,
        }, f, indent=2, ensure_ascii=False)
    
    return {
        "status": "success",
        "svg_path": svg_path,
        "json_path": json_path,
        "total_chapters": len(timeline),
        "timeline_has_data": len(timeline) > 0,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python timeline_render.py <project_dir> [prefix]")
        sys.exit(1)
    
    proj = sys.argv[1]
    pfx = sys.argv[2] if len(sys.argv) > 2 else ""
    
    result = render_timeline(proj, pfx)
    if result["status"] == "success":
        print(f"[OK] Timeline rendered: {result['total_chapters']} chapters")
        print(f"     SVG:  {result['svg_path']}")
        print(f"     JSON: {result['json_path']}")
    else:
        print(f"[ERROR] {result.get('message', 'Unknown error')}")
