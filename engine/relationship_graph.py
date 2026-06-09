#!/usr/bin/env python3
"""
MennzLore Relationship Graph
=============================
Phase 1.2 improvement: Reads micro_facts from a project and generates:

1. Force-directed SVG graph (dark theme, character/location/event nodes)
2. GEXF file (Gephi-compatible network export)
3. JSON data file (nodes + edges with evidence)

Pure Python — zero external dependencies. SVG embedded, no browser needed.
"""
import os
import sys
import json
import glob
import math
import random
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class GraphNode:
    id: str
    label: str
    entity_type: str  # CHARACTER, LOCATION, ORGANIZATION, EVENT, CONCEPT, ITEM
    weight: int = 1  # Node size (interaction count)
    chapters: List[str] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0

@dataclass
class GraphEdge:
    source: str
    target: str
    relation_type: str  # interacts_with, opposes, allied_with, mentions, influences, object_transfer
    weight: int = 1  # Edge thickness
    evidence: List[str] = field(default_factory=list)  # Evidence descriptions


# ── Force-Directed Layout (Fruchterman-Reingold) ─────────────────────────────

def _force_layout(nodes: List[GraphNode], edges: List[GraphEdge],
                  width: int = 1200, height: int = 900,
                  iterations: int = 200) -> None:
    """Run force-directed layout in-place (modifies node x,y)."""
    n = len(nodes)
    if n == 0:
        return
    
    area = width * height
    k = math.sqrt(area / n)  # Optimal distance
    
    # Initialize random positions
    for node in nodes:
        node.x = random.uniform(50, width - 50)
        node.y = random.uniform(50, height - 50)
    
    # Build adjacency map
    adj = defaultdict(set)
    edge_lookup = {}
    for e in edges:
        adj[e.source].add(e.target)
        adj[e.target].add(e.source)
        edge_lookup[(e.source, e.target)] = e
        edge_lookup[(e.target, e.source)] = e
    
    # Node lookup
    node_map = {n.id: n for n in nodes}
    
    temperature = width / 10
    
    for _ in range(iterations):
        # Reset forces
        for node in nodes:
            node.vx = 0.0
            node.vy = 0.0
        
        # Repulsive forces (all pairs)
        for i in range(n):
            for j in range(i + 1, n):
                dx = nodes[i].x - nodes[j].x
                dy = nodes[i].y - nodes[j].y
                dist = math.sqrt(dx * dx + dy * dy) or 1.0
                force = k * k / dist
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                nodes[i].vx += fx
                nodes[i].vy += fy
                nodes[j].vx -= fx
                nodes[j].vy -= fy
        
        # Attractive forces (edges)
        for e in edges:
            src = node_map.get(e.source)
            tgt = node_map.get(e.target)
            if not src or not tgt:
                continue
            dx = src.x - tgt.x
            dy = src.y - tgt.y
            dist = math.sqrt(dx * dx + dy * dy) or 1.0
            force = dist * dist / k
            fx = (dx / dist) * force
            fy = (dy / dist) * force
            src.vx -= fx
            src.vy -= fy
            tgt.vx += fx
            tgt.vy += fy
        
        # Apply forces with temperature cooling
        temperature *= 0.95
        for node in nodes:
            vmag = math.sqrt(node.vx * node.vx + node.vy * node.vy)
            if vmag > temperature:
                node.vx = (node.vx / vmag) * temperature
                node.vy = (node.vy / vmag) * temperature
            node.x += node.vx
            node.y += node.vy
            # Clamp to viewport
            node.x = max(30, min(width - 30, node.x))
            node.y = max(30, min(height - 30, node.y))


# ── Entity Type Classification ───────────────────────────────────────────────

def _classify_entity(name: str, all_entities: dict) -> str:
    """Classify an entity as CHARACTER, LOCATION, ORGANIZATION, etc."""
    name_lower = name.lower()
    
    location_keywords = {'city', 'town', 'village', 'island', 'mountain', 'river',
                         'forest', 'castle', 'palace', 'house', 'room', 'street',
                         'road', 'kingdom', 'empire', 'land', 'country', 'world',
                         'sea', 'ocean', 'lake', 'desert', 'valley', 'cave', 'tower'}
    org_keywords = {'company', 'corporation', 'guild', 'army', 'navy', 'police',
                    'government', 'council', 'order', 'society', 'clan', 'tribe',
                    'family', 'house', 'agency', 'bureau', 'department'}
    event_keywords = {'war', 'battle', 'ceremony', 'wedding', 'funeral', 'festival',
                      'meeting', 'conference', 'revolution', 'coronation', 'feast'}
    concept_keywords = {'magic', 'power', 'prophecy', 'curse', 'legend', 'myth',
                        'religion', 'faith', 'science', 'technology', 'law', 'rule'}
    item_keywords = {'sword', 'ring', 'book', 'amulet', 'crown', 'stone', 'gem',
                     'weapon', 'armor', 'potion', 'scroll', 'map', 'key', 'amulet',
                     'staff', 'wand', 'orb', 'blade', 'shield', 'bow', 'arrow', 'dagger'}
    
    tokens = set(name_lower.split())
    tokens.update(name_lower.replace('-', ' ').replace('_', ' ').split())
    
    for token in tokens:
        if token in location_keywords:
            return "LOCATION"
        if token in org_keywords:
            return "ORGANIZATION"
        if token in event_keywords:
            return "EVENT"
        if token in item_keywords:
            return "ITEM"
        if token in concept_keywords:
            return "CONCEPT"
    
    # Default: proper names are CHARACTERS, descriptors are CONCEPTS
    if name[0].isupper() and len(name.split()) <= 3:
        return "CHARACTER"
    return "CONCEPT"


# ── Relationship Type Classification ─────────────────────────────────────────

def _classify_relation(connection_type: str, description: str = "") -> str:
    """Normalize relationship type into standard categories."""
    t = connection_type.lower().strip()
    d = description.lower() if description else ""
    
    if any(w in t for w in ('oppos', 'enemy', 'rival', 'conflict', 'fight', 'battle', 'versus')):
        return "opposes"
    if any(w in t for w in ('alliance', 'ally', 'friend', 'marriage', 'family', 'love', 'loyal')):
        return "allied_with"
    if any(w in t for w in ('transfer', 'give', 'receive', 'trade', 'object_transfer')):
        return "object_transfer"
    if any(w in t for w in ('influence', 'control', 'manipulate', 'command', 'lead')):
        return "influences"
    if any(w in t for w in ('mention', 'reference', 'quote', 'speak of')):
        return "mentions"
    if any(w in t for w in ('meet', 'encounter', 'visit', 'see', 'greet')):
        return "interacts_with"
    
    # Fallback: check description
    if 'fight' in d or 'kill' in d or 'attack' in d:
        return "opposes"
    if 'friend' in d or 'ally' in d or 'love' in d:
        return "allied_with"
    
    return "interacts_with"


# ── Main Graph Builder ───────────────────────────────────────────────────────

def build_relationship_graph(project_dir: str, prefix: str) -> dict:
    """Build a relationship graph from all micro_facts in a project.
    
    Returns dict with keys: nodes, edges, stats, svg_path, gexf_path, json_path
    """
    mf_dir = os.path.join(project_dir, "micro_facts")
    if not os.path.isdir(mf_dir):
        mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
    
    if not os.path.isdir(mf_dir):
        raise FileNotFoundError(
            f"No micro_facts directory found at {mf_dir}. "
            f"Run Phase 4 (merge) before Phase 1.2 (relationship graph)."
        )
    
    pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
    mf_files = sorted(glob.glob(pattern))
    
    if not mf_files:
        raise FileNotFoundError(f"No micro_facts files found matching {pattern}")
    
    # Collect all entities and connections
    all_characters = set()
    all_connections = []
    entity_appearances = defaultdict(set)  # entity -> {chapters}
    entity_weight = Counter()  # entity -> interaction count
    
    for fpath in mf_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        chapter_id = data.get("chapter_id", "?")
        
        # Characters
        for char in data.get("characters_present", []):
            if char and isinstance(char, str):
                all_characters.add(char)
                entity_appearances[char].add(chapter_id)
                entity_weight[char] += 1
        
        # Locations from scenes
        for scene in data.get("scene_details", []):
            loc = scene.get("location", "")
            if loc and isinstance(loc, str) and loc not in ("Unknown Location", "unknown", ""):
                entity_appearances[loc].add(chapter_id)
                entity_weight[loc] += 1
        
        # Cross-chapter connections
        for conn in data.get("cross_chapter_connections", []):
            from_e = conn.get("from_entity", "")
            to_e = conn.get("to_entity", "")
            if from_e and to_e:
                all_connections.append({
                    "source": from_e,
                    "target": to_e,
                    "type": conn.get("connection_type", "interacts_with"),
                    "description": conn.get("description", ""),
                    "chapter": chapter_id,
                })
                entity_weight[from_e] += 1
                entity_weight[to_e] += 1
        
        # Character behaviors → implicit interactions
        for beh in data.get("character_behaviors", []):
            char = beh.get("character", "")
            if char:
                entity_weight[char] += 1
    
    # Build nodes
    nodes = []
    node_ids = set()
    all_entities = {e: {"weight": entity_weight.get(e, 0)} for e in entity_weight}
    
    for entity_name, info in all_entities.items():
        etype = _classify_entity(entity_name, all_entities)
        node = GraphNode(
            id=entity_name,
            label=entity_name,
            entity_type=etype,
            weight=info["weight"],
            chapters=sorted(entity_appearances.get(entity_name, set()))
        )
        nodes.append(node)
        node_ids.add(entity_name)
    
    # Aggregate edges (merge multiple occurrences of same pair)
    edge_aggregator = {}  # (source, target) -> {type, weight, evidence}
    for conn in all_connections:
        src, tgt = conn["source"], conn["target"]
        if src not in node_ids or tgt not in node_ids:
            # Add missing nodes on the fly
            if src not in node_ids:
                nodes.append(GraphNode(id=src, label=src, entity_type=_classify_entity(src, all_entities)))
                node_ids.add(src)
            if tgt not in node_ids:
                nodes.append(GraphNode(id=tgt, label=tgt, entity_type=_classify_entity(tgt, all_entities)))
                node_ids.add(tgt)
        
        key = tuple(sorted([src, tgt]))
        if key not in edge_aggregator:
            edge_aggregator[key] = {
                "source": key[0],
                "target": key[1],
                "type": conn["type"],
                "weight": 0,
                "evidence": []
            }
        edge_aggregator[key]["weight"] += 1
        desc = conn.get("description", "")
        if desc and desc not in edge_aggregator[key]["evidence"]:
            edge_aggregator[key]["evidence"].append(desc)
    
    edges = []
    for key, agg in edge_aggregator.items():
        rel_type = _classify_relation(agg["type"])
        edges.append(GraphEdge(
            source=agg["source"],
            target=agg["target"],
            relation_type=rel_type,
            weight=agg["weight"],
            evidence=agg["evidence"][:3]  # Keep top 3 evidence items
        ))
    
    # Run force layout
    _force_layout(nodes, edges)
    
    # Compute stats
    entity_type_counts = Counter(n.entity_type for n in nodes)
    relation_type_counts = Counter(e.relation_type for e in edges)
    
    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "entity_types": dict(entity_type_counts),
        "relation_types": dict(relation_type_counts),
        "project_prefix": prefix,
    }
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": stats,
    }


# ── SVG Renderer ─────────────────────────────────────────────────────────────

def _render_svg(nodes: List[GraphNode], edges: List[GraphEdge],
                width: int = 1200, height: int = 900) -> str:
    """Render a dark-theme force-directed graph as an SVG string."""
    
    # Color palette by entity type
    type_colors = {
        "CHARACTER":     "#e8a838",  # Gold
        "LOCATION":      "#4a9eff",  # Blue
        "ORGANIZATION":  "#ff6b6b",  # Red
        "EVENT":         "#a855f7",  # Purple
        "CONCEPT":       "#34d399",  # Green
        "ITEM":          "#f472b6",  # Pink
    }
    # Edge colors by relation type
    relation_colors = {
        "interacts_with":   "rgba(255,255,255,0.25)",
        "opposes":          "rgba(255,107,107,0.45)",
        "allied_with":      "rgba(52,211,153,0.40)",
        "influences":       "rgba(168,85,247,0.40)",
        "mentions":         "rgba(255,255,255,0.15)",
        "object_transfer":  "rgba(244,114,182,0.35)",
    }
    
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
        f'<rect width="100%" height="100%" fill="#1a1a2e"/>',
        f'<text x="20" y="30" fill="#888" font-family="monospace" font-size="12">'
        f'MennzLore Relationship Graph</text>',
    ]
    
    # Draw edges first (behind nodes)
    for e in edges:
        src = next((n for n in nodes if n.id == e.source), None)
        tgt = next((n for n in nodes if n.id == e.target), None)
        if not src or not tgt:
            continue
        color = relation_colors.get(e.relation_type, "rgba(255,255,255,0.2)")
        stroke_w = max(1, min(5, math.log2(e.weight + 1)))
        svg_parts.append(
            f'<line x1="{src.x:.1f}" y1="{src.y:.1f}" x2="{tgt.x:.1f}" y2="{tgt.y:.1f}" '
            f'stroke="{color}" stroke-width="{stroke_w:.1f}" opacity="0.7"/>'
        )
    
    # Draw nodes
    for node in nodes:
        color = type_colors.get(node.entity_type, "#ccc")
        radius = max(8, min(40, 5 + node.weight * 1.5))
        opacity = min(1.0, 0.5 + node.weight * 0.02)
        
        # Node circle
        svg_parts.append(
            f'<circle cx="{node.x:.1f}" cy="{node.y:.1f}" r="{radius:.1f}" '
            f'fill="{color}" opacity="{opacity:.2f}" stroke="{color}" stroke-width="1.5"/>'
        )
        
        # Node label
        font_size = max(8, min(13, radius * 0.55))
        label = node.label[:20] + ("…" if len(node.label) > 20 else "")
        svg_parts.append(
            f'<text x="{node.x:.1f}" y="{node.y + radius + font_size + 3:.1f}" '
            f'text-anchor="middle" fill="#ddd" font-family="sans-serif" '
            f'font-size="{font_size:.0f}">{label}</text>'
        )
    
    # Legend
    legend_x = width - 160
    legend_y = 60
    svg_parts.append(
        f'<rect x="{legend_x - 10}" y="{legend_y - 20}" width="160" height="140" '
        f'fill="rgba(0,0,0,0.6)" rx="5"/>'
    )
    svg_parts.append(
        f'<text x="{legend_x}" y="{legend_y}" fill="#aaa" font-family="monospace" font-size="11">'
        f'Legend</text>'
    )
    for i, (etype, color) in enumerate(type_colors.items()):
        ly = legend_y + 15 + i * 16
        svg_parts.append(
            f'<circle cx="{legend_x + 5}" cy="{ly}" r="5" fill="{color}"/>'
            f'<text x="{legend_x + 15}" y="{ly + 4}" fill="#ccc" font-family="sans-serif" '
            f'font-size="10">{etype}</text>'
        )
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


# ── GEXF Exporter ────────────────────────────────────────────────────────────

def _render_gexf(nodes: List[GraphNode], edges: List[GraphEdge]) -> str:
    """Export graph as GEXF (Gephi-compatible XML format)."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gexf xmlns="http://www.gexf.net/1.3" version="1.3">',
        '<graph mode="static" defaultedgetype="undirected">',
    ]
    
    # Node attributes
    lines.append('<attributes class="node">')
    lines.append('  <attribute id="0" title="entity_type" type="string"/>')
    lines.append('  <attribute id="1" title="weight" type="integer"/>')
    lines.append('</attributes>')
    
    # Edge attributes
    lines.append('<attributes class="edge">')
    lines.append('  <attribute id="0" title="relation_type" type="string"/>')
    lines.append('  <attribute id="1" title="weight" type="integer"/>')
    lines.append('</attributes>')
    
    # Nodes
    lines.append('<nodes>')
    for i, node in enumerate(nodes):
        label_escaped = node.label.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        lines.append(
            f'  <node id="{i}" label="{label_escaped}">'
            f'<attvalues><attvalue for="0" value="{node.entity_type}"/>'
            f'<attvalue for="1" value="{node.weight}"/></attvalues>'
            f'</node>'
        )
    lines.append('</nodes>')
    
    # Build id lookup
    id_map = {n.id: i for i, n in enumerate(nodes)}
    
    # Edges
    lines.append('<edges>')
    edge_id = 0
    for e in edges:
        src_id = id_map.get(e.source)
        tgt_id = id_map.get(e.target)
        if src_id is None or tgt_id is None:
            continue
        lines.append(
            f'  <edge id="{edge_id}" source="{src_id}" target="{tgt_id}">'
            f'<attvalues><attvalue for="0" value="{e.relation_type}"/>'
            f'<attvalue for="1" value="{e.weight}"/></attvalues>'
            f'</edge>'
        )
        edge_id += 1
    lines.append('</edges>')
    
    lines.append('</graph>')
    lines.append('</gexf>')
    return '\n'.join(lines)


# ── Public API ───────────────────────────────────────────────────────────────

def render_relationships(project_dir: str, prefix: str = "",
                         output_dir: str | None = None) -> dict:
    """Build relationship graph and write SVG, GEXF, and JSON outputs.
    
    Args:
        project_dir: Path to project directory containing micro_facts/
        prefix: Project prefix (auto-detected if empty)
        output_dir: Output directory (default: project_dir/output/relationships/)
    
    Returns:
        dict with paths and stats
    """
    if not prefix:
        prefix = os.path.basename(project_dir.rstrip("/\\"))
    
    if output_dir is None:
        output_dir = os.path.join(project_dir, "output", "relationships")
    
    # Build graph
    result = build_relationship_graph(project_dir, prefix)
    nodes = result["nodes"]
    edges = result["edges"]
    stats = result["stats"]
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Render SVG
    svg_content = _render_svg(nodes, edges)
    svg_path = os.path.join(output_dir, f"{prefix}_relationship_graph.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    
    # Render GEXF
    gexf_content = _render_gexf(nodes, edges)
    gexf_path = os.path.join(output_dir, f"{prefix}_network.gexf")
    with open(gexf_path, "w", encoding="utf-8") as f:
        f.write(gexf_content)
    
    # Write JSON data
    json_data = {
        "project_prefix": prefix,
        "stats": stats,
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "entity_type": n.entity_type,
                "weight": n.weight,
                "chapters": n.chapters,
            }
            for n in nodes
        ],
        "edges": [
            {
                "source": e.source,
                "target": e.target,
                "relation_type": e.relation_type,
                "weight": e.weight,
                "evidence": e.evidence,
            }
            for e in edges
        ],
    }
    json_path = os.path.join(output_dir, f"{prefix}_relationship_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    return {
        "status": "success",
        "svg_path": svg_path,
        "gexf_path": gexf_path,
        "json_path": json_path,
        "stats": stats,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python relationship_graph.py <project_dir> [prefix]")
        sys.exit(1)
    
    proj = sys.argv[1]
    pfx = sys.argv[2] if len(sys.argv) > 2 else ""
    
    result = render_relationships(proj, pfx)
    if result["status"] == "success":
        print(f"[OK] Relationship graph rendered:")
        print(f"     SVG:  {result['svg_path']}")
        print(f"     GEXF: {result['gexf_path']}")
        print(f"     JSON: {result['json_path']}")
        print(f"     Nodes: {result['stats']['total_nodes']} | Edges: {result['stats']['total_edges']}")
        print(f"     Entity types: {result['stats']['entity_types']}")
        print(f"     Relation types: {result['stats']['relation_types']}")
    else:
        print(f"[ERROR] {result.get('message', 'Unknown error')}")
