import os
import glob
import json
from typing import List, Dict, Any
from engine.rag_memory import LocalVectorMemory

class SagaVectorMemory(LocalVectorMemory):
    def load_saga_facts(self, saga_dir: str, volumes: list):
        """
        Load facts from multiple volumes in the saga.
        Supports both dicts and VolumeConfig objects in the 'volumes' list.
        """
        self.documents = []
        for vol in volumes:
            # Support both dict and VolumeConfig object
            if hasattr(vol, "project_dir"):
                p_dir = vol.project_dir
                prefix = vol.prefix
                vol_id = vol.volume_id
                title = vol.title
            else:
                p_dir = vol.get("project_dir")
                prefix = vol.get("prefix")
                vol_id = vol.get("volume_id")
                title = vol.get("title", prefix)
            
            # Resolve relative project_dir if needed
            if not os.path.isabs(p_dir):
                p_dir = os.path.abspath(os.path.join(saga_dir, p_dir))

            mf_dir = os.path.join(p_dir, "micro_facts")
            if not os.path.isdir(mf_dir):
                mf_dir = os.path.join(p_dir, "analysis", "micro_facts")

            if not os.path.isdir(mf_dir):
                print(f"[WARNING] Micro facts directory not found for volume {vol_id} at {mf_dir}")
                continue

            pattern = os.path.join(mf_dir, f"{prefix}_EP*_micro_facts.json")
            for fpath in sorted(glob.glob(pattern)):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    ep_id = data.get("chapter_id", "")
                    
                    # 1. Index plot points
                    for kpp in data.get("key_plot_points", []):
                        self.add_document(
                            text=f"[{title}] Episode {ep_id}: {kpp.get('description')}",
                            metadata={"type": "plot_point", "ep": ep_id, "id": kpp.get("point_id"), "volume": vol_id}
                        )
                    # 2. Index character behaviors
                    for beh in data.get("character_behaviors", []):
                        self.add_document(
                            text=f"[{title}] Character {beh.get('character')} in Episode {ep_id} scene {beh.get('in_scene_id')}: {beh.get('behavior')}",
                            metadata={"type": "behavior", "ep": ep_id, "character": beh.get("character"), "volume": vol_id}
                        )
                    # 3. Index items of interest
                    for item in data.get("items_of_interest", []):
                        self.add_document(
                            text=f"[{title}] Item '{item.get('item')}' in Episode {ep_id}: {item.get('description')} (Role: {item.get('role_in_chapter')})",
                            metadata={"type": "item", "ep": ep_id, "item": item.get("item"), "volume": vol_id}
                        )
                    # 4. Index dialogue summaries
                    for dlg in data.get("dialogue_summaries", []):
                        self.add_document(
                            text=f"[{title}] Dialogue between {', '.join(dlg.get('participants', []))} in Episode {ep_id} regarding '{dlg.get('topic')}': {dlg.get('summary')}",
                            metadata={"type": "dialogue", "ep": ep_id, "topic": dlg.get("topic"), "volume": vol_id}
                        )
                    # 5. Index lore discoveries
                    for disc in data.get("lore_discoveries", []):
                        self.add_document(
                            text=f"[{title}] Lore Discovery in Episode {ep_id}: {disc.get('description')} (Evidence: \"{disc.get('evidence_quote')}\")",
                            metadata={"type": "discovery", "ep": ep_id, "id": disc.get("discovery_id"), "volume": vol_id}
                        )
                except Exception as e:
                    print(f"[WARNING] Failed to index facts from {fpath}: {e}")

        self.build_index()

    def query_cross_volume(self, query_text: str, limit: int = 5, vol_filter: str = None) -> list:
        """
        Query across all loaded volumes with an optional volume filter.
        """
        results = self.query(query_text, limit=limit * 3)  # Query more to allow filtering
        if vol_filter:
            results = [doc for doc in results if doc["metadata"].get("volume") == vol_filter]
        return results[:limit]

    def query_character_history(self, char_name: str) -> list:
        """
        Retrieves all lore facts referring to a character across the saga.
        """
        return self.query_cross_volume(char_name, limit=10)

def build_cross_volume_context(saga_dir: str, volumes: list, query: str, limit: int = 5) -> str:
    """
    Helper function to query all volume facts and construct a prompt injection context block.
    """
    mem = SagaVectorMemory()
    mem.load_saga_facts(saga_dir, volumes)
    results = mem.query_cross_volume(query, limit)
    
    if not results:
        return ""
        
    lines = [
        "### RELEVANT HISTORY FROM PREVIOUS VOLUMES:",
        ""
    ]
    for idx, doc in enumerate(results, 1):
        lines.append(f"({idx}) {doc['text']}")
    return "\n".join(lines)
