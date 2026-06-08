import os
import json
import re
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
