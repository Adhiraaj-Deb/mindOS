"""
core/file_utils.py — Backward-compat shim.

Re-exports VAULT_PATH and utilities from config.py so that
existing code (graph_view.py etc.) that imports from here continues to work.
"""
import os
import glob
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import VAULT_DIR, TASKS_FILE, IDEAS_FILE, MEMORY_FILE, REMINDERS_FILE

# Keep the old name for backward compat (graph_view.py uses VAULT_PATH)
VAULT_PATH = VAULT_DIR


def get_all_md_files() -> list:
    """Return all .md files in the vault, excluding system dirs."""
    files = glob.glob(os.path.join(VAULT_PATH, "**", "*.md"), recursive=True)
    skip  = ("chroma_db", ".venv", "__pycache__", ".obsidian")
    return [f for f in files if not any(s in f for s in skip)]


def read_file(path: str) -> str:
    """Safely read a file, returning empty string if missing."""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""


def append_to_file(path: str, text: str) -> None:
    """Append a line to a file, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + text)
