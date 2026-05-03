"""
ui/chat_view.py — Knowledge & Memory interface.

Purpose:
  - Conversational AI with full vault context and rolling history
  - The AI can call save_memory, search memory, answer from RAG context
  - Identical AI pipeline to Dashboard (same AIWorker, same ConversationManager)

Changes from previous version:
  - Removed old AIWorker signals (is_command, response_ready, error_occurred)
  - Now uses result_ready(str, list) signal from ui.ai_worker.AIWorker
  - Removed post-hoc save_memory() heuristic — memory is saved via LLM tool call
  - main_window reference for ConversationManager access
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QFrame,
    QTextEdit,
)
from PyQt6.QtCore import Qt

from ui.ai_worker import AIWorker


# ── Chat bubbles ──────────────────────────────────────────────────────────────

class Bubble(QFrame):
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.setSpacing(0)

        if is_user:
            lbl.setStyleSheet(
                "background:#0071e3;color:#ffffff;border-radius:14px;"
                "padding:11px 16px;font-size:14px;line-height:1.5;")
            row.addStretch(1)
            row.addWidget(lbl, 3)
        else:
            lbl.setStyleSheet(
                "background:#111111;border:1px solid rgba(255,255,255,0.07);"
                "color:rgba(255,255,255,0.88);border-radius:14px;"
                "padding:13px 16px;font-size:14px;line-height:1.65;")
            row.addWidget(lbl, 4)
            row.addStretch(1)


class ThinkingBubble(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        lbl = QLabel("Thinking\u2026")
        lbl.setStyleSheet(
            "background:#0a0a0a;border:1px solid rgba(255,255,255,0.055);"
            "color:rgba(255,255,255,0.28);border-radius:14px;"
            "padding:11px 16px;font-size:13px;font-style:italic;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 4, 0, 4)
        row.addWidget(lbl, 4)
        row.addStretch(1)


# ── Chat view ─────────────────────────────────────────────────────────────────

class ChatView(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._mw                             = main_window
        self._worker: AIWorker | None        = None
        self._thinking_bubble: ThinkingBubble | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar
        top_bar = QWidget()
        top_bar.setFixedHeight(68)
        top_bar.setStyleSheet(
            "background:#000000;"
            "border-bottom:1px solid rgba(255,255,255,0.06);")
        tl = QHBoxLayout(top_bar)
        tl.setContentsMargins(40, 0, 40, 0)
        tl.setSpacing(0)

        text_block = QVBoxLayout()
        text_block.setSpacing(1)
        title = QLabel("Knowledge & Memory")
        title.setStyleSheet(
            "color:#ffffff;font-size:16px;font-weight:600;"
            "letter-spacing:-0.3px;background:transparent;")
        sub = QLabel(
            "Ask questions from your vault \u00b7 say things you want remembered")
        sub.setStyleSheet(
            "color:rgba(255,255,255,0.3);font-size:12px;background:transparent;")
        text_block.addWidget(title)
        text_block.addWidget(sub)
        tl.addLayout(text_block)
        tl.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("action", "ghost")
        clear_btn.setFixedWidth(68)
        clear_btn.clicked.connect(self._clear_chat)
        tl.addWidget(clear_btn)
        root.addWidget(top_bar)

        # ── Message area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background:#000000;")

        self._msg_widget = QWidget()
        self._msg_widget.setStyleSheet("background:#000000;")
        self._msg_layout = QVBoxLayout(self._msg_widget)
        self._msg_layout.setContentsMargins(40, 24, 40, 16)
        self._msg_layout.setSpacing(8)
        self._msg_layout.addStretch()

        self._empty_lbl = QLabel(
            "Start a conversation. Ask questions, share facts, or say\n"
            "\"My dog's name is Bruno\" and I'll remember it.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.13);font-size:14px;font-style:italic;"
            "background:transparent;padding:60px 20px;")
        self._msg_layout.insertWidget(0, self._empty_lbl)

        self._scroll.setWidget(self._msg_widget)
        root.addWidget(self._scroll, 1)

        # ── Bottom input bar
        bottom = QWidget()
        bottom.setFixedHeight(72)
        bottom.setStyleSheet(
            "background:#000000;"
            "border-top:1px solid rgba(255,255,255,0.06);")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(40, 12, 40, 12)
        bl.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText(
            "Ask your vault a question, or say something you want remembered\u2026")
        self._input.returnPressed.connect(self._send)
        bl.addWidget(self._input, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setProperty("action", "primary")
        self._send_btn.setFixedWidth(72)
        self._send_btn.clicked.connect(self._send)
        bl.addWidget(self._send_btn)

        root.addWidget(bottom)

    # ── AI pipeline (identical to Dashboard) ──────────────────────────────────

    def _send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return

        self._input.clear()
        self._input.setEnabled(False)
        self._send_btn.setEnabled(False)
        self._empty_lbl.setVisible(False)

        self._add_bubble(text, is_user=True)

        self._thinking_bubble = ThinkingBubble()
        self._msg_layout.addWidget(self._thinking_bubble)
        self._scroll_bottom()

        # Pull history from shared ConversationManager
        history = self._mw.conversation_manager.get_history() if self._mw else []

        self._worker = AIWorker(text, history)
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_result(self, reply: str, new_history: list):
        # Remove thinking bubble
        if self._thinking_bubble:
            self._thinking_bubble.setParent(None)
            self._thinking_bubble.deleteLater()
            self._thinking_bubble = None

        self._add_bubble(reply, is_user=False)
        self._scroll_bottom()

        # Persist updated history and refresh all views
        if self._mw:
            self._mw.conversation_manager.set_history(new_history)
            self._mw.refresh_all_views()

    def _on_done(self):
        self._worker = None
        self._input.setEnabled(True)
        self._send_btn.setEnabled(True)
        self._input.setFocus()

    def _add_bubble(self, text: str, is_user: bool):
        self._msg_layout.addWidget(Bubble(text, is_user))

    def _scroll_bottom(self):
        sb = self._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_chat(self):
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._empty_lbl.setVisible(True)
        self._msg_layout.insertWidget(0, self._empty_lbl)
