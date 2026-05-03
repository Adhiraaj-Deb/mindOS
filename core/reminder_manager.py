"""
core/reminder_manager.py — Complete reminder system for MindOS.

Storage format in 08_Reminders/reminders.md:
  * [YYYY-MM-DD HH:MM] Reminder text
  * [YYYY-MM-DD]       All-day reminder text
  * [YYYY-MM-DD HH:MM] [DONE] Completed reminder

Supports:
  - Parse natural language: "remind me to call John on April 15 at 3pm"
  - Retrieve all / today's / upcoming reminders
  - Mark done, delete reminders
"""
import re
import os
from datetime import datetime, date, timedelta
from typing import Optional

from .file_utils import VAULT_PATH, append_to_file, read_file

try:
    from dateutil import parser as du_parser
    from dateutil.relativedelta import relativedelta
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

REMINDERS_FILE = os.path.join(VAULT_PATH, "08_Reminders", "reminders.md")


# ── Data model ─────────────────────────────────────────────────────────────────

class Reminder:
    def __init__(self, text: str, dt: datetime,
                 all_day: bool = False, done: bool = False):
        self.text    = text.strip()
        self.dt      = dt          # datetime (time is 00:00 if all_day)
        self.all_day = all_day
        self.done    = done

    @property
    def is_past(self) -> bool:
        now = datetime.now()
        if self.all_day:
            return self.dt.date() < date.today()
        return self.dt < now

    @property
    def is_today(self) -> bool:
        return self.dt.date() == date.today()

    def to_md_line(self) -> str:
        if self.all_day:
            stamp = self.dt.strftime("%Y-%m-%d")
        else:
            stamp = self.dt.strftime("%Y-%m-%d %H:%M")
        done_tag = " [DONE]" if self.done else ""
        return f"* [{stamp}]{done_tag} {self.text}"

    def friendly_str(self) -> str:
        if self.all_day:
            time_str = "(all day)"
        else:
            time_str = self.dt.strftime("at %I:%M %p")
        day_str = self.dt.strftime("%A, %B %-d")  # may fail on Windows
        try:
            day_str = self.dt.strftime("%A, %B %-d")
        except ValueError:
            day_str = self.dt.strftime("%A, %B %d")
        status = " ✓" if self.done else ""
        return f"{day_str} {time_str} — {self.text}{status}"


# ── Parsing stored reminders ───────────────────────────────────────────────────

_LINE_RE = re.compile(
    r"^\*\s*\[(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\]"
    r"(\s*\[DONE\])?\s+(.+)$"
)

def _parse_line(line: str) -> Optional[Reminder]:
    m = _LINE_RE.match(line.strip())
    if not m:
        return None
    date_str, time_str, done_tag, text = m.group(1), m.group(2), m.group(3), m.group(4)
    all_day = time_str is None
    if all_day:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0)
    else:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    done = bool(done_tag and "DONE" in done_tag)
    return Reminder(text=text, dt=dt, all_day=all_day, done=done)


def load_reminders() -> list[Reminder]:
    """Load all reminders from file."""
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
    if not os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            f.write("# Reminders\n")
        return []
    raw = read_file(REMINDERS_FILE)
    reminders = []
    for line in raw.splitlines():
        r = _parse_line(line)
        if r:
            reminders.append(r)
    return sorted(reminders, key=lambda r: r.dt)


def save_all_reminders(reminders: list[Reminder]) -> None:
    """Overwrite the reminders file with the given list."""
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
    lines = ["# Reminders\n"]
    for r in sorted(reminders, key=lambda r: r.dt):
        lines.append(r.to_md_line())
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── Natural language parsing ───────────────────────────────────────────────────

# Date-related keyword replacements before dateutil
_REL_MAP = {
    r"\btoday\b":        lambda: date.today().strftime("%Y-%m-%d"),
    r"\btomorrow\b":     lambda: (date.today() + timedelta(days=1)).strftime("%Y-%m-%d"),
    r"\bnext week\b":    lambda: (date.today() + timedelta(weeks=1)).strftime("%Y-%m-%d"),
    r"\bthis evening\b": lambda: date.today().strftime("%Y-%m-%d") + " 18:00",
    r"\bthis morning\b": lambda: date.today().strftime("%Y-%m-%d") + " 09:00",
    r"\bthis afternoon\b": lambda: date.today().strftime("%Y-%m-%d") + " 14:00",
    r"\bthis night\b":   lambda: date.today().strftime("%Y-%m-%d") + " 21:00",
    r"\btonight\b":      lambda: date.today().strftime("%Y-%m-%d") + " 21:00",
}

# Pattern: "remind me (to|about|for) TEXT on DATE at TIME"
_REMIND_PATTERNS = [
    # "remind me to call John on April 15 at 3pm"
    re.compile(
        r"remind\s+me\s+(?:to|about|for)?\s*(.+?)\s+on\s+(.+?)\s+at\s+(.+)",
        re.IGNORECASE),
    # "remind me at 3pm on April 15 to call John"
    re.compile(
        r"remind\s+me\s+at\s+(.+?)\s+on\s+(.+?)\s+(?:to|about|for)?\s*(.+)",
        re.IGNORECASE),
    # "remind me to call John on April 15"
    re.compile(
        r"remind\s+me\s+(?:to|about|for)?\s*(.+?)\s+on\s+(.+)",
        re.IGNORECASE),
    # "remind me tomorrow at 3pm to call John"
    re.compile(
        r"remind\s+me\s+(tomorrow|today)\s+at\s+(.+?)\s+(?:to|about|for)?\s*(.+)",
        re.IGNORECASE),
    # "remind me tomorrow to call John"
    re.compile(
        r"remind\s+me\s+(tomorrow|today)\s+(?:to|about|for)?\s*(.+)",
        re.IGNORECASE),
    # "set a reminder for April 15 at 3pm: call John"
    re.compile(
        r"set\s+a\s+reminder\s+(?:for|on)?\s*(.+?)\s+at\s+(.+?)[\:\-]+(.+)",
        re.IGNORECASE),
    # "set a reminder for April 15: call John"
    re.compile(
        r"set\s+a\s+reminder\s+(?:for|on)?\s*(.+?)[\:\-]+(.+)",
        re.IGNORECASE),
]

# Time pattern like "3pm", "3:30pm", "15:00", "3 pm"
_TIME_RE = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)?\b"
)

def _parse_time(time_str: str) -> Optional[tuple[int, int]]:
    """Return (hour, minute) from a time string, or None."""
    m = _TIME_RE.search(time_str.strip())
    if not m:
        return None
    hour   = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    ampm   = m.group(3)
    if ampm:
        ampm = ampm.lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
    return (hour, minute)


def _parse_date(date_str: str) -> Optional[date]:
    """Parse a date string using dateutil (with relative keyword substitution)."""
    text = date_str.strip()

    # Apply relative keyword substitutions
    for pattern, fn in _REL_MAP.items():
        text = re.sub(pattern, fn(), text, flags=re.IGNORECASE)

    if HAS_DATEUTIL:
        try:
            parsed = du_parser.parse(text, default=datetime.now(), dayfirst=False)
            return parsed.date()
        except Exception:
            pass

    # Manual fallback for simple cases
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%B %d", "%b %d",
                "%d %B", "%d %b", "%B %dth", "%B %dst", "%B %dnd", "%B %drd"):
        try:
            d = datetime.strptime(text, fmt)
            if d.year == 1900:
                d = d.replace(year=date.today().year)
            return d.date()
        except ValueError:
            continue
    return None


def parse_reminder_command(text: str) -> Optional[Reminder]:
    """
    Attempt to parse a natural-language reminder command.
    Returns a Reminder object on success, None if not recognized.
    """
    text = text.strip()

    for pat in _REMIND_PATTERNS:
        m = pat.match(text)
        if not m:
            continue

        groups = [g.strip() if g else "" for g in m.groups()]

        # Extract components based on which pattern matched
        if len(groups) == 3:
            part_a, part_b, part_c = groups

            # Detect which group has the time and which has the date
            has_time_a = bool(_TIME_RE.search(part_a))
            has_time_b = bool(_TIME_RE.search(part_b))
            has_time_c = bool(_TIME_RE.search(part_c))

            if has_time_a and not has_time_b:
                # "at TIME on DATE to TEXT" or "at TIME on DATE: TEXT"
                time_hm, date_str, reminder_text = _parse_time(part_a), part_b, part_c
            elif has_time_c:
                # "TEXT on DATE at TIME"
                reminder_text, date_str, time_str = part_a, part_b, part_c
                time_hm = _parse_time(time_str)
            elif has_time_b:
                reminder_text, time_str, date_str = part_a, part_b, part_c
                time_hm = _parse_time(time_str)
            else:
                reminder_text, date_str = part_a, part_b
                time_hm, time_str = None, ""
                # Maybe time embedded in date_str
                tp = _parse_time(date_str)
                if tp:
                    time_hm = tp
                    date_str = re.sub(_TIME_RE, "", date_str).strip()

            parsed_date = _parse_date(date_str)

        elif len(groups) == 2:
            part_a, part_b = groups
            # "tomorrow to X" or "TEXT on DATE"
            relative_words = {"tomorrow", "today"}
            if part_a.lower() in relative_words:
                parsed_date = _parse_date(part_a)
                reminder_text = part_b
                time_hm = _parse_time(part_b)
                if time_hm:
                    reminder_text = re.sub(_TIME_RE, "", reminder_text).strip()
            else:
                reminder_text = part_a
                time_hm = _parse_time(part_b)
                date_str = re.sub(_TIME_RE, "", part_b).strip() if time_hm else part_b
                parsed_date = _parse_date(part_b if not time_hm else date_str)
        else:
            continue

        if not parsed_date:
            continue

        # Build datetime
        if time_hm:
            h, mi = time_hm
            dt = datetime(parsed_date.year, parsed_date.month, parsed_date.day, h, mi)
            all_day = False
        else:
            dt = datetime(parsed_date.year, parsed_date.month, parsed_date.day)
            all_day = True

        reminder_text = reminder_text.strip(".,;: ")
        if not reminder_text:
            continue

        return Reminder(text=reminder_text, dt=dt, all_day=all_day)

    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def save_reminder(reminder: Reminder) -> str:
    """Append a reminder to the file. Returns confirmation string."""
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
    if not os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            f.write("# Reminders\n")
    with open(REMINDERS_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + reminder.to_md_line())
    return reminder.to_md_line()


def get_reminders_for_today() -> list[Reminder]:
    return [r for r in load_reminders() if r.is_today and not r.done]


def get_upcoming_reminders(days: int = 7) -> list[Reminder]:
    cutoff = datetime.now() + timedelta(days=days)
    return [
        r for r in load_reminders()
        if not r.done and r.dt <= cutoff and not r.is_past
    ]


def get_all_active_reminders() -> list[Reminder]:
    return [r for r in load_reminders() if not r.done]


def get_overdue_reminders() -> list[Reminder]:
    return [r for r in load_reminders() if r.is_past and not r.done]


def mark_done(text_fragment: str) -> str:
    """Mark the first reminder matching a text fragment as done."""
    reminders = load_reminders()
    for r in reminders:
        if text_fragment.lower() in r.text.lower():
            r.done = True
            save_all_reminders(reminders)
            return f"Marked done: {r.text}"
    return f"No reminder found matching: '{text_fragment}'"


def delete_reminder(text_fragment: str) -> str:
    """Delete the first reminder matching a text fragment."""
    reminders = load_reminders()
    original  = len(reminders)
    reminders = [r for r in reminders if text_fragment.lower() not in r.text.lower()]
    if len(reminders) == original:
        return f"No reminder found matching: '{text_fragment}'"
    save_all_reminders(reminders)
    return f"Deleted reminder matching: '{text_fragment}'"


def format_reminders_response(reminders: list[Reminder], label: str = "reminders") -> str:
    """Format a list of reminders into a human-readable reply."""
    if not reminders:
        return f"You have no {label}."
    lines = [f"You have {len(reminders)} {label}:\n"]
    now = datetime.now()
    for r in reminders:
        prefix = "⚠️ OVERDUE — " if r.is_past and not r.all_day else ""
        if r.all_day:
            time_part = "(all day)"
        else:
            time_part = r.dt.strftime("at %I:%M %p")
        try:
            day_part = r.dt.strftime("%A, %B %-d, %Y")
        except ValueError:
            day_part = r.dt.strftime("%A, %B %d, %Y")
        lines.append(f"  • {prefix}{r.text}\n    {day_part} {time_part}")
    return "\n".join(lines)
