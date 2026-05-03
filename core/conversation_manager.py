"""
core/conversation_manager.py — Rolling conversation history buffer.

A single instance lives on the MainWindow and is shared by every
UI panel (Dashboard, Chat). All AI calls pull history from here
and push updated history back here after each turn.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MAX_HISTORY_TURNS


class ConversationManager:
    """
    Maintains a rolling buffer of user/assistant message pairs.
    The buffer is trimmed to MAX_HISTORY_TURNS turns (pairs).
    """

    def __init__(self, max_turns: int = MAX_HISTORY_TURNS):
        self._max_turns = max_turns
        self.history: list = []   # list of {"role": ..., "content": ...} dicts

    # ── Public API ────────────────────────────────────────────────────────────────

    def get_history(self) -> list:
        """Return a copy of the current history list."""
        return list(self.history)

    def set_history(self, new_history: list) -> None:
        """Replace history with a new list and trim to max window."""
        self.history = new_history
        self._trim()

    def clear(self) -> None:
        """Reset history."""
        self.history = []

    # ── Internal ──────────────────────────────────────────────────────────────────

    def _trim(self) -> None:
        """Keep only the last max_turns * 2 messages."""
        cap = self._max_turns * 2
        if len(self.history) > cap:
            self.history = self.history[-cap:]
