"""
ui/gemini_view.py — Dedicated Gemini conversational interface.

Purpose:
  - Isolated conversational AI using Google Gemini via API.
  - Does NOT access local vault memory/history by default.
  - If instructed to memory save, uses `<GEMINI_MEMORY>` which gets saved.
  - Maintains its own isolated conversation history.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt

from ui.gemini_worker import GeminiWorker
from ui.chat_view import Bubble, ThinkingBubble  # reuse styling components

class GeminiView(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._mw = main_window
        self._worker: GeminiWorker | None = None
        self._thinking_bubble: ThinkingBubble | None = None
        self.history = []  # Isolated conversation history
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
        title = QLabel("Gemini Interface")
        title.setStyleSheet(
            "color:#ffffff;font-size:16px;font-weight:600;"
            "letter-spacing:-0.3px;background:transparent;")
        sub = QLabel(
            "Chat with Cloud Gemini · Tell it to \"save\" to explicitly remember things")
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
            "Welcome to Gemini.\n"
            "This space is isolated from your main local vault.\n"
            "Only explicit 'remember this' commands are saved.")
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
        self._input.setPlaceholderText("Send a message to Gemini...")
        self._input.returnPressed.connect(self._send)
        bl.addWidget(self._input, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setProperty("action", "primary")
        self._send_btn.setFixedWidth(72)
        self._send_btn.clicked.connect(self._send)
        bl.addWidget(self._send_btn)

        root.addWidget(bottom)

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

        self._worker = GeminiWorker(text, self.history)
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_result(self, reply: str, new_history: list):
        if self._thinking_bubble:
            self._thinking_bubble.setParent(None)
            self._thinking_bubble.deleteLater()
            self._thinking_bubble = None

        self._add_bubble(reply, is_user=False)
        self._scroll_bottom()

        # Update isolated history
        self.history = new_history[-20:] # Keep last 20 messages buffer to avoid huge token counts
        
        # It won't refresh the UI dashboard since it writes to a separate memory file, 
        # but we could optionally call mw.refresh_all_views() if wanted. Let's do it just in case.
        if self._mw and hasattr(self._mw, "refresh_all_views"):
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
        self.history = []
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._empty_lbl.setVisible(True)
        self._msg_layout.insertWidget(0, self._empty_lbl)
