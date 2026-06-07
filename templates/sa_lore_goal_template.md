# ===== DO NOT SHORTEN THIS TEMPLATE =====
# Replace {EP_ID}, {PART1_JSON}, {GLOBAL_LORE_EXCERPT} only.

## Task: SA Lore for {EP_ID}

Match the chapter micro-facts against global lore. Return valid JSON.

### EXACT FIELD NAMES:

```json
{
  "chapter_id": "{EP_ID}",
  "clues_matched": [
    {"clue_id": "CLUE_001", "description": "...", "chapter_evidence": "...", "chapter_progress": "...", "match_evidence": "...", "confidence": "high|medium|low", "in_scene_id": "..."}
  ],
  "arc_markers": [
    {"marker_id": "ARC-001", "arc_name": "...", "chapter_progress": "...", "significance": "...", "in_scene_id": "..."}
  ],
  "cross_chapter_connections": [
    {"connection_id": "CON-001", "from_entity": "...", "to_entity": "...", "connection_type": "meeting|reference|object_transfer", "description": "...", "in_scene_id": "..."}
  ],
  "lore_discoveries": [
    {"discovery_id": "DSC-001", "description": "...", "source": "...", "evidence_quote": "...", "in_scene_id": "..."}
  ]
}
```

### FIELD RULES
- `clues_matched[].match_evidence` — NOT `evidence`
- Every clue must have a match_evidence quote from this chapter
- No `null` — use []
- Only match clues that actually appear in this chapter

### INPUT: Combined SA (Part 1)

```json
{PART1_JSON}
```

### INPUT: Global Lore Excerpt

{_global_lore_excerpt}