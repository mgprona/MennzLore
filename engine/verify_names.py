#!/usr/bin/env python3
"""
Phase 3.2: Auto-Verify Names
=============================
Cross-references the name map JSON with raw/clean text files to check if defined characters
are actually present in the text, reporting missing/unreferenced names.

Usage:
    python engine/verify_names.py <project_dir> [prefix]
"""
import os
import sys
import json
import glob

def verify_names(project_dir: str, prefix: str | None = None) -> dict:
    project_dir = project_dir.rstrip("/\\")
    if not prefix:
        prefix = os.path.basename(project_dir)

    print(f"\n{'='*60}\nPHASE 3.2 — AUTO-VERIFY NAMES\n{'='*60}")
    print(f"Project: {prefix}")
    print(f"Dir:     {project_dir}")

    verification_dir = os.path.join(project_dir, "verification")
    nm_paths = [
        os.path.join(verification_dir, f"{prefix}_name_map.json"),
        os.path.join(verification_dir, "name_map.json")
    ]
    
    name_map_path = None
    for path in nm_paths:
        if os.path.exists(path):
            name_map_path = path
            break
            
    if not name_map_path:
        print(f"[ERROR] name_map.json not found in verification/ directory.")
        return {"status": "error", "message": "name_map.json not found"}

    try:
        with open(name_map_path, "r", encoding="utf-8") as f:
            name_map = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read name map: {e}")
        return {"status": "error", "message": str(e)}

    # Extract characters
    chars_dict = {}
    if "characters" in name_map:
        chars_dict = name_map["characters"]
    elif "name_map" in name_map:
        for k, v in name_map["name_map"].items():
            if isinstance(v, dict) and v.get("type", "character") == "character":
                chars_dict[k] = v
    else:
        for k, v in name_map.items():
            if isinstance(v, dict) and v.get("type", "character") == "character":
                chars_dict[k] = v

    if not chars_dict:
        print("[WARNING] No character definitions found in the name map.")
        return {"status": "warning", "message": "No characters in name map", "missing_characters": []}

    # Map each variant/alias back to its canonical name
    variant_lookup = {}
    for canonical, data in chars_dict.items():
        keys = [canonical]
        if isinstance(data, dict):
            keys += [data.get("thai", ""), data.get("en", ""), data.get("standard", "")]
            keys += data.get("aliases", [])
            keys += data.get("asr_variants", [])
        
        # Clean and add unique keys
        for k in keys:
            if isinstance(k, str):
                k = k.strip().lower()
                if k and k not in ["character", "type"]:
                    variant_lookup.setdefault(k, set()).add(canonical)

    # Locate source text directory
    text_dir = os.path.join(project_dir, "raw")
    if not os.path.isdir(text_dir) or not glob.glob(os.path.join(text_dir, "*.*")):
        text_dir = os.path.join(project_dir, "clean")
    if not os.path.isdir(text_dir) or not glob.glob(os.path.join(text_dir, "*.*")):
        text_dir = project_dir

    # Find text files
    text_files = []
    for ext in ("*.txt", "*.md"):
        text_files += glob.glob(os.path.join(text_dir, ext))
        text_files += glob.glob(os.path.join(text_dir, "chapters", ext))
        
    if not text_files:
        print(f"[WARNING] No raw or clean text files found in {text_dir} for verification.")
        return {"status": "warning", "message": "No text files found to check", "missing_characters": []}

    # Read all text contents
    full_text = ""
    scanned_paths = []
    for fp in sorted(text_files):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                full_text += f.read() + "\n"
            scanned_paths.append(os.path.abspath(fp))
        except Exception as e:
            print(f"[WARNING] Could not read file {fp}: {e}")

    full_text_lower = full_text.lower()
    print(f"Scanned {len(scanned_paths)} files, total text length: {len(full_text_lower):,} chars")

    # Check counts for each variant
    counts = {}
    char_totals = {c: 0 for c in chars_dict.keys()}
    
    for variant, canons in variant_lookup.items():
        cnt = full_text_lower.count(variant)
        counts[variant] = cnt
        for c in canons:
            char_totals[c] += cnt

    # Collect missing characters
    missing_chars = []
    found_chars = []
    details = {}

    for c in sorted(chars_dict.keys()):
        c_variants = [v for v, canons in variant_lookup.items() if c in canons]
        c_counts = {v: counts[v] for v in c_variants}
        total_occurrences = char_totals[c]
        
        details[c] = {
            "variants": c_variants,
            "counts": c_counts,
            "total_occurrences": total_occurrences
        }
        
        if total_occurrences == 0:
            missing_chars.append(c)
        else:
            found_chars.append(c)

    # Print results
    print(f"\nVerification Results:")
    print(f"  Total characters checked: {len(chars_dict)}")
    print(f"  Characters found:         {len(found_chars)}")
    print(f"  Characters missing (0 instances in text): {len(missing_chars)}")

    if missing_chars:
        print("\n[!] MISSING CHARACTERS IN RAW/CLEAN TEXT:")
        for mc in missing_chars:
            print(f"  - {mc} (variants checked: {', '.join(details[mc]['variants'])})")
    else:
        print("\n[OK] All characters in the name map were found at least once in the text.")

    print(f"\n{'='*60}\nAUTO-VERIFY NAMES COMPLETE\n{'='*60}")
    
    return {
        "status": "ok",
        "project_dir": project_dir,
        "prefix": prefix,
        "total_characters": len(chars_dict),
        "missing_characters": missing_chars,
        "found_characters": found_chars,
        "details": details,
        "scanned_files": scanned_paths
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python engine/verify_names.py <project_dir> [prefix]")
        sys.exit(1)
    verify_names(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
