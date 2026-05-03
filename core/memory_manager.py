"""
core/memory_manager.py — ChromaDB sync, RAG retrieval, and vault readers.

Owns:
  - Reminder dataclass + markdown parser
  - sync_vault()     : incremental ChromaDB re-embedding
  - retrieve()       : semantic search → single context string
  - get_all_reminders(), get_all_tasks(), get_all_ideas(), get_memories()
    → parsed data for UI views
"""
import os
import re
import json
import glob
from datetime import datetime, date, timedelta
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    VAULT_DIR, TASKS_FILE, IDEAS_FILE, MEMORY_FILE, REMINDERS_FILE,
    CHROMA_DIR, MTIMES_FILE, RAG_TOP_K,
)


# ── Reminder data class ───────────────────────────────────────────────────────────

class Reminder:
    """Represents a single reminder entry."""

    def __init__(self, text: str, dt: datetime,
                 all_day: bool = False, done: bool = False):
        self.text    = text.strip()
        self.dt      = dt
        self.all_day = all_day
        self.done    = done

    @property
    def is_past(self) -> bool:
        if self.all_day:
            return self.dt.date() < date.today()
        return self.dt < datetime.now()

    @property
    def is_today(self) -> bool:
        return self.dt.date() == date.today()

    def to_md_line(self) -> str:
        stamp    = self.dt.strftime("%Y-%m-%d") if self.all_day else self.dt.strftime("%Y-%m-%d %H:%M")
        done_tag = " [DONE]" if self.done else ""
        return f"* [{stamp}]{done_tag} {self.text}"


# ── Reminder line parser ──────────────────────────────────────────────────────────

_REMINDER_RE = re.compile(
    r"^\*\s*\[(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\]"
    r"(\s*\[DONE\])?\s+(.+)$"
)


def _parse_reminder_line(line: str) -> Optional[Reminder]:
    m = _REMINDER_RE.match(line.strip())
    if not m:
        return None
    date_str, time_str, done_tag, text = m.group(1), m.group(2), m.group(3), m.group(4)
    all_day = time_str is None
    dt      = (datetime.strptime(date_str, "%Y-%m-%d")
               if all_day
               else datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
    return Reminder(text=text, dt=dt, all_day=all_day, done=bool(done_tag and "DONE" in done_tag))


# ── Vault readers ─────────────────────────────────────────────────────────────────

def get_all_reminders() -> list:
    """Return all Reminder objects, sorted by datetime."""
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
    if not os.path.exists(REMINDERS_FILE):
        return []
    reminders = []
    try:
        with open(REMINDERS_FILE, encoding="utf-8") as f:
            for line in f:
                r = _parse_reminder_line(line)
                if r:
                    reminders.append(r)
    except Exception:
        pass
    return sorted(reminders, key=lambda r: r.dt)


def get_all_tasks() -> list:
    """Return tasks as list of {text, done, high, due} dicts."""
    if not os.path.exists(TASKS_FILE):
        return []
    tasks = []
    try:
        with open(TASKS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not (line.startswith("- [") or line.startswith("* [")):
                    continue
                done = line[3:4].lower() == "x"
                rest = re.sub(r"^[-*]\s*\[[xX\s]\]\s*", "", line).strip()
                high = False
                pm   = re.match(r"\[(high|normal|low)\]\s*", rest, re.IGNORECASE)
                if pm:
                    high = pm.group(1).lower() == "high"
                    rest = rest[pm.end():]
                due  = ""
                dm   = re.search(r"\s*\u2014\s*due:\s*(.+)$", rest)
                if dm:
                    due  = dm.group(1).strip()
                    rest = rest[:dm.start()].strip()
                if rest.strip():
                    tasks.append({"text": rest.strip(), "done": done, "high": high, "due": due})
    except Exception:
        pass
    return tasks


def get_all_ideas() -> list:
    """Return ideas as a list of strings (newest last)."""
    if not os.path.exists(IDEAS_FILE):
        return []
    ideas = []
    try:
        with open(IDEAS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("* "):
                    idea = line[2:].strip()
                    if idea:
                        ideas.append(idea)
    except Exception:
        pass
    return ideas


def get_memories() -> list:
    """Return memories as list of {date, text} dicts."""
    if not os.path.exists(MEMORY_FILE):
        return []
    memories = []
    try:
        with open(MEMORY_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("* "):
                    continue
                m = re.match(r"\*\s*\[(\d{4}-\d{2}-\d{2})\]\s*(.*)", line)
                if m:
                    memories.append({"date": m.group(1), "text": m.group(2)})
                else:
                    text = line[2:].strip()
                    if text:
                        memories.append({"date": "", "text": text})
    except Exception:
        pass
    return memories


# ── Backward-compat aliases (used by existing UI views) ──────────────────────────

def get_tasks()    -> list: return get_all_tasks()
def get_ideas()    -> list: return get_all_ideas()
def load_reminders() -> list: return get_all_reminders()


# ── ChromaDB sync and retrieval ───────────────────────────────────────────────────

_embedding_model  = None
_chroma_collection = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def _get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        _chroma_collection = client.get_or_create_collection(name="mindos_memory")
    return _chroma_collection


def _load_mtimes() -> dict:
    if os.path.exists(MTIMES_FILE):
        try:
            with open(MTIMES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_mtimes(mtimes: dict) -> None:
    os.makedirs(os.path.dirname(MTIMES_FILE), exist_ok=True)
    with open(MTIMES_FILE, "w", encoding="utf-8") as f:
        json.dump(mtimes, f)


def _chunk_text(text: str, max_words: int = 300) -> list:
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


def sync_vault(forced: bool = False) -> None:
    """
    Incrementally re-embed changed vault files into ChromaDB.
    Set forced=True to force re-embed of ALL files (e.g. after major vault changes).
    """
    try:
        mtimes     = _load_mtimes()
        md_files   = glob.glob(os.path.join(VAULT_DIR, "**", "*.md"), recursive=True)
        collection = _get_collection()
        model      = _get_embedding_model()
        updated    = False
        _skip      = ("chroma_db", ".venv", "__pycache__", ".obsidian", 
                      "08_Reminders", "02_Tasks", "07_Memory", "01_Daily", "00_Dashboard")

        # Prune deleted files from ChromaDB
        live_paths = set(fp for fp in md_files if not any(s in fp for s in _skip))
        for fp in list(mtimes.keys()):
            if fp not in live_paths:
                try:
                    collection.delete(where={"source": fp})
                except Exception:
                    pass
                del mtimes[fp]
                updated = True

        # Embed new or changed files
        for fp in md_files:
            if any(s in fp for s in _skip):
                continue
            mtime = os.path.getmtime(fp)
            if not forced and mtime <= mtimes.get(fp, 0):
                continue

            # Remove old chunks for this file
            try:
                collection.delete(where={"source": fp})
            except Exception:
                pass

            try:
                with open(fp, encoding="utf-8") as f:
                    content = f.read()
                if content.strip():
                    chunks     = _chunk_text(content)
                    embeddings = model.encode(chunks).tolist()
                    rel_path   = os.path.relpath(fp, VAULT_DIR).replace("\\", "/")
                    collection.upsert(
                        documents=chunks,
                        embeddings=embeddings,
                        metadatas=[{"source": fp, "rel_path": rel_path}] * len(chunks),
                        ids=[f"doc_{os.path.basename(fp)}_{int(mtime)}_{i}"
                             for i in range(len(chunks))],
                    )
            except Exception:
                continue

            mtimes[fp] = mtime
            updated    = True

        if updated:
            _save_mtimes(mtimes)
    except Exception as e:
        print(f"sync_vault error: {e}")


def retrieve(query: str, top_k: int = RAG_TOP_K) -> str:
    """
    Query ChromaDB with semantic search.
    Returns annotated context: each chunk is prefixed with its source note path.
    """
    try:
        model  = _get_embedding_model()
        col    = _get_collection()
        emb    = model.encode([query]).tolist()
        res    = col.query(query_embeddings=emb, n_results=min(top_k, col.count()))
        docs   = res.get("documents", [[]])[0]
        metas  = res.get("metadatas", [[]])[0]

        seen, chunks = set(), []
        for doc, meta in zip(docs, metas):
            if not doc or doc in seen:
                continue
            seen.add(doc)
            src = meta.get("rel_path") or meta.get("source", "vault")
            chunks.append(f"[Source: {src}]\n{doc}")

        return "\n\n---\n\n".join(chunks)
    except Exception:
        return ""
