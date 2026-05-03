"""
ui/tasks_view.py — Task list (read-only view).
To add a task, use the Dashboard: type 'Task: review the report'
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt

from core.memory_manager import get_tasks


class TaskItem(QFrame):
    def __init__(self, task: dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(14)

        dot = QLabel()
        dot.setFixedSize(12, 12)
        if task["done"]:
            dot.setStyleSheet("background:#30d158;border-radius:6px;")
        elif task["high"]:
            dot.setStyleSheet(
                "border:1.5px solid #ff453a;background:rgba(255,69,58,0.14);"
                "border-radius:6px;")
        else:
            dot.setStyleSheet(
                "border:1.5px solid rgba(255,255,255,0.22);border-radius:6px;"
                "background:transparent;")
        row.addWidget(dot)

        color  = "rgba(255,255,255,0.28)" if task["done"] else "rgba(255,255,255,0.84)"
        strike = "text-decoration:line-through;" if task["done"] else ""
        lbl = QLabel(task["text"])
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{color};{strike}font-size:13px;"
            f"letter-spacing:-0.1px;background:transparent;")
        row.addWidget(lbl, 1)

        if task["high"] and not task["done"]:
            badge = QLabel("HIGH")
            badge.setFixedHeight(18)
            badge.setStyleSheet(
                "background:rgba(255,69,58,0.18);color:#ff453a;"
                "font-size:9px;font-weight:700;letter-spacing:0.07em;"
                "padding:2px 6px;border-radius:4px;")
            row.addWidget(badge)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,0.055);border:none;max-height:1px;")
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(row)
        outer.addWidget(sep)
        self.setLayout(outer)


def _section_card(title: str, tasks: list, color: str = "rgba(255,255,255,0.28)") -> QFrame:
    card = QFrame()
    card.setProperty("card", "true")
    cl = QVBoxLayout(card)
    cl.setContentsMargins(24, 18, 24, 14)
    cl.setSpacing(0)
    head = QLabel(title)
    head.setStyleSheet(
        f"color:{color};font-size:10px;font-weight:600;"
        f"letter-spacing:0.1em;background:transparent;margin-bottom:8px;")
    cl.addWidget(head)
    if not tasks:
        empty = QLabel("None")
        empty.setStyleSheet(
            "color:rgba(255,255,255,0.18);font-style:italic;"
            "font-size:13px;background:transparent;padding:6px 0;")
        cl.addWidget(empty)
    else:
        for t in tasks:
            cl.addWidget(TaskItem(t))
    return card


class TasksView(QWidget):
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
        eyebrow = QLabel("Task System")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("Tasks")
        title.setProperty("role", "page-title")
        sub = QLabel('Use the Dashboard to add tasks — e.g. type: "Task: review the report"')
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

        self._body = QWidget()
        self._body.setStyleSheet("background:#000000;")
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(48, 0, 48, 60)
        self._body_layout.setSpacing(16)
        self._body_layout.addStretch()

        scroll.setWidget(self._body)
        root.addWidget(scroll, 1)

    def refresh(self):
        while self._body_layout.count() > 1:
            item = self._body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks   = get_tasks()
        high    = [t for t in tasks if t["high"] and not t["done"]]
        pending = [t for t in tasks if not t["done"] and not t["high"]]
        done    = [t for t in tasks if t["done"]]

        idx = 0
        if high:
            self._body_layout.insertWidget(idx, _section_card("High Priority", high, "#ff453a"))
            idx += 1
        self._body_layout.insertWidget(idx, _section_card("Pending", pending))
        idx += 1
        if done:
            self._body_layout.insertWidget(idx, _section_card("Completed", done, "#30d158"))
