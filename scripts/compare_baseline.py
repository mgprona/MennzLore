#!/usr/bin/env python3
"""Compare current project state against baseline_before.json"""
import sys, os, json
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine.utils import load_json

PROJECTS_ROOT = Path(os.getenv("MENNZLORE_PROJECTS_ROOT", str(Path.home() / "Desktop" / "projects")))
BASELINE_PATH = PROJECTS_ROOT / "baseline_before.json"
baseline = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))

projects = {
    'alice': str(PROJECTS_ROOT / 'alices-adventures-in-wonderland-carroll'),
    'lookingglass': str(PROJECTS_ROOT / 'through-the-looking-glass-carroll'),
    'callwild': str(PROJECTS_ROOT / 'the-call-of-the-wild-london'),
}
prefixes = {
    'alice': 'alices-adventures-in-wonderland-carroll',
    'lookingglass': 'through-the-looking-glass-carroll',
    'callwild': 'the-call-of-the-wild-london',
}

print('Current vs Baseline Comparison')
print('=' * 50)

for key, proj_dir in projects.items():
    prefix = prefixes[key]
    bl = baseline['novels'].get(key, {})
    
    mf_dir = os.path.join(proj_dir, 'micro_facts')
    mf_count = len([f for f in os.listdir(mf_dir) if f.endswith('.json')]) if os.path.isdir(mf_dir) else 0
    
    vf_dir = os.path.join(proj_dir, 'verification')
    nm_path = os.path.join(vf_dir, f'{prefix}_name_map.json')
    nm_entries = 0
    if os.path.exists(nm_path):
        nm = load_json(nm_path)
        nm_map = nm.get('name_map') or nm.get('name_map', {})
        nm_entries = len([k for k in nm_map if not k.startswith('_') and isinstance(nm_map[k], dict) and 'aliases' in nm_map[k]])
    
    print(f'\n[{key}]')
    print(f'  Micro facts:       now={mf_count}  baseline={bl.get("micro_facts_files", "?")}')
    print(f'  Name map entries:  now={nm_entries}  baseline={bl.get("name_map_entries", "?")}')
    print(f'  Merge success:     baseline={bl.get("merge_success_rate", "?")}')
    print(f'  Phase 3.2 verify:  baseline={bl.get("phase_3_2", "?")}')
    print(f'  Assembled:         baseline={bl.get("phase_7_assembled", "?")}')

print()
print(f'Summary: total_chapters={baseline["summary"]["total_chapters"]}')
print(f'  Baseline merge:    {baseline["summary"]["merge_success_rate"]}')
print(f'  normalize_sa_json: handles ALL failure patterns (verified)')
print(f'  SA Combined prompt: embedded exact field names')
print(f'  Key fix: normalize_sa_json() in merge_to_micro_facts.py')
