import os
from typing import List, Dict, Any
from engine.utils import load_json

class VolumeConfig:
    def __init__(self, volume_id: str, title: str, year: int, gutenberg_id: str, prefix: str, project_dir: str):
        self.volume_id = volume_id
        self.title = title
        self.year = year
        self.gutenberg_id = gutenberg_id
        self.prefix = prefix
        # We will store the absolute path here
        self.project_dir = project_dir

    def to_dict(self) -> Dict[str, Any]:
        return {
            "volume_id": self.volume_id,
            "title": self.title,
            "year": self.year,
            "gutenberg_id": self.gutenberg_id,
            "prefix": self.prefix,
            "project_dir": self.project_dir
        }

class SagaConfig:
    def __init__(self, saga_id: str, saga_title: str, author: str, lore_handoff_mode: str, volumes: List[VolumeConfig]):
        self.saga_id = saga_id
        self.saga_title = saga_title
        self.author = author
        self.lore_handoff_mode = lore_handoff_mode
        self.volumes = volumes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "saga_id": self.saga_id,
            "saga_title": self.saga_title,
            "author": self.author,
            "lore_handoff_mode": self.lore_handoff_mode,
            "volumes": [vol.to_dict() for vol in self.volumes]
        }

def load_saga_config(saga_dir: str) -> SagaConfig:
    """
    Load and parse saga_config.json from saga_dir, and resolve paths relative to saga_dir.
    """
    config_path = os.path.join(saga_dir, "saga_config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Saga config file not found at: {config_path}")

    data = load_json(config_path)
    if not data:
        raise ValueError(f"Saga config at {config_path} is empty or invalid JSON")

    # Required fields
    required_saga_fields = ["saga_id", "saga_title", "author", "volumes"]
    for field in required_saga_fields:
        if field not in data:
            raise KeyError(f"Missing required saga config field: '{field}'")

    volumes_data = data["volumes"]
    volumes: List[VolumeConfig] = []
    
    for idx, vol_data in enumerate(volumes_data):
        required_vol_fields = ["volume_id", "title", "year", "gutenberg_id", "prefix", "project_dir"]
        for field in required_vol_fields:
            if field not in vol_data:
                raise KeyError(f"Missing required field '{field}' in volume at index {idx}")

        # Resolve project_dir relative to saga_dir
        raw_project_dir = vol_data["project_dir"]
        if os.path.isabs(raw_project_dir):
            abs_project_dir = raw_project_dir
        else:
            abs_project_dir = os.path.abspath(os.path.join(saga_dir, raw_project_dir))

        vol = VolumeConfig(
            volume_id=vol_data["volume_id"],
            title=vol_data["title"],
            year=int(vol_data["year"]),
            gutenberg_id=str(vol_data["gutenberg_id"]),
            prefix=vol_data["prefix"],
            project_dir=abs_project_dir
        )
        volumes.append(vol)

    return SagaConfig(
        saga_id=data["saga_id"],
        saga_title=data["saga_title"],
        author=data["author"],
        lore_handoff_mode=data.get("lore_handoff_mode", "compressed"),
        volumes=volumes
    )
