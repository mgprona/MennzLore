"""
tests/test_normalize_sa_json.py
===============================
Unit tests for engine/merge_to_micro_facts.normalize_sa_json.
Tests safety net normalization of subagent output against schema mismatches.

Run:
    python -m pytest tests/ -v
or:
    python tests/test_normalize_sa_json.py
"""
import sys
import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR.parent))

from engine.merge_to_micro_facts import normalize_sa_json

class TestNormalizeSaJson(unittest.TestCase):
    def test_normalize_empty(self):
        data = {}
        normalized = normalize_sa_json(data)
        self.assertEqual(normalized, {})

    def test_normalize_scene_details_missing_order(self):
        # 1. scene_details[].order (missing integer)
        data = {
            "scene_details": [
                {"scene_id": "SC-001", "description": "Scene 1 without order"},
                {"scene_id": "SC-002", "order": None, "description": "Scene 2 with None order"},
                {"scene_id": "SC-003", "order": 99, "description": "Scene 3 with order"}
            ]
        }
        normalized = normalize_sa_json(data)
        scenes = normalized["scene_details"]
        self.assertEqual(scenes[0]["order"], 1)
        self.assertEqual(scenes[1]["order"], 2)
        self.assertEqual(scenes[2]["order"], 99)

    def test_normalize_dialogue_summaries_missing_quotes_and_id(self):
        # 2 & 3. dialogue_summaries (missing key_quotes, dialogue_id)
        data = {
            "dialogue_summaries": [
                {
                    "speaker": "Alice",
                    "listener": "Cheshire Cat",
                    "summary": "Alice asks for directions"
                }
            ]
        }
        normalized = normalize_sa_json(data)
        diags = normalized["dialogue_summaries"]
        self.assertEqual(diags[0]["dialogue_id"], "DI-001")
        self.assertEqual(diags[0]["key_quotes"], [])
        self.assertEqual(diags[0]["participants"], ["Alice", "Cheshire Cat"])

    def test_normalize_lore_discoveries_renamed_fields(self):
        # 4 & 5 & 7. lore_discoveries (discovery -> description, revealed_by -> source, missing evidence_quote)
        data = {
            "lore_discoveries": [
                {
                    "discovery": "The Red Queen is quick-tempered",
                    "revealed_by": "Alice's observation"
                }
            ]
        }
        normalized = normalize_sa_json(data)
        lores = normalized["lore_discoveries"]
        self.assertEqual(lores[0]["discovery_id"], "LD-001")
        self.assertEqual(lores[0]["description"], "The Red Queen is quick-tempered")
        self.assertEqual(lores[0]["source"], "Alice's observation")
        self.assertEqual(lores[0]["evidence_quote"], "")
        self.assertNotIn("discovery", lores[0])
        self.assertNotIn("revealed_by", lores[0])

    def test_normalize_cross_chapter_connections_renamed_fields(self):
        # 6. cross_chapter_connections[].connection_id (missing, use connection)
        data = {
            "cross_chapter_connections": [
                {
                    "connection": "CC-LINK-1",
                    "description": "Looking-glass world mirrors Wonderland events"
                }
            ]
        }
        normalized = normalize_sa_json(data)
        conns = normalized["cross_chapter_connections"]
        self.assertEqual(conns[0]["connection_id"], "CC-LINK-1")
        self.assertEqual(conns[0]["description"], "Looking-glass world mirrors Wonderland events")
        self.assertNotIn("connection", conns[0])

if __name__ == "__main__":
    unittest.main(verbosity=2)
