"""
BlenderNanoBanana - JSON Serialization Utilities
"""

import json
import os
from typing import Any


def load_json(path: str) -> Any:
    """Load and parse a JSON file. Returns None if file missing."""
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any, pretty: bool = True) -> None:
    """Save data to a JSON file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, ensure_ascii=False)


def to_json_str(data: Any, pretty: bool = False) -> str:
    if pretty:
        return json.dumps(data, indent=2, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def from_json_str(s: str) -> Any:
    return json.loads(s)
