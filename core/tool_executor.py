"""
core/tool_executor.py — ALL vault-write operations for MindOS.

This is the ONLY module that writes to vault files.
Every function accepts typed parameters, writes atomically,
and returns a human-readable confirmation string.
Never fails silently.
"""
import os
import re
from datetime import datetime, timedelta
from datetime import date as DateType
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TASKS_FILE, IDEAS_FILE, MEMORY_FILE, REMINDERS_FILE

try:
    from dateutil import parser as du_parser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


# ── Low-level file helpers ────────────────────────────────────────────────────────

def _ensure_file(path: str, header: str = "") -> None:
    """Create a file and parent dirs if they don't exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"{header}\n\n" if header else "")


def _safe_append(path: str, line: str) -> None:
    """Atomically append one line to a file."""
    _ensure_file(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + line)
        f.flush()
        os.fsync(f.fileno())


def _read_all(path: str) -> list:
    """Read all lines from a file."""
    _ensure_file(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def _write_all(path: str, lines: list) -> None:
    """Overwrite a file with the given lines."""
    _ensure_file(path)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
        f.flush()
        os.fsync(f.fileno())


# ── Natural language date/time parsing ────────────────────────────────────────────

def parse_natural_date(s: str) -> Optional[DateType]:
    """Convert a natural language date string to a date object."""
    if not s:
        return DateType.today()
    s = s.strip()
    sl = s.lower()

    today = DateType.today()
    if sl == "today":
        return today
    if sl == "tomorrow":
        return today + timedelta(days=1)
    if sl == "yesterday":
        return today - timedelta(days=1)

    days_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    }
    for d_name, d_idx in days_map.items():
        if sl == d_name or sl == f"next {d_name}":
            delta = (d_idx - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return today + timedelta(days=delta)

    if HAS_DATEUTIL:
        try:
            parsed = du_parser.parse(s, default=datetime.now(), dayfirst=False)
            return parsed.date()
        except Exception:
            pass

    for fmt in (
        "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
        "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
        "%B %d", "%b %d",
    ):
        try:
            d = datetime.strptime(s, fmt)
            if d.year == 1900:
                d = d.replace(year=today.year)
            return d.date()
        except ValueError:
            continue
    return None


def parse_natural_time(s: str) -> Optional[tuple]:
    """Convert a natural language time string to (hour, minute) or None for all-day."""
    if not s:
        return None
    sl = s.strip().lower()
    if sl in ("all day", "all-day", "allday", "anytime", ""):
        return None

    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", sl)
    if not m:
        return None

    hour   = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm   = m.group(3) or ""

    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif not ampm and 1 <= hour <= 6:
        # Ambiguous: assume PM (e.g., "remind me at 3" = 3 PM)
        hour += 12

    return (hour, minute)


# ── Tool implementations (only these write to disk) ──────────────────────────────

def save_reminder(task: str, date: str = "", time: str = "all day") -> str:
    """
    Save a reminder to reminders.md.
    Accepts natural language date (e.g. 'tomorrow', 'April 20') and time (e.g. '9am', '14:30').
    """
    try:
        parsed_date = parse_natural_date(date) or DateType.today()
        parsed_time = parse_natural_time(time)

        if parsed_time:
            h, mi = parsed_time
            dt = datetime(parsed_date.year, parsed_date.month, parsed_date.day, h, mi)
            stamp   = dt.strftime("%Y-%m-%d %H:%M")
            t_label = dt.strftime("%I:%M %p")
        else:
            stamp   = parsed_date.strftime("%Y-%m-%d")
            t_label = "all day"

        try:
            d_label = parsed_date.strftime("%A, %B %-d, %Y")
        except ValueError:
            d_label = parsed_date.strftime("%A, %B %d, %Y")

        task = task.strip()
        line = f"* [{stamp}] {task}"
        _safe_append(REMINDERS_FILE, line)

        return (
            f"Reminder saved!\n\n"
            f"  Date:  {d_label}\n"
            f"  Time:  {t_label}\n"
            f"  Note:  {task}"
        )
    except Exception as e:
        return f"Failed to save reminder: {e}"


def add_task(title: str, priority: str = "normal", due_date: str = "") -> str:
    """Add a task to tasks.md."""
    try:
        title = title.strip()
        priority = priority.strip().lower()
        if priority not in ("high", "normal", "low"):
            priority = "normal"
        due_str = f" — due: {due_date.strip()}" if due_date.strip() else ""
        line = f"- [ ] [{priority}] {title}{due_str}"
        _safe_append(TASKS_FILE, line)
        return f"Task added: {title} [{priority} priority]{due_str}"
    except Exception as e:
        return f"Failed to add task: {e}"


def save_memory(fact: str) -> str:
    """Save a fact or piece of information to memory.md."""
    try:
        fact = fact.strip()
        ts   = datetime.now().strftime("%Y-%m-%d")
        line = f"* [{ts}] {fact}"
        _safe_append(MEMORY_FILE, line)
        return f"Saved to memory: {fact}"
    except Exception as e:
        return f"Failed to save memory: {e}"


def add_idea(content: str, tags: list = None) -> str:
    """Add an idea to ideas.md."""
    try:
        content  = content.strip()
        tags_str = (" " + " ".join(f"#{t}" for t in tags)) if tags else ""
        line     = f"* {content}{tags_str}"
        _safe_append(IDEAS_FILE, line)
        return f"Idea saved: {content}"
    except Exception as e:
        return f"Failed to save idea: {e}"


def list_reminders() -> str:
    """Return a formatted string of all active reminders."""
    try:
        from core.memory_manager import get_all_reminders
        reminders = get_all_reminders()
        active    = [r for r in reminders if not r.done]
        if not active:
            return "You have no active reminders."
        overdue  = [r for r in active if r.is_past]
        today    = [r for r in active if r.is_today and not r.is_past]
        upcoming = [r for r in active if not r.is_past and not r.is_today]
        lines    = [f"You have {len(active)} active reminder(s):\n"]
        for label, group in [("OVERDUE", overdue), ("TODAY", today), ("UPCOMING", upcoming)]:
            if group:
                lines.append(f"{label}:")
                for r in group:
                    try:
                        day = r.dt.strftime("%A, %B %-d, %Y")
                    except ValueError:
                        day = r.dt.strftime("%A, %B %d, %Y")
                    t = "(all day)" if r.all_day else r.dt.strftime("%I:%M %p")
                    lines.append(f"  • {r.text} — {day} {t}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list reminders: {e}"


def list_tasks() -> str:
    """Return a formatted string of all tasks."""
    try:
        from core.memory_manager import get_all_tasks
        tasks   = get_all_tasks()
        if not tasks:
            return "You have no tasks."
        pending = [t for t in tasks if not t["done"]]
        done    = [t for t in tasks if t["done"]]
        lines   = []
        if pending:
            lines.append(f"Pending ({len(pending)}):")
            for t in pending:
                b = " [HIGH]" if t["high"] else ""
                d = f" — due {t['due']}" if t.get("due") else ""
                lines.append(f"  \u2610 {t['text']}{b}{d}")
        if done:
            lines.append(f"\nCompleted ({len(done)}):")
            for t in done[:5]:
                lines.append(f"  \u2713 {t['text']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list tasks: {e}"


def list_ideas() -> str:
    """Return a formatted string of all ideas."""
    try:
        from core.memory_manager import get_all_ideas
        ideas = get_all_ideas()
        if not ideas:
            return "No ideas captured yet."
        lines = [f"You have {len(ideas)} idea(s):\n"]
        for i, idea in enumerate(reversed(ideas[:20]), 1):
            lines.append(f"  {i}. {idea}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to list ideas: {e}"


def complete_task(title_fragment: str) -> str:
    """Mark the first matching pending task as done."""
    try:
        lines   = _read_all(TASKS_FILE)
        frag    = title_fragment.strip().lower()
        matched = False
        new     = []
        for ln in lines:
            if not matched and "- [ ]" in ln and frag in ln.lower():
                ln      = ln.replace("- [ ]", "- [x]", 1)
                matched = True
            new.append(ln)
        if matched:
            _write_all(TASKS_FILE, new)
            return f"Task marked complete: {title_fragment}"
        return f"No pending task found matching: '{title_fragment}'"
    except Exception as e:
        return f"Failed to complete task: {e}"


def delete_reminder_match(text_fragment: str) -> str:
    """Delete the first reminder whose text contains the given fragment."""
    try:
        lines   = _read_all(REMINDERS_FILE)
        frag    = text_fragment.strip().lower()
        removed = False
        new     = []
        for ln in lines:
            if not removed and ln.strip().startswith("* [") and frag in ln.lower():
                removed = True
                continue
            new.append(ln)
        if removed:
            _write_all(REMINDERS_FILE, new)
            return f"Reminder deleted matching: '{text_fragment}'"
        return f"No reminder found matching: '{text_fragment}'"
    except Exception as e:
        return f"Failed to delete reminder: {e}"


def save_all_reminders_raw(reminder_objects: list) -> None:
    """
    Overwrite reminders.md with a list of Reminder objects.
    Used by the UI's edit/delete operations.
    """
    try:
        lines = ["# Reminders\n"]
        for r in sorted(reminder_objects, key=lambda x: x.dt):
            lines.append(r.to_md_line() + "\n")
        _write_all(REMINDERS_FILE, lines)
    except Exception as e:
        print(f"save_all_reminders_raw error: {e}")


# ── Vault note CRUD ───────────────────────────────────────────────────────────────
# These give the AI full read/write/create/delete access to any vault note.

def _sanitize_name(name: str) -> str:
    """Strip characters that are invalid in file/folder names."""
    name = name.strip()
    # Remove characters invalid on Windows/Mac filesystems
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "untitled"


def _note_path(folder: str, title: str) -> str:
    """Return the absolute path for a vault note."""
    from config import VAULT_DIR
    folder = _sanitize_name(folder)
    title  = _sanitize_name(title)
    if not title.endswith(".md"):
        title += ".md"
    return os.path.join(VAULT_DIR, folder, title)


def write_note(folder: str, title: str, content: str, append: bool = False) -> str:
    """
    Write (or append to) a note in the vault.

    Creates the folder and file if they don't exist.
    Use folder names that match the vault structure, e.g.:
      '04_Knowledge', '03_Projects', '06_People', '07_Memory', '05_Ideas'
    Or any custom folder name — it will be created automatically.

    Args:
        folder  : Vault folder name (e.g. '04_Knowledge', 'Science', 'Personal')
        title   : Note title / filename (without .md)
        content : Markdown content to write
        append  : If True, append to existing content; if False, overwrite
    """
    try:
        path = _note_path(folder, title)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")

        if append and os.path.exists(path):
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n\n---\n*Updated: {ts}*\n\n{content.strip()}")
                f.flush()
                os.fsync(f.fileno())
            return f"Note updated: {folder}/{title}.md"
        else:
            # Write full note with frontmatter header
            header = f"# {_sanitize_name(title).replace('_', ' ')}\n\n*Created: {ts}*\n\n"
            with open(path, "w", encoding="utf-8") as f:
                f.write(header + content.strip())
                f.flush()
                os.fsync(f.fileno())
            return f"Note created: {folder}/{title}.md"
    except Exception as e:
        return f"Failed to write note: {e}"


def read_note(folder: str, title: str) -> str:
    """
    Read the contents of a vault note.

    Args:
        folder : Vault folder name
        title  : Note title (with or without .md)
    """
    try:
        path = _note_path(folder, title)
        if not os.path.exists(path):
            # Try searching nearby
            from config import VAULT_DIR
            folder_path = os.path.join(VAULT_DIR, _sanitize_name(folder))
            if os.path.isdir(folder_path):
                files = os.listdir(folder_path)
                return (f"Note '{title}' not found in {folder}/. "
                        f"Available notes: {', '.join(f[:-3] for f in files if f.endswith('.md'))}")
            return f"Note not found: {folder}/{title}"
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Failed to read note: {e}"


def delete_note(folder: str, title: str) -> str:
    """
    Delete a note from the vault permanently.

    Args:
        folder : Vault folder name
        title  : Note title (with or without .md)
    """
    try:
        path = _note_path(folder, title)
        if not os.path.exists(path):
            return f"Note not found: {folder}/{title}"
        os.remove(path)
        return f"Note deleted: {folder}/{title}"
    except Exception as e:
        return f"Failed to delete note: {e}"


def list_notes(folder: str = "") -> str:
    """
    List all notes in a vault folder, or list all folders if no folder given.

    Args:
        folder : Vault folder name (empty string to list all folders)
    """
    try:
        from config import VAULT_DIR
        _skip = {"chroma_db", ".venv", "__pycache__", ".obsidian", ".git",
                 "assets", "lib", "__pycache__"}

        if not folder:
            # List all top-level folders
            entries = []
            for name in sorted(os.listdir(VAULT_DIR)):
                if name in _skip or name.startswith(".") or name.startswith("_"):
                    continue
                full = os.path.join(VAULT_DIR, name)
                if os.path.isdir(full):
                    n = len([f for f in os.listdir(full) if f.endswith(".md")])
                    entries.append(f"  {name}/  ({n} notes)")
            return "Vault folders:\n" + ("\n".join(entries) or "  (none)")

        folder_path = os.path.join(VAULT_DIR, _sanitize_name(folder))
        if not os.path.isdir(folder_path):
            return f"Folder '{folder}' does not exist in the vault."
        notes = sorted(f[:-3] for f in os.listdir(folder_path) if f.endswith(".md"))
        if not notes:
            return f"No notes in {folder}/ yet."
        return f"Notes in {folder}/:\n" + "\n".join(f"  - {n}" for n in notes)
    except Exception as e:
        return f"Failed to list notes: {e}"


def create_folder(folder_name: str) -> str:
    """
    Create a new folder in the vault.

    Args:
        folder_name : Name of the folder to create
    """
    try:
        from config import VAULT_DIR
        path = os.path.join(VAULT_DIR, _sanitize_name(folder_name))
        os.makedirs(path, exist_ok=True)
        return f"Folder created: {folder_name}/"
    except Exception as e:
        return f"Failed to create folder: {e}"


def search_notes(query: str) -> str:
    """
    Full-text search across all vault notes.
    Returns the names of notes containing the query string.

    Args:
        query : Text to search for (case-insensitive)
    """
    try:
        from config import VAULT_DIR
        query_lower = query.strip().lower()
        _skip = {"chroma_db", ".venv", "__pycache__", ".obsidian"}
        matches = []

        import glob as _glob
        for fp in _glob.glob(os.path.join(VAULT_DIR, "**", "*.md"), recursive=True):
            if any(s in fp for s in _skip):
                continue
            try:
                content = open(fp, encoding="utf-8").read().lower()
                if query_lower in content:
                    rel = os.path.relpath(fp, VAULT_DIR).replace("\\", "/")
                    # Get first matching line for context
                    for ln in content.split("\n"):
                        if query_lower in ln:
                            matches.append(f"  {rel}: …{ln.strip()[:80]}…")
                            break
            except Exception:
                continue

        if not matches:
            return f"No notes found containing: '{query}'"
        return f"Found '{query}' in {len(matches)} note(s):\n" + "\n".join(matches[:20])
    except Exception as e:
        return f"Search failed: {e}"

