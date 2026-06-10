# SA Lore — Chapter Lore-Matching (v3.7)

**Role:** Analyze ONE chapter's extracted micro-facts against the book's global lore. Match this chapter against known clues, arc markers, and trackable lore elements.

## ⚠️ CRITICAL TOOL RESTRICTIONS
- Do NOT use any search_files, grep_search, list_dir, or database tools.
- Do NOT search the repository or browse files. Your context is limited ONLY to the inputs provided.

## Schema — EXACT FIELD NAMES

```json
{
  "chapter_id": "EP002",
  "clues_matched": [
    {"clue_id": "CLUE_001",
     "description": "Who is the 'black gentleman'?",
     "chapter_evidence": "Jurgen defends the Prince of Darkness to a monk",
     "chapter_progress": "Introduced — the black gentleman thanks Jurgen",
     "match_evidence": "A black gentleman salutes Jurgen and thanks him",
     "confidence": "high",
     "in_scene_id": "SC-002"}
  ],
  "arc_markers": [
    {"marker_id": "ARC-001", "arc_name": "Jurgen's Journey",
     "chapter_progress": "Jurgen begins his quest: inciting incident",
     "significance": "The comfortable life is disrupted",
     "in_scene_id": "SC-002"}
  ],
  "cross_chapter_connections": [
    {"connection_id": "CON-001", "from_entity": "Jurgen", "to_entity": "Koshchei",
     "connection_type": "meeting",
     "description": "First meeting between Jurgen and the black gentleman",
     "in_scene_id": "SC-002"}
  ],
  "lore_discoveries": [
    {"discovery_id": "DSC-001",
     "description": "The black gentleman is associated with Koshchei",
     "source": "Chapter text — the black gentleman's appearance and actions match Koshchei",
     "evidence_quote": "a tall black gentleman who saluted Jurgen...",
     "in_scene_id": "SC-002"}
  ]
}
```

## ⚠️ Critical Rules

1. **Scope:** Use ONLY the part1_output, global_lore_excerpt, and previous_chapters_summary provided. Do NOT invent connections.
2. **Evidence required:** Every `clues_matched` entry MUST include `match_evidence` — a direct quote or paraphrase FROM THIS CHAPTER
3. **Minimum thresholds:** 2+ clues_matched for lore-heavy chapters, 1+ arc_marker for pivotal chapters
4. **No null values** — Use `[]` for empty arrays
5. **No project-wide search** — Your data is in the provided inputs only

## ⚠️ STRICT SCHEMA COMPLIANCE RULES:
You MUST use these exact field names. Do NOT rename or translate them:
- Use `connection_id` (NOT `connection`, NOT `id`)
- Use `description` in `lore_discoveries` (NOT `discovery`)
- Use `source` in `lore_discoveries` (NOT `revealed_by`)
- Use `evidence_quote` in `lore_discoveries` (NOT `quote`, NOT `evidence`)
- Ensure all entries contain `in_scene_id` referencing a valid scene.

## Usage

- `{part1_output}` = the SA Combined JSON for this chapter
- `{global_lore_excerpt}` = relevant clues/characters from global_lore.json for this chapter range
- `{previous_chapters_summary}` = auto-generated summaries of previous 2-3 chapters

Set `chapter_id` to exactly `EP{NNN}`.