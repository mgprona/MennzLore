#!/usr/bin/env python3
"""
MennzLore Raw Translator
========================
Translates raw Thai literature transcripts to English before core extraction.
Utilizes bilingual name mappings for consistency and caches translations.
"""
import os
import sys
import json
import requests
from typing import Dict, Any, List
from utils import load_json, write_json, calculate_file_hash

DEFAULT_MODEL = "google/gemini-2.5-flash"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

def get_name_mappings(project_dir: str, prefix: str) -> Dict[str, str]:
    """Extract Thai to English character name mappings from name_map.json."""
    nm_path = os.path.join(project_dir, "verification", f"{prefix}_name_map.json")
    if not os.path.exists(nm_path):
        # Fallback to name_map.json
        nm_path = os.path.join(project_dir, "verification", "name_map.json")
        
    name_map = load_json(nm_path)
    mappings = {}
    
    chars_dict = name_map.get("characters", name_map.get("name_map", name_map))
    if isinstance(chars_dict, dict):
        for thai_name, data in chars_dict.items():
            if isinstance(data, dict) and "english_name" in data:
                mappings[thai_name] = data["english_name"]
            else:
                # Fallback to key itself if it contains English characters
                if any(ord(c) < 128 for c in thai_name):
                    mappings[thai_name] = thai_name
    return mappings

def translate_thai_to_english(api_key: str, thai_text: str, name_mappings: Dict[str, str], model_id: str = DEFAULT_MODEL) -> str:
    """Send Thai text to OpenRouter for translation to English with constraints."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Format mapping guidance
    mapping_str = "\n".join([f"- '{thai}' -> '{eng}'" for thai, eng in name_mappings.items()])
    
    system_prompt = (
        "You are an expert literary translator specializing in translating classical Thai literature and transcripts into English.\n"
        "Your task is to translate the provided Thai transcript/story chapter into English.\n\n"
        "CRITICAL RULES:\n"
        "1. Perform a full, detailed, faithful translation. Do NOT summarize or omit details.\n"
        "2. Keep the paragraph breaks, dialogue structure, and layout exactly as in the original.\n"
        "3. You must translate character names and settings consistently using the following glossary mapping:\n"
        f"{mapping_str}\n"
        "4. Output ONLY the translated English text. Do not include any translator notes, introduction, or markdown code blocks around the text unless the original text had them."
    )
    
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": thai_text}
        ]
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=body, timeout=120)
        if response.status_code != 200:
            raise Exception(f"OpenRouter API Error {response.status_code}: {response.text}")
            
        res_json = response.json()
        choices = res_json.get("choices", [])
        if not choices:
            raise Exception(f"Invalid API response: {json.dumps(res_json)}")
            
        translated = choices[0].get("message", {}).get("content", "").strip()
        if not translated:
            raise Exception("Received empty translation content from API.")
            
        return translated
    except Exception as e:
        raise Exception(f"Translation API request failed: {e}")

def translate_english_to_thai(api_key: str, english_text: str, model_id: str = "google/gemini-2.5-pro") -> str:
    """Translate English text back to Thai, maintaining high literary quality."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    system_prompt = (
        "You are an elite literary translator specializing in translating English stories and world-building lorebooks into classical, beautiful Thai.\n"
        "Your task is to translate the provided English markdown text into Thai.\n\n"
        "CRITICAL RULES:\n"
        "1. Maintain the exact formatting, tables, lists, and markdown syntax.\n"
        "2. Use a refined, polished, and literary Thai writing style suitable for classic novels (like Phanom Tian's style).\n"
        "3. Translate character names and locations back to their correct Thai spellings consistently (e.g. 'Dararai' to 'ดาราราย', 'Ariyawat' to 'อริยวัตร', 'Khattiya' to 'ขัตติยะ', 'Apassara' to 'อภัสรา', 'Tuwu' to 'ตู้วู').\n"
        "4. Output ONLY the translated Thai markdown text. Do not include any notes, introductions, or markdown code blocks wrapping the output."
    )
    
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": english_text}
        ]
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=body, timeout=120)
        if response.status_code != 200:
            raise Exception(f"OpenRouter API Error {response.status_code}: {response.text}")
            
        res_json = response.json()
        choices = res_json.get("choices", [])
        if not choices:
            raise Exception(f"Invalid API response: {json.dumps(res_json)}")
            
        translated = choices[0].get("message", {}).get("content", "").strip()
        return translated
    except Exception as e:
        raise Exception(f"Translation API request failed: {e}")


def run_translation_pipeline(project_dir: str, prefix: str, model_id: str = DEFAULT_MODEL) -> dict:
    """Translates all raw transcripts from Thai to English, utilizing cache."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {"status": "error", "message": "OPENROUTER_API_KEY environment variable is required."}
        
    raw_dir = os.path.join(project_dir, "raw")
    en_dir = os.path.join(raw_dir, "en")
    os.makedirs(en_dir, exist_ok=True)
    
    name_mappings = get_name_mappings(project_dir, prefix)
    print(f"Loaded bilingual name mappings: {name_mappings}")
    
    # Load translation cache state
    cache_path = os.path.join(project_dir, f"{prefix}_translation_state.json")
    cache = load_json(cache_path)
    if "translated_files" not in cache:
        cache["translated_files"] = {}
        
    translated_count = 0
    skipped_count = 0
    
    # Scan raw files
    import glob
    pattern = os.path.join(raw_dir, f"{prefix}_EP*.txt")
    raw_files = sorted(glob.glob(pattern))
    
    if not raw_files:
        return {"status": "error", "message": f"No raw files found matching '{prefix}_EP*.txt' in {raw_dir}"}
        
    results = []
    
    for fpath in raw_files:
        filename = os.path.basename(fpath)
        # Extract episode identifier like EP001
        ep_match = os.path.basename(fpath).replace(f"{prefix}_", "").replace(".txt", "")
        
        dest_filename = f"{prefix}_{ep_match}_en.txt"
        dest_path = os.path.join(en_dir, dest_filename)
        
        current_hash = calculate_file_hash(fpath)
        cached_hash = cache["translated_files"].get(ep_match, {}).get("raw_hash", "")
        
        # Check if cache is valid and file exists
        if current_hash and current_hash == cached_hash and os.path.exists(dest_path):
            print(f"Episode {ep_match} translation is cached. Skipping.")
            results.append({"episode": ep_match, "status": "cached", "path": dest_path})
            skipped_count += 1
            continue
            
        print(f"Translating {filename} to English...")
        with open(fpath, "r", encoding="utf-8") as f:
            thai_content = f.read()
            
        try:
            english_content = translate_thai_to_english(api_key, thai_content, name_mappings, model_id)
            
            with open(dest_path, "w", encoding="utf-8") as out_f:
                out_f.write(english_content)
                
            # Update cache
            cache["translated_files"][ep_match] = {
                "raw_hash": current_hash,
                "translated_path": dest_path
            }
            write_json(cache_path, cache)
            
            results.append({"episode": ep_match, "status": "translated", "path": dest_path})
            translated_count += 1
            print(f"Successfully translated {filename} to {dest_filename}")
        except Exception as e:
            print(f"[ERROR] Failed to translate {filename}: {e}")
            results.append({"episode": ep_match, "status": "error", "error": str(e)})
            
    return {
        "status": "ok",
        "translated_count": translated_count,
        "skipped_count": skipped_count,
        "results": results
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: python translate_raw.py <project_dir> <prefix>")
        sys.exit(1)
        
    project_dir = sys.argv[1]
    prefix = sys.argv[2]
    
    res = run_translation_pipeline(project_dir, prefix)
    print(f"Translation complete: {json.dumps(res, indent=2)}")

if __name__ == "__main__":
    main()
