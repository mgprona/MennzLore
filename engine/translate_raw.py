#!/usr/bin/env python3
"""
MennzLore Raw Translator
========================
Translates raw Thai literature transcripts to English before core extraction.
Supports three translation modes:

  manual   — You (the user) place pre-translated EN files in raw/en/ yourself.
             The system just detects and registers them. Best for quality control.

  api      — A cheap OpenRouter model (e.g. Gemini Flash, DeepSeek) translates
             each episode file sequentially. Uses file-hash cache to skip unchanged files.

  parallel — Same as 'api' but episodes are translated concurrently using threads.
             Best for large novels with many episodes where speed matters.

Usage (CLI):
  python translate_raw.py <project_dir> <prefix> [--mode manual|api|parallel] [--model <model_id>]

Usage (Python):
  from translate_raw import run_translation_pipeline
  run_translation_pipeline(project_dir, prefix, mode="api")
"""
import os
import sys
import json
import glob
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

try:
    from utils import load_json, write_json, calculate_file_hash
except ImportError:
    from engine.utils import load_json, write_json, calculate_file_hash

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TRANSLATION_MODEL = "google/gemini-2.5-flash"  # cheap + large context
BACK_TRANSLATION_MODEL     = "google/gemini-2.5-pro"   # high quality for Thai literary output
API_URL = "https://openrouter.ai/api/v1/chat/completions"

VALID_MODES = ("manual", "api", "parallel")


# ---------------------------------------------------------------------------
# Name-mapping helpers
# ---------------------------------------------------------------------------

def get_name_mappings(project_dir: str, prefix: str) -> Dict[str, str]:
    """Extract Thai → English character name mappings from {prefix}_name_map.json."""
    nm_path = os.path.join(project_dir, "verification", f"{prefix}_name_map.json")
    if not os.path.exists(nm_path):
        nm_path = os.path.join(project_dir, "verification", "name_map.json")

    name_map = load_json(nm_path)
    mappings: Dict[str, str] = {}

    chars_dict = name_map.get("characters", name_map.get("name_map", name_map))
    if isinstance(chars_dict, dict):
        for thai_name, data in chars_dict.items():
            if isinstance(data, dict) and "english_name" in data:
                mappings[thai_name] = data["english_name"]
            elif any(ord(c) < 128 for c in thai_name):
                mappings[thai_name] = thai_name
    return mappings


# ---------------------------------------------------------------------------
# Core API helpers
# ---------------------------------------------------------------------------

def _openrouter_chat(api_key: str, system_prompt: str, user_content: str, model_id: str, timeout: int = 180) -> str:
    """Generic OpenRouter chat call. Returns assistant message content."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
    }
    response = requests.post(API_URL, headers=headers, json=body, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter {response.status_code}: {response.text[:500]}")
    choices = response.json().get("choices", [])
    if not choices:
        raise RuntimeError(f"Empty choices in response: {response.text[:300]}")
    return choices[0]["message"]["content"].strip()


def translate_thai_to_english(
    api_key: str,
    thai_text: str,
    name_mappings: Dict[str, str],
    model_id: str = DEFAULT_TRANSLATION_MODEL,
) -> str:
    """Translate Thai transcript → English using a bilingual name glossary."""
    mapping_str = "\n".join(f"  - '{th}' → '{en}'" for th, en in name_mappings.items())
    system_prompt = (
        "You are an expert literary translator specialising in classical Thai literature.\n"
        "Translate the provided Thai transcript/chapter into fluent English.\n\n"
        "RULES:\n"
        "1. Full faithful translation — do NOT summarise or omit any detail.\n"
        "2. Preserve paragraph breaks, dialogue structure, and formatting exactly.\n"
        "3. Use the glossary below for character and place names:\n"
        f"{mapping_str}\n"
        "4. Output ONLY the translated English text — no translator notes, no markdown wrappers."
    )
    return _openrouter_chat(api_key, system_prompt, thai_text, model_id)


def translate_english_to_thai(
    api_key: str,
    english_text: str,
    model_id: str = BACK_TRANSLATION_MODEL,
) -> str:
    """Translate English lorebook section → Thai with high literary quality (Phanom Tian style)."""
    system_prompt = (
        "You are an elite literary translator specialising in translating English lorebooks and\n"
        "world-building documents into classical, beautiful Thai prose.\n\n"
        "RULES:\n"
        "1. Maintain all markdown formatting (tables, lists, headers, bold, italic).\n"
        "2. Use refined, poetic Thai suitable for classic Thai novels (Phanom Tian style).\n"
        "3. Restore character and place names to their correct Thai spellings, e.g.:\n"
        "   'Ariyawat' → 'อริยวัตร', 'Dararai' → 'ดาราราย', 'Khattiya' → 'ขัตติยะ',\n"
        "   'Apassara' → 'อภัสรา', 'Chulatrikun' → 'จุลาตรีคูณ'.\n"
        "4. Output ONLY the translated Thai markdown — no notes, no wrappers."
    )
    return _openrouter_chat(api_key, system_prompt, english_text, model_id)


# ---------------------------------------------------------------------------
# MODE: manual
# ---------------------------------------------------------------------------

def _run_manual_mode(project_dir: str, prefix: str, raw_files: List[str], en_dir: str, cache: dict, cache_path: str) -> dict:
    """
    Manual mode: the user has already placed translated EN files in raw/en/.
    We scan for them, register them in the cache, and report what we found.
    Expected filename convention: {prefix}_{EP_ID}_en.txt
    """
    print("[translate_raw] MODE: manual")
    print(f"  Scanning {en_dir} for pre-translated files...")

    registered = 0
    missing = []

    for fpath in raw_files:
        ep_id = os.path.basename(fpath).replace(f"{prefix}_", "").replace(".txt", "")
        dest_filename = f"{prefix}_{ep_id}_en.txt"
        dest_path = os.path.join(en_dir, dest_filename)

        if os.path.exists(dest_path):
            raw_hash = calculate_file_hash(fpath)
            cache["translated_files"][ep_id] = {
                "raw_hash": raw_hash,
                "translated_path": dest_path,
                "mode": "manual",
            }
            print(f"  [OK] {dest_filename} — registered")
            registered += 1
        else:
            missing.append(dest_filename)
            print(f"  [MISSING] {dest_filename} — place your translation here: {dest_path}")

    write_json(cache_path, cache)

    if missing:
        print(f"\n  ⚠  {len(missing)} file(s) missing. Place them in:\n  {en_dir}")
        return {
            "status": "partial",
            "registered": registered,
            "missing": missing,
        }

    print(f"\n  ✓ All {registered} file(s) registered from manual translations.")
    return {"status": "ok", "mode": "manual", "registered": registered}


# ---------------------------------------------------------------------------
# MODE: api (sequential)
# ---------------------------------------------------------------------------

def _translate_one_episode(
    api_key: str,
    fpath: str,
    prefix: str,
    en_dir: str,
    name_mappings: Dict[str, str],
    model_id: str,
) -> dict:
    """Translate a single Thai episode file and return result dict."""
    ep_id = os.path.basename(fpath).replace(f"{prefix}_", "").replace(".txt", "")
    dest_filename = f"{prefix}_{ep_id}_en.txt"
    dest_path = os.path.join(en_dir, dest_filename)

    with open(fpath, "r", encoding="utf-8") as f:
        thai_content = f.read()

    english_content = translate_thai_to_english(api_key, thai_content, name_mappings, model_id)

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(english_content)

    return {
        "episode": ep_id,
        "status": "translated",
        "path": dest_path,
        "raw_hash": calculate_file_hash(fpath),
    }


def _run_api_mode(
    project_dir: str,
    prefix: str,
    raw_files: List[str],
    en_dir: str,
    cache: dict,
    cache_path: str,
    api_key: str,
    model_id: str,
) -> dict:
    """Sequential API translation mode."""
    print(f"[translate_raw] MODE: api  |  model: {model_id}")

    translated_count = 0
    skipped_count = 0
    results = []

    for fpath in raw_files:
        ep_id = os.path.basename(fpath).replace(f"{prefix}_", "").replace(".txt", "")
        dest_path = os.path.join(en_dir, f"{prefix}_{ep_id}_en.txt")

        current_hash = calculate_file_hash(fpath)
        cached_hash  = cache["translated_files"].get(ep_id, {}).get("raw_hash", "")

        if current_hash and current_hash == cached_hash and os.path.exists(dest_path):
            print(f"  [CACHED]  {ep_id} — skipping")
            results.append({"episode": ep_id, "status": "cached", "path": dest_path})
            skipped_count += 1
            continue

        print(f"  [TRANSLATING]  {os.path.basename(fpath)} ...")
        try:
            res = _translate_one_episode(api_key, fpath, prefix, en_dir, 
                                          get_name_mappings(project_dir, prefix), model_id)
            cache["translated_files"][ep_id] = {
                "raw_hash": res["raw_hash"],
                "translated_path": res["path"],
                "mode": "api",
                "model": model_id,
            }
            write_json(cache_path, cache)
            results.append(res)
            translated_count += 1
            print(f"  [OK]       {ep_id} → {os.path.basename(res['path'])}")
        except Exception as e:
            print(f"  [ERROR]   {ep_id}: {e}")
            results.append({"episode": ep_id, "status": "error", "error": str(e)})

    return {
        "status": "ok",
        "mode": "api",
        "model": model_id,
        "translated_count": translated_count,
        "skipped_count": skipped_count,
        "results": results,
    }


# ---------------------------------------------------------------------------
# MODE: parallel
# ---------------------------------------------------------------------------

def _run_parallel_mode(
    project_dir: str,
    prefix: str,
    raw_files: List[str],
    en_dir: str,
    cache: dict,
    cache_path: str,
    api_key: str,
    model_id: str,
    max_workers: int = 4,
) -> dict:
    """
    Parallel API translation mode.
    Spawns up to `max_workers` threads so multiple episodes translate simultaneously.
    Ideal when you have many episodes and want maximum speed.
    """
    print(f"[translate_raw] MODE: parallel  |  model: {model_id}  |  workers: {max_workers}")

    name_mappings = get_name_mappings(project_dir, prefix)

    # Separate cached vs. needs-translation
    to_translate = []
    results = []
    skipped_count = 0

    for fpath in raw_files:
        ep_id = os.path.basename(fpath).replace(f"{prefix}_", "").replace(".txt", "")
        dest_path = os.path.join(en_dir, f"{prefix}_{ep_id}_en.txt")
        current_hash = calculate_file_hash(fpath)
        cached_hash  = cache["translated_files"].get(ep_id, {}).get("raw_hash", "")

        if current_hash and current_hash == cached_hash and os.path.exists(dest_path):
            print(f"  [CACHED]  {ep_id} — skipping")
            results.append({"episode": ep_id, "status": "cached", "path": dest_path})
            skipped_count += 1
        else:
            to_translate.append((ep_id, fpath))

    if not to_translate:
        return {
            "status": "ok",
            "mode": "parallel",
            "translated_count": 0,
            "skipped_count": skipped_count,
            "results": results,
        }

    print(f"  Submitting {len(to_translate)} episode(s) to {max_workers} parallel worker(s)...")

    translated_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_translate_one_episode, api_key, fpath, prefix, en_dir, name_mappings, model_id): ep_id
            for ep_id, fpath in to_translate
        }
        for future in as_completed(future_map):
            ep_id = future_map[future]
            try:
                res = future.result()
                cache["translated_files"][ep_id] = {
                    "raw_hash": res["raw_hash"],
                    "translated_path": res["path"],
                    "mode": "parallel",
                    "model": model_id,
                }
                write_json(cache_path, cache)  # safe: GIL protects dict writes; json dump is atomic enough
                results.append(res)
                translated_count += 1
                print(f"  [OK]  {ep_id} → {os.path.basename(res['path'])}")
            except Exception as e:
                print(f"  [ERROR]  {ep_id}: {e}")
                results.append({"episode": ep_id, "status": "error", "error": str(e)})

    return {
        "status": "ok",
        "mode": "parallel",
        "model": model_id,
        "translated_count": translated_count,
        "skipped_count": skipped_count,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_translation_pipeline(
    project_dir: str,
    prefix: str,
    mode: str = "api",
    model_id: str = DEFAULT_TRANSLATION_MODEL,
    max_workers: int = 4,
) -> dict:
    """
    Run the T1 translation pipeline.

    Parameters
    ----------
    project_dir  : absolute path to the project directory
    prefix       : project prefix (e.g. 'chula')
    mode         : 'manual' | 'api' | 'parallel'
                     manual   — user pre-places EN files; system just registers them
                     api      — sequential OpenRouter API calls (default)
                     parallel — concurrent OpenRouter API calls for speed
    model_id     : OpenRouter model to use for translation (api/parallel modes only)
    max_workers  : thread count for parallel mode (default: 4)
    """
    if mode not in VALID_MODES:
        return {"status": "error", "message": f"Invalid mode '{mode}'. Choose from: {VALID_MODES}"}

    raw_dir = os.path.join(project_dir, "raw")
    en_dir  = os.path.join(raw_dir, "en")
    os.makedirs(en_dir, exist_ok=True)

    # Load / initialise cache
    cache_path = os.path.join(project_dir, f"{prefix}_translation_state.json")
    cache = load_json(cache_path)
    if "translated_files" not in cache:
        cache["translated_files"] = {}
    cache["mode"] = mode  # record which mode was used

    # Discover source files
    raw_files = sorted(glob.glob(os.path.join(raw_dir, f"{prefix}_EP*.txt")))
    if not raw_files:
        return {
            "status": "error",
            "message": f"No raw files matching '{prefix}_EP*.txt' found in {raw_dir}",
        }

    print(f"\n[translate_raw] Project : {project_dir}")
    print(f"[translate_raw] Prefix  : {prefix}")
    print(f"[translate_raw] Episodes: {len(raw_files)} file(s) found")

    # --- dispatch to mode handler ---

    if mode == "manual":
        return _run_manual_mode(project_dir, prefix, raw_files, en_dir, cache, cache_path)

    # api / parallel both need an API key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "status": "error",
            "message": (
                "OPENROUTER_API_KEY is not set.\n"
                "  • Set it with: $env:OPENROUTER_API_KEY='sk-...'\n"
                "  • Or switch to manual mode: run_translation_pipeline(..., mode='manual')"
            ),
        }

    if mode == "api":
        return _run_api_mode(project_dir, prefix, raw_files, en_dir, cache, cache_path, api_key, model_id)

    if mode == "parallel":
        return _run_parallel_mode(project_dir, prefix, raw_files, en_dir, cache, cache_path, api_key, model_id, max_workers)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="MennzLore Raw Translator — Thai → English (T1 step of TET pipeline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Translation modes:
  manual    You place the EN files in raw/en/ yourself, system just registers them.
            Filename format expected: {prefix}_{EP_ID}_en.txt
            Best for: quality control, expensive episodes, human-in-the-loop review.

  api       Each episode is translated sequentially via OpenRouter API.
            Best for: small number of episodes, simple setup.

  parallel  Episodes are translated concurrently (threaded) via OpenRouter API.
            Best for: many episodes, speed-critical batch runs.

Examples:
  python translate_raw.py C:/projects/chula chula
  python translate_raw.py C:/projects/chula chula --mode manual
  python translate_raw.py C:/projects/chula chula --mode parallel --workers 6
  python translate_raw.py C:/projects/chula chula --mode api --model deepseek/deepseek-chat
        """,
    )
    parser.add_argument("project_dir", help="Absolute path to the project directory")
    parser.add_argument("prefix",      help="Project prefix (e.g. 'chula')")
    parser.add_argument(
        "--mode", choices=VALID_MODES, default="api",
        help="Translation mode: manual | api | parallel  (default: api)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_TRANSLATION_MODEL,
        help=f"OpenRouter model ID for api/parallel modes (default: {DEFAULT_TRANSLATION_MODEL})",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of parallel threads for 'parallel' mode (default: 4)",
    )

    args = parser.parse_args()

    result = run_translation_pipeline(
        project_dir=args.project_dir,
        prefix=args.prefix,
        mode=args.mode,
        model_id=args.model,
        max_workers=args.workers,
    )

    print(f"\nResult: {json.dumps(result, indent=2, ensure_ascii=False)}")

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
