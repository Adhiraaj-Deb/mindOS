"""
ui/ai_worker.py — Shared non-blocking AI call thread.

Used by BOTH DashboardView and ChatView.
Accepts user_input + the current rolling history,
calls core.ai_engine.ask(), and emits the reply + updated history.
"""
from PyQt6.QtCore import QThread, pyqtSignal
import core.ai_engine as ai_engine


class AIWorker(QThread):
    """
    Background thread that calls ai_engine.ask().

    Signals:
        result_ready(str, list) — (reply_text, updated_history)
    """
    result_ready = pyqtSignal(str, list)

    def __init__(self, user_input: str, history: list, mode: str = "chat", parent=None):
        super().__init__(parent)
        self.user_input = user_input
        self.history    = list(history)   # copy to avoid mutation during run
        self.mode       = mode

    def run(self):
        try:
            reply, new_history = ai_engine.ask(self.user_input, self.history, mode=self.mode)
            self.result_ready.emit(reply, new_history)
        except Exception as exc:
            self.result_ready.emit(f"Error: {exc}", self.history)
