# backend/memory.py
"""
Short-term and long-term memory management.
Short-term: kept in memory per session (in-memory dict).
Long-term: persisted to JSON (long_memory.json) and used in retrieval.
"""

import time
from pathlib import Path
from typing import Dict, Any, List
from .config import LONG_MEMORY_PATH
from .utils import load_json, save_json, ensure_dir

ensure_dir(LONG_MEMORY_PATH.parent)

# Short-term memory structure (session_id -> list of messages)
short_term_memories: Dict[str, List[Dict[str, Any]]] = {}

def create_session(session_id: str):
    if session_id not in short_term_memories:
        short_term_memories[session_id] = []

def add_to_short_term(session_id: str, role: str, text: str):
    create_session(session_id)
    short_term_memories[session_id].append({
        "timestamp": int(time.time()),
        "role": role,
        "text": text
    })

def get_short_term(session_id: str):
    return short_term_memories.get(session_id, [])

# Long-term memory persisted to LONG_MEMORY_PATH
def append_long_term(entry: Dict[str, Any]):
    data = load_json(LONG_MEMORY_PATH, default=[])
    data = data or []
    data.append(entry)
    save_json(LONG_MEMORY_PATH, data)

def load_long_term():
    return load_json(LONG_MEMORY_PATH, default=[])
