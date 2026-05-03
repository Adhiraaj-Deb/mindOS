"""
ui/ideas_view.py — Ideas list (read-only view).
To add an idea, use the Dashboard: type 'Idea: build a reading tracker'
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt

from core.memory_manager import get_ideas


class IdeaItem(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)

        icon = QLabel("💡")
        icon.setFixedWidth(18)
        icon.setStyleSheet("font-size:13px;background:transparent;")
        row.addWidget(icon)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color:rgba(255,255,255,0.78);font-size:13.5px;"
            "letter-spacing:-0.1px;background:transparent;")
        row.addWidget(lbl, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,0.055);border:none;max-height:1px;")
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(row)
        outer.addWidget(sep)
        self.setLayout(outer)


class IdeasView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QWidget()
        hdr.setStyleSheet("background:#000000;")
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(48, 52, 48, 24)
        hl.setSpacing(4)
        eyebrow = QLabel("Idea Capture")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("Ideas")
        title.setProperty("role", "page-title")
        sub = QLabel('Use the Dashboard to capture ideas — e.g. type: "Idea: build a habit tracker"')
        sub.setProperty("role", "sub")
        hl.addWidget(eyebrow)
        hl.addWidget(title)
        hl.addWidget(sub)
        root.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:#000000;")

        body = QWidget()
        body.setStyleSheet("background:#000000;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(48, 0, 48, 60)
        bl.setSpacing(0)

        self._card = QFrame()
        self._card.setProperty("card", "true")
        self._card_layout = QVBoxLayout(self._card)
        self._card_layout.setContentsMargins(24, 18, 24, 14)
        self._card_layout.setSpacing(0)

        self._count_lbl = QLabel()
        self._count_lbl.setProperty("role", "card-head")
        self._card_layout.addWidget(self._count_lbl)

        self._list_layout = QVBoxLayout()
        self._list_layout.setContentsMargins(0, 6, 0, 0)
        self._list_layout.setSpacing(0)
        self._card_layout.addLayout(self._list_layout)

        bl.addWidget(self._card)
        bl.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def refresh(self):
        ideas = get_ideas()
        n = len(ideas)
        self._count_lbl.setText(f"{n} idea{'s' if n != 1 else ''} captured")

        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not ideas:
            empty = QLabel('No ideas yet.\nGo to Dashboard and type "Idea: your idea"')
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "color:rgba(255,255,255,0.18);font-style:italic;"
                "font-size:13px;background:transparent;padding:20px 0;")
            self._list_layout.addWidget(empty)
        else:
            for idea in reversed(ideas):
                self._list_layout.addWidget(IdeaItem(idea))
