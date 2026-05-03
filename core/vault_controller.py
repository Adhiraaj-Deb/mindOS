"""
core/vault_controller.py — Full CRUD control over the MindOS Obsidian vault.

Capabilities:
  - Read any file
  - Write / create any file (creates parent dirs automatically)
  - Append to any file
  - Delete any file
  - Create / delete folders
  - List files in a folder
  - Search all vault files for a keyword
"""
import os
import shutil
import glob
from datetime import datetime

from .file_utils import VAULT_PATH


# ── Safety boundary ────────────────────────────────────────────────────────────

def _safe(path: str) -> str:
    """Resolve path, ensuring it stays inside VAULT_PATH."""
    resolved = os.path.realpath(os.path.join(VAULT_PATH, path))
    vault_real = os.path.realpath(VAULT_PATH)
    if not resolved.startswith(vault_real):
        raise PermissionError(f"Access denied: '{path}' is outside the vault.")
    return resolved


# ── READ ───────────────────────────────────────────────────────────────────────

def read_note(relative_path: str) -> str:
    """Read a vault file by relative path. Returns content or empty string."""
    fp = _safe(relative_path)
    if not os.path.exists(fp):
        return ""
    with open(fp, encoding="utf-8") as f:
        return f.read()


def list_folder(relative_path: str = "") -> list[str]:
    """List all files/folders in a vault directory. Returns relative paths."""
    fp = _safe(relative_path)
    if not os.path.isdir(fp):
        return []
    items = []
    for entry in sorted(os.listdir(fp)):
        full = os.path.join(fp, entry)
        rel  = os.path.relpath(full, VAULT_PATH)
        tag  = "[DIR]" if os.path.isdir(full) else "[FILE]"
        items.append(f"{tag} {rel}")
    return items


def list_all_md() -> list[str]:
    """Return all .md file paths relative to vault root."""
    files = glob.glob(os.path.join(VAULT_PATH, "**", "*.md"), recursive=True)
    skip = {"chroma_db", ".venv", ".obsidian", "__pycache__"}
    result = []
    for f in files:
        parts = f.replace(VAULT_PATH, "").split(os.sep)
        if not any(s in parts for s in skip):
            result.append(os.path.relpath(f, VAULT_PATH))
    return sorted(result)


def search_vault(keyword: str, case_sensitive: bool = False) -> list[dict]:
    """Search all vault .md files for a keyword. Returns [{file, line_no, line}]."""
    results = []
    kw = keyword if case_sensitive else keyword.lower()
    for rel_path in list_all_md():
        fp = os.path.join(VAULT_PATH, rel_path)
        try:
            with open(fp, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    haystack = line if case_sensitive else line.lower()
                    if kw in haystack:
                        results.append({
                            "file":    rel_path,
                            "line_no": i,
                            "line":    line.rstrip(),
                        })
        except Exception:
            continue
    return results


# ── WRITE / CREATE ─────────────────────────────────────────────────────────────

def write_note(relative_path: str, content: str, overwrite: bool = True) -> str:
    """
    Write content to a vault file. Creates parent directories as needed.
    Returns the relative path written to.
    """
    fp = _safe(relative_path)
    if os.path.exists(fp) and not overwrite:
        return f"ERROR: '{relative_path}' already exists. Use overwrite=True to replace it."
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
    return relative_path


def append_note(relative_path: str, text: str) -> str:
    """Append a line to a vault file (creates if missing)."""
    fp = _safe(relative_path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "a", encoding="utf-8") as f:
        f.write("\n" + text)
    return relative_path


def create_folder(relative_path: str) -> str:
    """Create a directory inside the vault."""
    fp = _safe(relative_path)
    os.makedirs(fp, exist_ok=True)
    return relative_path


# ── DELETE ─────────────────────────────────────────────────────────────────────

def delete_note(relative_path: str) -> str:
    """Delete a vault file. Returns confirmation string."""
    fp = _safe(relative_path)
    if not os.path.exists(fp):
        return f"ERROR: '{relative_path}' does not exist."
    if os.path.isdir(fp):
        return f"ERROR: '{relative_path}' is a directory. Use delete_folder() instead."
    os.remove(fp)
    return f"Deleted: {relative_path}"


def delete_folder(relative_path: str, force: bool = False) -> str:
    """
    Delete a vault directory.
    If force=False and folder is non-empty, returns an error.
    """
    fp = _safe(relative_path)
    if not os.path.isdir(fp):
        return f"ERROR: '{relative_path}' is not a directory."
    if force:
        shutil.rmtree(fp)
        return f"Deleted folder (with contents): {relative_path}"
    else:
        try:
            os.rmdir(fp)  # Only works if empty
            return f"Deleted empty folder: {relative_path}"
        except OSError:
            return f"ERROR: '{relative_path}' is not empty. Use force=True to delete anyway."


# ── RENAME / MOVE ──────────────────────────────────────────────────────────────

def rename_note(old_path: str, new_path: str) -> str:
    """Move/rename a vault file."""
    old_fp = _safe(old_path)
    new_fp = _safe(new_path)
    if not os.path.exists(old_fp):
        return f"ERROR: '{old_path}' does not exist."
    os.makedirs(os.path.dirname(new_fp), exist_ok=True)
    shutil.move(old_fp, new_fp)
    return f"Moved: {old_path} → {new_path}"
