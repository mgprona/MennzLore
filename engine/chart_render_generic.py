#!/usr/bin/env python3
"""
Phase 10 — Chart Render (GENERIC v1.0)
=======================================
Processes spatial location data, determines geography, calculates character 
travel routes, and renders the fictional/real-world map skeleton as an SVG.
"""
import json
import os
import glob
import re
import sys
import math
import random
from xml.sax.saxutils import escape as xml_escape

try:
    from engine.utils import normalize_location, load_json, write_json
except ImportError:
    from utils import normalize_location, load_json, write_json

# Optional real-world gazetteer (loaded from <prefix>_gazetteer.json if present).
# For fictional/alien settings this stays empty → everything is fantasy-placed.
# Also automatically loads the built-in world_gazetteer.json from data/ for
# real-world location resolution without external API calls.
KNOWN_COORDS = {}

# ── Built-in world gazetteer (Fix: no external API needed) ──────────────────
_GAZETTEER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
_GAZETTEER_PATH = os.path.join(_GAZETTEER_DIR, "world_gazetteer.json")
if os.path.exists(_GAZETTEER_PATH):
    try:
        with open(_GAZETTEER_PATH, encoding="utf-8") as _f:
            _gaz = json.load(_f)
        for _k, _v in _gaz.items():
            if _k == "metadata":
                continue
            if isinstance(_v, list) and len(_v) >= 3:
                KNOWN_COORDS[_k.lower().strip()] = tuple(_v[:3])
        print(f"  [Gazetteer] Built-in world gazetteer loaded: {len(KNOWN_COORDS)} entries")
        _meta = _gaz.get("metadata", {})
        _version = _meta.get("version", "?")
        _entries = _meta.get("entries", len(KNOWN_COORDS))
        print(f"  [Gazetteer] v{_version} — {_entries} locations covering "
              f"{len(set(v[2] for v in KNOWN_COORDS.values() if len(v) > 2 and isinstance(v[2], str)))} countries")
    except Exception as _e:
        print(f"  [Gazetteer] Warning: built-in gazetteer load failed: {_e}")

FANTASY_ZONES = {
    "mountain_peak": {"x": (0.25, 0.75), "y": (0.05, 0.30)},
    "river_cliff": {"x": (0.20, 0.80), "y": (0.25, 0.50)},
    "coastal": {"x": (0.10, 0.60), "y": (0.55, 0.85)},
    "marsh_hills": {"x": (0.20, 0.60), "y": (0.35, 0.65)},
    "settlement": {"x": (0.25, 0.75), "y": (0.40, 0.75)},
    "forest": {"x": (0.15, 0.55), "y": (0.30, 0.60)},
    "farmland_valley": {"x": (0.30, 0.70), "y": (0.45, 0.70)},
    "underground": {"x": (0.30, 0.70), "y": (0.55, 0.80)},
    "default": {"x": (0.15, 0.85), "y": (0.15, 0.85)},
}

def resolve_location(name):
    n = re.sub(r'^the\s+', '', name.strip().lower())
    n = normalize_location(n)
    n = re.sub(r'\s*[--/].*$', '', n).strip()
    # Try full name first (before stripping suffixes)
    if n in KNOWN_COORDS:
        return KNOWN_COORDS[n]
    # Now strip residential suffixes and try again
    stripped = re.sub(r'\s+(?:house|street|road|square|avenue|lane|rooms|apartment)\s*$', '', n).strip()
    if stripped in KNOWN_COORDS:
        return KNOWN_COORDS[stripped]
    if stripped != n:
        n = stripped
    for w in sorted(n.split(), key=len, reverse=True):
        if len(w) > 3 and w.lower() in KNOWN_COORDS:
            return KNOWN_COORDS[w.lower()]
    return None

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def to_nm(km): 
    return km / 1.852

def latlon_to_xy(lat, lon, clat, clon, scale, W, H):
    cos_cl = math.cos(math.radians(clat))
    return (int(W/2 + (lon-clon) * cos_cl * scale), int(H/2 + (clat-lat) * scale))

def on_canvas(x, y, W, H, margin=60):
    return margin <= x <= W-margin and margin <= y <= H-margin

def terrain_from_name(name):
    n = name.lower()
    if any(w in n for w in ["mountain","peak","hill","mount","slope","ledge","cliff","spire","rock"]): 
        return "mountain_peak"
    if any(w in n for w in ["river","stream","water","lake","falls","crater lake"]): 
        return "river_cliff"
    if any(w in n for w in ["forest","wood","grove","tree","jungle"]): 
        return "forest"
    if any(w in n for w in ["sea","coast","ocean","bay","island","shore","beach","reed","mud flat"]): 
        return "coastal"
    if any(w in n for w in ["town","village","city","keep","castle","hall","temple","house","street","road","square","lane","palace","fortress","camp","spaceport","cabin","armory","terrace","parapet"]): 
        return "settlement"
    if any(w in n for w in ["valley","field","plain","meadow"]): 
        return "farmland_valley"
    if any(w in n for w in ["marsh","swamp","bog","fen","bogland"]): 
        return "marsh_hills"
    if any(w in n for w in ["cave","cavern","mine"]): 
        return "underground"
    return "default"

def generate_svg(meta, locations, routes):
    W, H = 1000, 700
    clat, clon = meta["center"]
    scale = meta["scale"]
    novel = meta.get("novel", "Unknown")
    author = meta.get("author", "Unknown")
    coord_ratio = meta.get("coord_ratio", 0.0)
    n_real = meta.get("n_real", 0)
    n_total = meta.get("n_total", 0)
    svg = []
    
    def a(s): 
        svg.append(s)
        
    a('<?xml version="1.0" encoding="UTF-8"?>')
    a('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" width="100%" height="100%">')
    a('  <metadata>')
    a('    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:map="https://hermes-agent.nousresearch.com/chart-render/v3.1">')
    a('      <rdf:Description rdf:about="">')
    a('        <dc:title>' + xml_escape(novel) + ' — Map Skeleton</dc:title>')
    a('        <dc:creator>' + xml_escape(author) + '</dc:creator>')
    a('        <dc:description>Map skeleton derived from lore extraction.</dc:description>')
    a('        <map:version>generic-1.0</map:version>')
    a('        <map:coord-coverage>' + str(round(coord_ratio, 2)) + '</map:coord-coverage>')
    a('        <map:coord-real>' + str(n_real) + '</map:coord-real>')
    a('        <map:coord-total>' + str(n_total) + '</map:coord-total>')
    a('        <map:projection>equirectangular</map:projection>')
    a('        <map:center-lat>' + str(clat) + '</map:center-lat>')
    a('        <map:center-lon>' + str(clon) + '</map:center-lon>')
    a('        <map:locations>')
    for name, loc in sorted(locations.items()):
        c = loc.get("coordinates")
        if c:
            a('          <map:location id="' + loc.get("id","?") + '" name="' + xml_escape(name) + '" lat="' + str(c[0]) + '" lon="' + str(c[1]) + '" type="' + loc.get("location_type","?") + '" terrain="' + loc.get("terrain","?") + '"/>')
    a('        </map:locations>')
    a('        <map:routes>')
    for r in routes:
        a('          <map:route from="' + xml_escape(r["from"]) + '" to="' + xml_escape(r["to"]) + '" distance-nm="' + str(r["distance_nm"]) + '" method="' + r.get("method","?") + '"/>')
    a('        </map:routes>')
    a('      </rdf:Description>')
    a('    </rdf:RDF>')
    a('  </metadata>')
    a('''  <defs><style>
      .bg-water     { fill: #d0e4f2; }
      .coast-fill   { fill: #e8dcc8; stroke: #5a4a3a; stroke-width: 1.5; }
      .sandbank     { fill: #f0d8a8; stroke: #c4a060; stroke-width: 0.8; }
      .graticule    { fill: none; stroke: #c0d0e0; stroke-width: 0.5; opacity: 0.5; }
      .grid-label   { font: 8px sans-serif; fill: #6a7a8a; }
      .route        { fill: none; stroke: #8b3a3a; stroke-width: 1.5; stroke-dasharray: 6,4; }
      .route-label  { font: 8px sans-serif; fill: #5a3a2a; }
      .loc-name     { font: bold 11px sans-serif; fill: #1a1a2a; text-anchor: middle; }
      .loc-type     { font: italic 8px sans-serif; fill: #6a6a7a; text-anchor: middle; }
      .title        { font: bold 22px Georgia,serif; fill: #1a1a2a; }
      .subtitle     { font: 11px Georgia,serif; fill: #5a5a6a; }
      .compass      { font: bold 14px Georgia,serif; fill: #1a1a2a; }
      .legend       { font: 9px sans-serif; fill: #1a1a2a; }
      .legend-title { font: bold 10px sans-serif; fill: #1a1a2a; }
    </style><clipPath id="clip"><rect x="0" y="0" width="1000" height="700"/></clipPath></defs>''')
    a('  <rect class="bg-water" width="1000" height="700"/>')
    a('  <g id="geo" clip-path="url(#clip)">')
    a('    <g id="title-block">')
    a('      <rect x="200" y="20" width="600" height="50" rx="3" fill="#f5f0e8" stroke="#5a4a3a" stroke-width="1" opacity="0.9"/>')
    a('      <text class="title" x="500" y="40" text-anchor="middle">' + xml_escape(novel) + '</text>')
    a('      <text class="subtitle" x="500" y="58" text-anchor="middle">by ' + xml_escape(author) + '  |  Lore-derived map  |  ' + str(n_real) + '/' + str(n_total) + ' coords</text>')
    a('    </g>')
    a('    <g id="locations">')
    placed = {}
    for name, loc in sorted(locations.items()):
        coords = loc.get("coordinates")
        canvas_pos = loc.get("canvas_pos")
        if canvas_pos: 
            x, y = canvas_pos
        elif coords: 
            x, y = latlon_to_xy(coords[0], coords[1], clat, clon, scale, W, H)
        else: 
            continue
        if not on_canvas(x, y, W, H): 
            continue
        placed[name] = (x, y)
        lid = loc.get("id", "?")
        terrain = loc.get("terrain", "?")
        a('      <g id="' + lid + '" data-name="' + xml_escape(name) + '" data-terrain="' + terrain + '">')
        a('        <circle cx="' + str(x) + '" cy="' + str(y) + '" r="5" fill="#5a4a3a" stroke="#1a1a2a" stroke-width="1"/>')
        a('        <text class="loc-name" x="' + str(x) + '" y="' + str(y-12) + '">' + xml_escape(name[:24]) + '</text>')
        a('        <text class="loc-type" x="' + str(x) + '" y="' + str(y+14) + '">' + xml_escape(terrain.replace("_"," ")) + '</text>')
        a('      </g>')
    a('    </g>')
    a('    <g id="routes">')
    drawn = set()
    for r in routes[:20]:
        frm, to = r["from"], r["to"]
        if frm not in placed or to not in placed: 
            continue
        key = tuple(sorted([frm, to]))
        if key in drawn: 
            continue
        drawn.add(key)
        x1, y1 = placed[frm]
        x2, y2 = placed[to]
        mx, my = (x1+x2)//2, (y1+y2)//2
        a('      <g data-from="' + xml_escape(frm) + '" data-to="' + xml_escape(to) + '" data-distance-nm="' + str(r["distance_nm"]) + '">')
        a('        <line class="route" x1="' + str(x1) + '" y1="' + str(y1) + '" x2="' + str(x2) + '" y2="' + str(y2) + '"/>')
        lbl = str(round(r["distance_nm"])) + " nm / " + r.get("method","?")
        a('        <text class="route-label" x="' + str(mx) + '" y="' + str(my-8) + '" text-anchor="middle">' + lbl + '</text>')
        a('      </g>')
    a('    </g>')
    a('  </g><!-- /geo -->')
    a('''    <g id="compass-rose">
      <circle cx="880" cy="130" r="32" fill="none" stroke="#3a3a4a" stroke-width="1.5"/>
      <circle cx="880" cy="130" r="28" fill="none" stroke="#3a3a4a" stroke-width="0.5"/>
      <polygon points="880,100 874,120 886,120" fill="#1a1a2a"/>
      <polygon points="880,160 874,140 886,140" fill="#8a8a9a"/>
      <polygon points="910,130 890,125 890,135" fill="#8a8a9a"/>
      <polygon points="850,130 870,125 870,135" fill="#8a8a9a"/>
      <text class="compass" x="880" y="95" text-anchor="middle">N</text>
      <text class="compass" x="880" y="172" text-anchor="middle" font-size="11">S</text>
      <text class="compass" x="918" y="134" text-anchor="middle" font-size="11">E</text>
      <text class="compass" x="842" y="134" text-anchor="middle" font-size="11">W</text>
    </g>''')
    ly = H - 145
    a('    <g id="legend">')
    a('      <rect x="25" y="' + str(ly) + '" width="175" height="95" rx="3" fill="#f5f0e8" stroke="#5a4a3a" stroke-width="1" opacity="0.9"/>')
    a('      <text class="legend-title" x="33" y="' + str(ly+16) + '">LEGEND</text>')
    a('      <line class="route" x1="33" y1="' + str(ly+30) + '" x2="50" y2="' + str(ly+30) + '"/>')
    a('      <text class="legend" x="55" y="' + str(ly+33) + '">Travel Route</text>')
    a('      <circle cx="40" cy="' + str(ly+48) + '" r="4" fill="#5a4a3a" stroke="#1a1a2a" stroke-width="1"/>')
    a('      <text class="legend" x="55" y="' + str(ly+51) + '">Location</text>')
    a('    </g>')
    a('    <g id="chart-notes">')
    a('      <text class="route-label" font-size="7" font-style="italic">')
    a('        <tspan x="700" y="' + str(H-50) + '">MAP SKELETON generic-1.0</tspan>')
    a('        <tspan x="700" dy="12">Coord coverage: ' + str(round(coord_ratio*100)) + '%</tspan>')
    a('        <tspan x="700" dy="12">Feed to vision AI for styling</tspan>')
    a('      </text>')
    a('    </g>')
    a('</svg>')
    return "\n".join(svg)

def build_chart(project_dir, prefix):
    print("  --- Chart Render (generic v1.0) ---")
    output_dir = os.path.join(project_dir, "output", "spatial")
    os.makedirs(output_dir, exist_ok=True)
    verification = os.path.join(project_dir, "verification")

    # title/author from global_lore
    novel_name = prefix.replace("-", " ").title()
    author = "Unknown"
    gl_path = os.path.join(verification, f"{prefix}_global_lore.json")
    if os.path.exists(gl_path):
        with open(gl_path, encoding="utf-8") as f:
            md = json.load(f).get("book_metadata", {})
        novel_name = md.get("title", novel_name)
        author = md.get("author", author)

    # optional gazetteer for real-world settings
    gaz_path = os.path.join(verification, f"{prefix}_gazetteer.json")
    if os.path.exists(gaz_path):
        with open(gaz_path, encoding="utf-8") as f:
            for k, v in json.load(f).items():
                KNOWN_COORDS[k.lower()] = tuple(v)
        print(f"  Gazetteer loaded: {len(KNOWN_COORDS)} known coords")

    mf_dir = os.path.join(project_dir, "micro_facts")
    if not os.path.isdir(mf_dir):
        mf_dir = os.path.join(project_dir, "analysis", "micro_facts")

    locations = {}
    loc_id = 0
    for f in sorted(glob.glob(os.path.join(mf_dir, prefix + "_EP*_micro_facts.json"))):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        for s in data.get("scene_details", []):
            if isinstance(s, dict):
                raw = s.get("location", "")
                if raw:
                    norm = normalize_location(raw)
                    if len(norm) > 1 and norm not in locations:
                        locations[norm] = {"id": f"loc_{loc_id:03d}", "episodes": []}
                        loc_id += 1
                    if norm in locations:
                        ep = data.get("chapter_id", "")
                        if ep and ep not in locations[norm]["episodes"]:
                            locations[norm]["episodes"].append(ep)
    print("  Locations: " + str(len(locations)) + " from micro_facts")

    geo_data = {}
    real_n, fantasy_n = 0, 0
    for canonical in sorted(locations.keys()):
        result = resolve_location(canonical)
        terrain = terrain_from_name(canonical)
        if result:
            lat, lon, loc_type, country = result
            real_n += 1
            geo_data[canonical] = {
                "id": locations[canonical]["id"], "coordinates": [lat, lon],
                "terrain": terrain, "location_type": loc_type, "country": country,
                "coordinate_source": "real", "mentioned_in_eps": locations[canonical]["episodes"]}
        else:
            fantasy_n += 1
            geo_data[canonical] = {
                "id": locations[canonical]["id"], "coordinates": None,
                "terrain": terrain, "location_type": "fantasy", "country": "",
                "coordinate_source": "fantasy", "mentioned_in_eps": locations[canonical]["episodes"]}
    total = len(geo_data)
    coord_ratio = real_n / total if total else 0
    print(f"  Real: {real_n}/{total}, Fantasy: {fantasy_n}/{total}, Coverage: {coord_ratio*100:.0f}%")

    placed_f = {}
    for name, loc in sorted(geo_data.items()):
        if loc.get("coordinates"): 
            continue
        t = loc.get("terrain", "default")
        zone = FANTASY_ZONES.get(t, FANTASY_ZONES["default"])
        for _ in range(100):
            x = random.randint(int(zone["x"][0]*1000), int(zone["x"][1]*1000))
            y = random.randint(int(zone["y"][0]*700), int(zone["y"][1]*700))
            if all(math.sqrt((x-px)**2 + (y-py)**2) >= 65 for px, py in placed_f.values()):
                placed_f[name] = (x, y)
                break
        if name not in placed_f:
            placed_f[name] = (random.randint(80, 920), random.randint(80, 620))
        geo_data[name]["canvas_pos"] = list(placed_f[name])

    routes = []
    eps_ordered = []
    for f in sorted(glob.glob(os.path.join(mf_dir, prefix + "_EP*_micro_facts.json"))):
        ep = os.path.basename(f).split("_EP")[1].split("_")[0]
        eps_ordered.append(ep)
    prev_locs = []
    for ep in eps_ordered:
        cands = glob.glob(os.path.join(mf_dir, f"{prefix}_EP{ep}_micro_facts.json"))
        if not cands: 
            continue
        with open(cands[0], encoding="utf-8") as fh:
            data = json.load(fh)
        current = []
        for s in data.get("scene_details", []):
            if isinstance(s, dict):
                raw = s.get("location", "")
                if raw:
                    norm = normalize_location(raw)
                    if norm in geo_data:
                        current.append(norm)
        if prev_locs and current:
            for pl in prev_locs:
                for cl in current:
                    if pl != cl and pl in geo_data and cl in geo_data:
                        ca = geo_data[pl].get("coordinates")
                        cb = geo_data[cl].get("coordinates")
                        if ca and cb:
                            km = haversine_km(ca[0], ca[1], cb[0], cb[1])
                            d_nm = round(to_nm(km), 1)
                            method = "walk" if d_nm < 10 else "travel"
                        else:
                            pa = geo_data[pl].get("canvas_pos")
                            pb = geo_data[cl].get("canvas_pos")
                            if pa and pb:
                                px = math.sqrt((pa[0]-pb[0])**2 + (pa[1]-pb[1])**2)
                                d_nm = round(px / 10, 1)
                            else:
                                d_nm = round(random.uniform(1, 8), 1)
                            method = "trek"
                        routes.append({"from": pl, "to": cl, "method": method, "distance_nm": d_nm})
        prev_locs = current
    routes = routes[:30]

    lats = [v["coordinates"][0] for v in geo_data.values() if v.get("coordinates")]
    lons = [v["coordinates"][1] for v in geo_data.values() if v.get("coordinates")]
    if lats and lons:
        min_lat, max_lat = min(lats)-0.5, max(lats)+0.5
        min_lon, max_lon = min(lons)-0.5, max(lons)+0.5
    else:
        min_lat, max_lat, min_lon, max_lon = 0.0, 10.0, 0.0, 10.0
    clat = (min_lat + max_lat) / 2
    clon = (min_lon + max_lon) / 2
    vis_range = max_lat - min_lat
    scale = (700 - 160) / (vis_range * math.pi / 180) if vis_range > 0 else 700

    meta = {"novel": novel_name, "author": author, "prefix": prefix,
            "center": (clat, clon), "scale": scale,
            "bounds": (min_lat, max_lat, min_lon, max_lon),
            "coord_ratio": coord_ratio, "n_real": real_n, "n_total": total}
    svg = generate_svg(meta, geo_data, routes)

    with open(os.path.join(output_dir, "location_geography.json"), "w", encoding="utf-8") as f:
        json.dump(geo_data, f, ensure_ascii=False, indent=2)
    print("  location_geography.json")
    with open(os.path.join(output_dir, "route_network.json"), "w", encoding="utf-8") as f:
        json.dump({"routes": routes, "total": len(routes)}, f, ensure_ascii=False, indent=2)
    print("  route_network.json")
    with open(os.path.join(output_dir, "chart_map_skeleton.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    print("  chart_map_skeleton.svg")

    # Generate map visual prompts
    loc_names = list(geo_data.keys())
    top_locs = loc_names[:6]
    locs_list_str = ", ".join(top_locs)
    
    map_prompt_midjourney = (
        f"A beautiful fantasy map of the world of '{novel_name}' by {author}. "
        f"Antique cartography style, old aged vintage parchment paper, sepia ink, hand-drawn map. "
        f"Features key locations including: {locs_list_str}. "
        f"Illustrations of mountains, rivers, forests, and old castles. Compass rose at the corner. "
        f"Hand-lettered calligraphic text labels in the style appropriate to the setting, "
        f"ornate border decoration, highly detailed, historical look, masterpiece, --ar 16:9"
    )
    
    map_prompt_stable_diffusion = (
        f"Fantasy map, cartography, hand-drawn map of '{novel_name}', antique style, "
        f"aged yellow parchment, sepia ink illustration, calligraphy labeling {locs_list_str}, "
        f"highly detailed fantasy geography, mountain peaks, rivers, forests, vintage compass rose, "
        f"high resolution, masterpiece."
    )
    
    prompt_data = {
        "project": prefix,
        "novel": novel_name,
        "author": author,
        "locations_included": top_locs,
        "prompt_midjourney": map_prompt_midjourney,
        "prompt_stable_diffusion": map_prompt_stable_diffusion
    }
    
    with open(os.path.join(output_dir, "map_image_prompt.json"), "w", encoding="utf-8") as f:
        json.dump(prompt_data, f, ensure_ascii=False, indent=2)
    print("  map_image_prompt.json")
    
    with open(os.path.join(output_dir, "map_image_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(map_prompt_midjourney)
    print("  map_image_prompt.txt")

    print(f"  Phase 10 complete — {output_dir}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/chart_render_generic.py <project_dir> [prefix]")
        sys.exit(0)
    project_dir = sys.argv[1].rstrip("/\\")
    prefix = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(project_dir)
    build_chart(project_dir, prefix)
