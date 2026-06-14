import os
import json
import re
import hashlib
from typing import Dict, Any, List

def load_json(file_path: str) -> Dict[str, Any]:
    """Safely load JSON file with UTF-8 encoding."""
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARNING] Failed to load JSON from {file_path}: {e}")
        return {}

def write_json(file_path: str, data: Any, indent: int = 2) -> bool:
    """Safely write JSON file with UTF-8 encoding."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to write JSON to {file_path}: {e}")
        return False

def build_variant_lookup(name_map: Dict[str, Any]) -> Dict[str, str]:
    """
    Builds a lookup mapping lowercase names/aliases/variants back to the canonical name.
    Supports nested name maps under 'characters' or 'name_map', as well as flat name maps.
    """
    lookup = {}
    
    chars_dict = {}
    if "characters" in name_map:
        chars_dict = name_map["characters"]
    elif "name_map" in name_map:
        chars_dict = name_map["name_map"]
    else:
        chars_dict = name_map

    for canonical, data in chars_dict.items():
        if canonical.startswith("_"):  # Skip metadata keys like _meta
            continue
        if not isinstance(data, dict):
            continue
        # Ensure it is character-like (skip location/concept keys if they specify type)
        if data.get("type") not in (None, "character") and "aliases" not in data and "en" not in data and "standard" not in data:
            continue
            
        keys = [canonical, data.get("thai", ""), data.get("en", ""), data.get("standard", "")]
        keys += data.get("aliases", [])
        keys += data.get("asr_variants", [])
        
        for k in keys:
            if isinstance(k, str):
                k = k.strip().lower()
                if k and k not in lookup:
                    lookup[k] = canonical
    return lookup

def normalize_name(raw_name: str, variant_lookup: Dict[str, str]) -> str:
    """Normalize a raw character name using the variant lookup dictionary."""
    if not raw_name:
        return ""
    key = raw_name.strip().lower()
    if key in variant_lookup:
        return variant_lookup[key]
    
    # Strip any parentheticals, e.g. "Lord Swanleigh (deceased)" -> "Lord Swanleigh"
    cleaned = re.sub(r'\s*\(.*?\)\s*', '', raw_name).strip()
    if cleaned.lower() in variant_lookup:
        return variant_lookup[cleaned.lower()]
        
    # Split by separators, e.g., "Mrs. Herbert / Helen Vaughan" -> check first part
    for sep in (" / ", " — "):
        if sep in raw_name:
            first = raw_name.split(sep)[0].strip().lower()
            if first in variant_lookup:
                return variant_lookup[first]
                
    return raw_name

def normalize_location(raw_loc: str) -> str:
    """Normalize a location name by stripping suffixes, parentheses, em-dashes."""
    if not raw_loc:
        return ""
    loc = raw_loc.split("(")[0].strip()
    # Strip trailing descriptive clause after em-dash or slash
    loc = re.sub(r'\s+— .*$', '', loc)
    loc = re.sub(r'\s+-- .*$', '', loc)
    loc = loc.split(" — ")[0] if " — " in loc else loc
    return loc.strip()

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file's content to detect changes."""
    if not os.path.exists(file_path):
        return ""
    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception as e:
        print(f"[WARNING] Failed to calculate hash for {file_path}: {e}")
        return ""

def is_episode_cached(project_dir: str, prefix: str, ep_num: str, raw_filepath: str) -> bool:
    """Check if the episode's raw content hash matches the cached state and output exists."""
    # Check if final output exists
    mf_dir = os.path.join(project_dir, "micro_facts")
    if not os.path.isdir(mf_dir):
        mf_dir = os.path.join(project_dir, "analysis", "micro_facts")
    
    out_path = os.path.join(mf_dir, f"{prefix}_{ep_num}_micro_facts.json")
    if not os.path.exists(out_path):
        return False
        
    # Check state file
    state_path = os.path.join(project_dir, f"{prefix}_pipeline_state.json")
    if not os.path.exists(state_path):
        return False
        
    state = load_json(state_path)
    cached_hash = state.get("episode_hashes", {}).get(ep_num, {}).get("raw_hash", "")
    current_hash = calculate_file_hash(raw_filepath)
    
    return current_hash != "" and current_hash == cached_hash

def update_episode_cache(project_dir: str, prefix: str, ep_num: str, raw_filepath: str):
    """Update the cache hash for a specific episode in the project state file."""
    state_path = os.path.join(project_dir, f"{prefix}_pipeline_state.json")
    state = load_json(state_path)
    
    if "episode_hashes" not in state:
        state["episode_hashes"] = {}
        
    current_hash = calculate_file_hash(raw_filepath)
    if current_hash:
        state["episode_hashes"][ep_num] = {
            "raw_hash": current_hash,
            "merged_facts_exists": True
        }
        write_json(state_path, state)


def generate_previous_chapters_summary(project_dir: str, prefix: str, current_ep_num: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Step 2: Generate auto-summaries of the previous N chapters.
    Calculates key events, characters, and new introductions without LLM cost.
    """
    # Parse episode number to integer
    match = re.search(r'\d+', current_ep_num)
    if not match:
        return []
    current_idx = int(match.group(0))
    
    micro_dir = os.path.join(project_dir, "micro_facts")
    if not os.path.isdir(micro_dir):
        micro_dir = os.path.join(project_dir, "analysis", "micro_facts")
        
    # Track characters seen prior to the previous chapters to detect "newly introduced"
    all_seen_chars = set()
    
    # 1. Scan from EP001 up to current_idx - limit - 1 to build baseline seen characters
    for idx in range(1, current_idx - limit):
        ep_label = f"EP{idx:03d}"
        fpath = os.path.join(micro_dir, f"{prefix}_{ep_label}_micro_facts.json")
        if os.path.exists(fpath):
            ep_data = load_json(fpath)
            for c in ep_data.get("characters_present", []):
                all_seen_chars.add(c)
                
    summaries = []
    # 2. Extract summaries for the last `limit` chapters
    for idx in range(max(1, current_idx - limit), current_idx):
        ep_label = f"EP{idx:03d}"
        fpath = os.path.join(micro_dir, f"{prefix}_{ep_label}_micro_facts.json")
        if not os.path.exists(fpath):
            continue
            
        ep_data = load_json(fpath)
        kpps = ep_data.get("key_plot_points", [])
        # Get first 3 key events summary
        key_events = [k.get("description", "") for k in kpps[:3] if k.get("description")]
        
        present = ep_data.get("characters_present", [])
        
        # Detect new characters introduced in this specific chapter
        new_chars = []
        for c in present:
            if c not in all_seen_chars:
                new_chars.append(c)
                all_seen_chars.add(c)
                
        summaries.append({
            "chapter": ep_label,
            "chapter_title": ep_data.get("chapter_title", ""),
            "key_events": key_events,
            "characters_present": present,
            "new_characters_introduced": new_chars
        })
        
    return summaries


