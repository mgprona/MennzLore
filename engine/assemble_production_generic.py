#!/usr/bin/env python3
"""
Phase 9 — Production Render (GENERIC v1.0)
===========================================
Generates cinematography shot lists, scene image prompts, entity registries, 
and visual style bibles for creative production.
"""
import json
import os
import glob
import re
import sys
from datetime import datetime
from collections import defaultdict

try:
    from engine.utils import build_variant_lookup, normalize_name, load_json, write_json
except ImportError:
    from utils import build_variant_lookup, normalize_name, load_json, write_json

try:
    from engine.phase3_global_lore import _unwrap_xml_arrays
except ImportError:
    # Standalone import path (when run as a script)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from phase3_global_lore import _unwrap_xml_arrays

# ─── CONFIG ──────────────────────────────────────────
ASPECT_RATIOS = {"wide": "16:9", "portrait": "9:16", "square": "1:1", "cinematic": "21:9"}

MOOD_TO_CINEMATIC = {
    "tense": {"lighting": "dramatic chiaroscuro", "color_palette": "amber and shadow", "lens": "50mm"},
    "ominous": {"lighting": "low-key with deep shadows", "color_palette": "dark green and black", "lens": "35mm wide"},
    "horror": {"lighting": "single source harsh light", "color_palette": "cold blue-grey", "lens": "24mm distorted"},
    "horrifying": {"lighting": "strobe-like flicker", "color_palette": "pulse red", "lens": "24mm handheld"},
    "nightmarish": {"lighting": "bioluminescent glow", "color_palette": "deep purple and emerald", "lens": "fisheye"},
    "mysterious": {"lighting": "soft diffused", "color_palette": "sepia and fog", "lens": "85mm portrait"},
    "foreboding": {"lighting": "backlit silhouette", "color_palette": "grey-blue monochrome", "lens": "70mm"},
    "clinical": {"lighting": "sterile overhead", "color_palette": "white and steel", "lens": "macro"},
    "chilling": {"lighting": "cold window light", "color_palette": "ice blue and grey", "lens": "50mm"},
    "tragic": {"lighting": "soft funeral", "color_palette": "muted earth tones", "lens": "85mm soft"},
    "gloomy": {"lighting": "overcast diffuse", "color_palette": "slate grey", "lens": "35mm"},
    "introspective": {"lighting": "warm firelight", "color_palette": "amber and crimson", "lens": "50mm"},
    "conversational": {"lighting": "warm fireplace", "color_palette": "amber and crimson", "lens": "85mm portrait"},
    "eerie": {"lighting": "uneven practicals", "color_palette": "faded yellow and black", "lens": "35mm"},
    "grim": {"lighting": "practical lamp", "color_palette": "brown and rust", "lens": "35mm"},
    "dark": {"lighting": "street lamps only", "color_palette": "sodium orange and black", "lens": "50mm"},
    "apocalyptic": {"lighting": "smoke-filtered sun", "color_palette": "burnt orange and charcoal", "lens": "24mm wide"},
    "melancholic": {"lighting": "overcast memorial", "color_palette": "faded indigo and ivory", "lens": "85mm soft"},
    "haunting": {"lighting": "moonlight through curtains", "color_palette": "silver and deep blue", "lens": "70mm"},
    "reflective": {"lighting": "golden hour glow", "color_palette": "warm ochre and soft brown", "lens": "50mm"},
    "scholarly": {"lighting": "library lamp", "color_palette": "warm paper tones", "lens": "50mm macro"},
    "urgent": {"lighting": "harsh noon", "color_palette": "bleached white and red", "lens": "24mm handheld"},
    "creeping": {"lighting": "slow dolly backlight", "color_palette": "fading violet", "lens": "70mm"},
    "oppressive": {"lighting": "low ceiling shadow", "color_palette": "mud brown and grey", "lens": "24mm wide"},
    "shocking": {"lighting": "flash bulb burst", "color_palette": "white blast and black", "lens": "24mm"},
    "grotesque": {"lighting": "surgical spot", "color_palette": "flesh pink and bile green", "lens": "macro distorted"},
    "existential": {"lighting": "void black", "color_palette": "infinite black and faint white", "lens": "infinity"},
    "sordid": {"lighting": "single naked bulb", "color_palette": "urine yellow and brown", "lens": "35mm"},
    "supernatural": {"lighting": "otherworldly glow", "color_palette": "ethereal cyan and violet", "lens": "50mm"},
    "portentous": {"lighting": "storm light", "color_palette": "lead grey and pale yellow", "lens": "35mm"},
    "unease": {"lighting": "slightly off-kilter", "color_palette": "sickly green and grey", "lens": "50mm hinted"},
    "weary": {"lighting": "fading daylight", "color_palette": "dusty ochre and grey", "lens": "50mm"},
    "harrowing": {"lighting": "stark high-contrast", "color_palette": "muddy green and black", "lens": "24mm handheld"},
    "surreal": {"lighting": "shifting dreamlike", "color_palette": "iridescent unnatural hues", "lens": "fisheye"},
    "hypnotic": {"lighting": "pulsing rhythmic", "color_palette": "deep red and firelit gold", "lens": "85mm"},
    "stealthy": {"lighting": "moonlit shadow", "color_palette": "dark teal and black", "lens": "70mm"},
    "adventurous": {"lighting": "bright open sky", "color_palette": "vivid sky blue and earth", "lens": "35mm wide"},
    "dramatic": {"lighting": "dramatic chiaroscuro", "color_palette": "amber and shadow", "lens": "50mm"},
}

MOOD_TO_SHOT = {
    "tense": {"size": "medium", "move": "slow push-in"},
    "ominous": {"size": "wide", "move": "static"},
    "horror": {"size": "close_up", "move": "handheld"},
    "horrifying": {"size": "close_up", "move": "whip pan"},
    "nightmarish": {"size": "extreme_close_up", "move": "dutch_angle"},
    "mysterious": {"size": "medium", "move": "slow pan"},
    "foreboding": {"size": "extreme_wide", "move": "crane down"},
    "clinical": {"size": "close_up", "move": "static"},
    "chilling": {"size": "wide", "move": "slow dolly back"},
    "tragic": {"size": "extreme_wide", "move": "slow push-in"},
    "gloomy": {"size": "wide", "move": "static"},
    "introspective": {"size": "close_up", "move": "slow zoom"},
    "conversational": {"size": "medium", "move": "over-shoulder"},
    "eerie": {"size": "wide", "move": "static"},
    "grim": {"size": "medium", "move": "static"},
    "dark": {"size": "extreme_wide", "move": "tracking"},
    "apocalyptic": {"size": "extreme_wide", "move": "crane up"},
    "melancholic": {"size": "wide", "move": "timelapse"},
    "haunting": {"size": "medium", "move": "slow reveal"},
    "reflective": {"size": "close_up", "move": "slow push-in"},
    "scholarly": {"size": "close_up", "move": "slow zoom"},
    "urgent": {"size": "close_up", "move": "whip pan"},
    "creeping": {"size": "wide", "move": "slow dolly"},
    "oppressive": {"size": "extreme_wide", "move": "static"},
    "shocking": {"size": "extreme_close_up", "move": "snap zoom"},
    "grotesque": {"size": "close_up", "move": "macro crawl"},
    "existential": {"size": "extreme_wide", "move": "infinite pull-back"},
    "sordid": {"size": "medium", "move": "handheld"},
    "supernatural": {"size": "wide", "move": "float"},
    "portentous": {"size": "wide", "move": "slow crane"},
    "unease": {"size": "medium", "move": "slight handheld"},
    "weary": {"size": "medium", "move": "static"},
    "harrowing": {"size": "wide", "move": "handheld"},
    "surreal": {"size": "extreme_close_up", "move": "dutch_angle"},
    "hypnotic": {"size": "close_up", "move": "slow zoom"},
    "stealthy": {"size": "medium", "move": "low tracking"},
    "adventurous": {"size": "extreme_wide", "move": "sweeping crane"},
    "dramatic": {"size": "medium", "move": "slow push-in"},
}


# ─── STYLE INFERENCE ──────────────────────────────────
def infer_art_style(genre_list, title):
    """Infer an art-direction style string from the work's genre."""
    g = " ".join(genre_list).lower() if genre_list else ""
    if any(w in g for w in ["science fiction", "sci-fi", "space", "planetary", "galactic"]):
        return ("retro-futurist pulp science fiction, 1950s space-opera cover art, "
                "painterly gouache illustration, alien wilderness vistas, dramatic cinematic "
                "lighting, vintage sci-fi aesthetic, hyper-detailed, masterpiece")
    if any(w in g for w in ["gothic", "horror", "weird", "cosmic"]):
        return ("Gothic horror, oil painting, dramatic chiaroscuro, pre-Raphaelite composition, "
                "hyper-detailed, dark academic, masterpiece")
    if any(w in g for w in ["fantasy", "myth", "fairy"]):
        return ("high fantasy concept art, painterly, epic dramatic lighting, rich detail, "
                "matte painting, masterpiece")
    if any(w in g for w in ["historical", "period", "victorian", "regency"]):
        return ("period-accurate historical realism, oil painting, naturalistic lighting, "
                "fine detail, masterpiece")
    return ("cinematic concept art, painterly, dramatic lighting, hyper-detailed, masterpiece")


def infer_era_setting(metadata):
    """Build a generic era/setting note from metadata.

    Unwraps any ``{"item": ...}`` array wrappers from ``genre`` before
    processing, since the MCP/JSON-RPC layer sometimes wraps the value
    on the wire. Without this, ``metadata["genre"]`` could be a dict
    (e.g. ``{"item": ["detective fiction", "mystery"]}``) and the slice
    ``[:3]`` would raise ``TypeError: unhashable type: 'slice'`` (Bug #7).
    """
    metadata = _unwrap_xml_arrays(metadata)
    genre_list = _unwrap_xml_arrays(metadata.get("genre", []))
    genre = " ".join(genre_list).lower()
    series = metadata.get("series_context", "")
    if any(w in genre for w in ["science fiction", "space", "planetary", "galactic"]):
        era = "Spacefaring future"
    elif any(w in genre for w in ["gothic", "victorian", "period"]):
        era = "Period setting"
    elif "fantasy" in genre:
        era = "Fantasy realm"
    else:
        era = "Story-world"
    return {"era": era, "setting": series[:80] if series else metadata.get("title", ""),
            "style_note": ", ".join(metadata.get("genre", [])[:3])}


# ─── NAME MAP HELPERS ─────────────────────────────────
def get_name_map_root(raw):
    """Voodoo nests entities under 'name_map'; original used top-level 'characters'."""
    if isinstance(raw.get("name_map"), dict):
        return raw["name_map"]
    return raw


def character_names(nm_root):
    """Set of canonical names whose type is character."""
    out = set()
    for name, data in nm_root.items():
        if isinstance(data, dict) and data.get("type", "character") == "character":
            out.add(name)
    return out


def aliases_for(nm_root, canonical):
    data = nm_root.get(canonical, {})
    if isinstance(data, dict):
        al = data.get("aliases", [])
        return [canonical] + [a for a in al if isinstance(a, str)]
    return [canonical]


# ─── VISUAL STYLE PARSING ─────────────────────────────
def parse_visual_style_md(path):
    """Parse '## Name' blocks with '* **EPxx**: Appearance: .. | Clothing: .. | Props: ..'."""
    visual = {}
    if not os.path.exists(path):
        return visual
    current = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            mh = re.match(r'^##\s+(.+?)\s*$', line)
            if mh:
                current = mh.group(1).strip()
                continue
            if current and line.lstrip().startswith("*"):
                m = re.search(r'\*\*EP\d+\*\*:\s*(.+)$', line)
                desc = m.group(1).strip() if m else line.lstrip("* ").strip()
                if current not in visual or len(desc) > len(visual[current]):
                    visual[current] = desc
    return visual


def visual_phrase(desc):
    """Condense an 'Appearance: .. | Clothing: .. | Props: ..' line into a prompt phrase."""
    if not desc:
        return ""
    parts = []
    for seg in desc.split("|"):
        seg = seg.strip()
        for label in ("Appearance:", "Clothing:", "Props:"):
            if seg.startswith(label):
                val = seg[len(label):].strip().rstrip(".")
                if val:
                    parts.append(val)
                break
    return "; ".join(parts) if parts else desc.strip()


def mood_to_keywords(mood_str):
    m = (mood_str or "").lower().strip()
    words = re.findall(r'[a-z]+', m)
    unmatched = set(words)
    best_match, best_score = None, 0
    for key in sorted(MOOD_TO_CINEMATIC.keys(), key=len, reverse=True):
        key_words = set(key.split())
        overlap = key_words & unmatched
        if overlap:
            score = len(overlap) / len(key_words) if key_words else 0
            if score > best_score:
                best_score, best_match = score, key
    return best_match if best_score >= 0.5 else "dramatic"


def build_image_prompt(title, location, visual_details, mood, characters, char_visuals,
                       items_str, style):
    cin = MOOD_TO_CINEMATIC.get(mood_to_keywords(mood), MOOD_TO_CINEMATIC["dramatic"])
    loc_clean = location.split("(")[0].split(" — ")[0].strip()[:60]
    if not visual_details:
        visual_details = f"A {mood} scene at {loc_clean}"

    char_desc_parts = []
    for c in characters[:4]:
        if c in char_visuals and char_visuals[c]:
            char_desc_parts.append(f"{c} ({char_visuals[c]})")
        else:
            char_desc_parts.append(c)
    char_str = ", ".join(char_desc_parts) if char_desc_parts else "figures in keeping with the setting"

    prompt_parts = [f"Scene from '{title}': {loc_clean}."]
    vd = visual_details.strip()
    if vd and vd[-1] not in '.!?':
        vd += '.'
    prompt_parts.append(vd)
    if items_str:
        prompt_parts.append(f"Props: {items_str}.")
    prompt_parts.append(f"Characters: {char_str}.")
    prompt_parts.append(f"Mood: {mood}.")
    prompt_parts.append(f"Lighting: {cin['lighting']}. Color palette: {cin['color_palette']}.")
    prompt_parts.append(f"Lens: {cin['lens']}.")
    prompt_parts.append(f"Style: {style}.")
    return " ".join(prompt_parts)


# ─── MAIN ────────────────────────────────────────────
def build_production(project_dir, prefix):
    print(f"\n{'='*60}\nPHASE 9 - PRODUCTION RENDER (GENERIC v1.0)\n{'='*60}")
    print(f"Project: {prefix}\nDir:     {project_dir}")

    mf_dir = os.path.join(project_dir, "micro_facts")
    if not os.path.isdir(mf_dir):
        mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
    entities_dir = os.path.join(project_dir, "entities")
    verification = os.path.join(project_dir, "verification")
    output = os.path.join(project_dir, "output", "production")
    os.makedirs(output, exist_ok=True)

    # global_lore → metadata
    metadata = {}
    gl_path = os.path.join(verification, f"{prefix}_global_lore.json")
    if os.path.exists(gl_path):
        with open(gl_path, encoding="utf-8") as f:
            metadata = json.load(f).get("book_metadata", {})
    title = metadata.get("title", prefix.replace("-", " ").title())
    genre = metadata.get("genre", [])
    STYLE = infer_art_style(genre, title)
    era_setting = infer_era_setting(metadata)
    print(f"Title:   {title}")
    print(f"Genre:   {', '.join(genre)}")
    print(f"Style:   {STYLE[:70]}...")

    # name_map (flat, nested under 'name_map')
    name_map_raw = {}
    nm_path = os.path.join(verification, f"{prefix}_name_map.json")
    if os.path.exists(nm_path):
        with open(nm_path, encoding="utf-8") as f:
            name_map_raw = json.load(f)
    nm_root = get_name_map_root(name_map_raw)
    variant_lookup = build_variant_lookup(name_map_raw)
    char_name_set = character_names(nm_root)

    # character visuals from visual_style.md
    vs_path = os.path.join(entities_dir, f"{prefix}_visual_style.md")
    raw_visuals = parse_visual_style_md(vs_path)
    char_visuals = {name: visual_phrase(desc) for name, desc in raw_visuals.items()}
    print(f"Visual profiles parsed: {len(char_visuals)}")

    # load micro_facts
    all_eps = {}
    for f in sorted(glob.glob(os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json"))):
        ep = os.path.basename(f).split("_EP")[1].split("_")[0]
        with open(f, encoding="utf-8") as fh:
            all_eps[ep] = json.load(fh)
    eps_ordered = sorted(all_eps.keys(), key=lambda x: int(x.replace("EP", "")))
    print(f"Loaded: {len(eps_ordered)} episodes")

    # 1. SCENE INVENTORY & PROMPTS
    print("\n--- Scene Inventory & Prompts ---")
    scenes, prompts = [], []
    total_scenes_processed = 0
    for ep in eps_ordered:
        data = all_eps[ep]
        chapter_title = data.get("chapter_title", f"EP{ep}")
        sds = data.get("scene_details", [])
        items = data.get("items_of_interest", [])
        item_descs = []
        for item in items:
            if isinstance(item, dict):
                name = item.get("item", "")
                desc = (item.get("description", "") or "").strip()
                role = item.get("role_in_chapter", "")
                if name:
                    full_desc = desc
                    if role and role not in full_desc:
                        full_desc = f"{full_desc} — {role}" if full_desc else role
                    item_descs.append(f"{name} ({full_desc})" if full_desc else name)
        items_str = "; ".join(item_descs[:8]) if item_descs else ""

        for s_idx, s in enumerate(sds):
            if not isinstance(s, dict):
                continue
            total_scenes_processed += 1
            if total_scenes_processed % 10 == 0:
                print(f"  Progress: {total_scenes_processed} scenes processed...", flush=True)
            location = s.get("location", "Unknown")
            visual = s.get("visual_details", "")
            mood = s.get("mood", "")
            chars_raw = s.get("characters_present_in_scene", s.get("characters_present", []))
            chars = [normalize_name(c, variant_lookup) for c in chars_raw if isinstance(c, str)]
            loc_clean = location.split("(")[0].split(" — ")[0].strip()
            scene_id = f"SCENE_{ep}_{s_idx + 1:02d}"

            prompt_text = build_image_prompt(title, location, visual, mood, chars,
                                             char_visuals, items_str, STYLE)
            mood_key = mood_to_keywords(mood)
            shot_info = MOOD_TO_SHOT.get(mood_key, {"size": "medium", "move": "static"})
            sd_prompt = prompt_text.replace(
                "Style: " + STYLE,
                "Style: analog film grain, soft focus, vintage cinematic look")

            scenes.append({
                "scene_id": scene_id, "episode": ep, "chapter": chapter_title,
                "order": s_idx + 1, "location": loc_clean, "location_raw": location,
                "mood": mood, "characters_present": chars,
                "characters_visual": [f"{c}: {char_visuals.get(c, 'in-setting attire')}" for c in chars],
                "props": item_descs[:5], "visual_details": visual.strip() if visual else "",
                "shot_size": shot_info["size"], "camera_movement": shot_info["move"],
                "duration_sec": 5 + (2 if "dialogue" in mood_key or "conversational" in mood_key else 0),
                "transition": "cut",
            })
            prompts.append({
                "scene_id": scene_id, "episode": ep, "location": loc_clean, "mood": mood,
                "characters": chars,
                "characters_visual": [f"{c}: {char_visuals.get(c, 'in-setting attire')}" for c in chars],
                "props": item_descs[:5], "prompt_midjourney": prompt_text,
                "prompt_stable_diffusion": sd_prompt, "aspect_ratio": ASPECT_RATIOS["wide"],
                "cinematic": MOOD_TO_CINEMATIC.get(mood_key, {}),
            })
            print(f"  {scene_id:20s} | {loc_clean[:30]:30s} | {mood[:25]:25s} | {len(chars)} chars")

    with open(os.path.join(output, "cinematography_shot_list.json"), "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)
    print(f"\n  cinematography_shot_list.json ({len(scenes)} scenes)")
    with open(os.path.join(output, "scene_image_prompts.json"), "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    print(f"  scene_image_prompts.json ({len(prompts)} prompts)")

    # 2. ENTITY REGISTRY
    print("\n--- Entity Registry ---")
    char_profiles = defaultdict(lambda: {"episodes": [], "behaviors": []})
    for ep in eps_ordered:
        for b in all_eps[ep].get("character_behaviors", []):
            if not isinstance(b, dict):
                continue
            cname = normalize_name(b.get("character", ""), variant_lookup)
            if cname:
                char_profiles[cname]["episodes"].append(ep)
                char_profiles[cname]["behaviors"].append((b.get("behavior", "") or "")[:80])

    character_registry = {}
    next_id = 0
    for char_name in sorted(char_profiles.keys()):
        if char_name_set and char_name not in char_name_set and char_name not in char_visuals:
            continue
        cid = f"CHAR_{next_id:03d}"
        next_id += 1
        episodes = sorted(set(char_profiles[char_name]["episodes"]), key=lambda x: int(x.replace("EP", "")))
        key_behaviors = list(set(char_profiles[char_name]["behaviors"]))[:5]
        character_registry[cid] = {
            "canonical_name": char_name,
            "aliases": list(set(aliases_for(nm_root, char_name))),
            "episodes_active": episodes,
            "total_scenes": len(episodes),
            "key_actions": key_behaviors,
            "visual_description": char_visuals.get(char_name, ""),
            "visual_anchor": era_setting,
        }

    location_registry = {}
    loc_path = os.path.join(entities_dir, f"{prefix}_locations.md")
    if os.path.exists(loc_path):
        with open(loc_path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r'^\*\s+\*\*(.+?)\*\*.*?EP(\d+)', line)
                if m:
                    loc, ep = m.group(1).strip(), f"EP{m.group(2)}"
                    location_registry.setdefault(loc, {"episodes": []})
                    if ep not in location_registry[loc]["episodes"]:
                        location_registry[loc]["episodes"].append(ep)

    entity_registry = {
        "project": title, "generated_at": datetime.now().isoformat(),
        "character_registry": character_registry, "location_registry": location_registry,
        "total_characters": len(character_registry), "total_locations": len(location_registry),
    }
    with open(os.path.join(output, "entity_registry.json"), "w", encoding="utf-8") as f:
        json.dump(entity_registry, f, ensure_ascii=False, indent=2)
    print(f"  entity_registry.json ({len(character_registry)} chars, {len(location_registry)} locs)")

    # 3. VISUAL STYLE BIBLE
    print("\n--- Visual Style Bible ---")
    style_bible = {}
    for char_name in sorted(char_profiles.keys()):
        if char_name not in character_registry_names(character_registry):
            continue
        episodes = sorted(set(char_profiles[char_name]["episodes"]), key=lambda x: int(x.replace("EP", "")))
        vis = char_visuals.get(char_name, "")
        ref = (f"{char_name} from '{title}'. "
               f"{vis + '. ' if vis else ''}"
               f"{era_setting['era']} setting. "
               f"Appears in chapters: {', '.join(episodes)}. "
               f"Art style: {', '.join(genre[:3])}.")
        style_bible[char_name] = {
            "first_appearance": episodes[0] if episodes else "?",
            "last_appearance": episodes[-1] if episodes else "?",
            "total_scenes": len(episodes), "episode_list": episodes,
            "visual_description": vis,
            "visual_reference_prompt": ref,
        }
    with open(os.path.join(output, "visual_style_bible.json"), "w", encoding="utf-8") as f:
        json.dump(style_bible, f, ensure_ascii=False, indent=2)
    print(f"  visual_style_bible.json ({len(style_bible)} characters)")

    # 4. PRODUCTION MANIFEST
    print("\n--- Production Manifest ---")
    ep_breakdown = []
    for ep in eps_ordered:
        ep_scenes = [s for s in scenes if s["episode"] == ep]
        ep_breakdown.append({
            "episode": ep, "title": all_eps[ep].get("chapter_title", f"EP{ep}"),
            "scene_count": len(ep_scenes),
            "characters": list(set(c for s in ep_scenes for c in s["characters_present"])),
            "locations": list(set(s["location"] for s in ep_scenes)),
        })
    manifest = {
        "project": prefix, "title": title, "generated_at": datetime.now().isoformat(),
        "pipeline_version": "generic-v1.0-production", "genre": genre,
        "art_style": STYLE, "total_episodes": len(eps_ordered),
        "total_scenes": len(scenes), "total_prompts": len(prompts),
        "total_characters": len(character_registry), "total_locations": len(location_registry),
        "aspect_ratio": "16:9",
        "recommended_tools": {
            "image_generation": ["Midjourney v6.1", "Stable Diffusion XL", "ComfyUI + Flux"],
            "video_generation": ["Luma Ray 2", "Kling 1.6", "Runway Gen-3"],
            "animation": ["AnimateDiff", "ComfyUI + Wan T2V"],
        },
        "episodes": ep_breakdown,
        "file_index": {
            "cinematography_shot_list.json": f"{len(scenes)} scenes",
            "scene_image_prompts.json": f"{len(prompts)} prompts",
            "entity_registry.json": f"{len(character_registry)} chars, {len(location_registry)} locs",
            "visual_style_bible.json": f"{len(style_bible)} characters",
            "production_manifest.json": "this file",
        },
    }
    with open(os.path.join(output, "production_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  production_manifest.json")

    print(f"\n{'='*60}\nPHASE 9 COMPLETE\n{'='*60}")
    print(f"Output: {output}")
    print(f"  Scenes: {len(scenes)} | Prompts: {len(prompts)} | "
          f"Chars: {len(character_registry)} | Locs: {len(location_registry)}")


def character_registry_names(reg):
    return {v["canonical_name"] for v in reg.values()}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/assemble_production_generic.py <project_dir> [prefix]")
        sys.exit(1)
    project_dir = sys.argv[1].rstrip("/\\")
    prefix = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(project_dir)
    build_production(project_dir, prefix)
