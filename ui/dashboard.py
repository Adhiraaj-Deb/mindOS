"""
ui/dashboard.py — Universal command center for MindOS.

ONE input box. Handles everything via the AI tool-calling pipeline:
  - Set reminders   ("Remind me to call John on April 20 at 3pm")
  - Add tasks       ("Add a task: review the report, high priority")
  - Capture ideas   ("Idea: build a reading tracker")
  - Ask questions   ("What are my reminders today?")
  - Any open-ended question → RAG pipeline

Pipeline (unified with Chat):
  user input → AIWorker(text, history) → ai_engine.ask() →
     tool calls executed on disk → natural language reply →
     conversation_manager updated → refresh_all_views()
"""
import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QFrame,
    QTextEdit, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

from ui.ai_worker import AIWorker
from core.memory_manager import get_all_tasks, get_all_reminders


# ── Compact stat pill ─────────────────────────────────────────────────────────

class StatPill(QFrame):
    def __init__(self, value: str, label: str, color: str = "#ffffff", parent=None):
        super().__init__(parent)
        self.setProperty("card", "dark")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(2)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"color:{color};font-size:26px;font-weight:700;"
            f"letter-spacing:-0.8px;background:transparent;")
        lbl_lbl = QLabel(label)
        lbl_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.3);font-size:9.5px;font-weight:600;"
            "letter-spacing:0.08em;text-transform:uppercase;background:transparent;")
        layout.addWidget(val_lbl)
        layout.addWidget(lbl_lbl)


# ── Today's reminder mini-item ────────────────────────────────────────────────

class TodayReminderItem(QLabel):
    def __init__(self, reminder, parent=None):
        if reminder.all_day:
            time_str = "(all day)"
        else:
            time_str = reminder.dt.strftime("%I:%M %p")
        prefix = "\u26a0 " if reminder.is_past else "\U0001f4c5 "
        color  = "#ff453a" if reminder.is_past else "#0071e3"
        super().__init__(f"{prefix}{reminder.text} \u2014 {time_str}", parent)
        self.setStyleSheet(
            f"color:{color};font-size:12.5px;background:transparent;"
            f"padding:4px 0;letter-spacing:-0.05px;")
        self.setWordWrap(True)


# ── Main dashboard ─────────────────────────────────────────────────────────────

class DashboardView(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self._mw     = main_window          # reference to MainWindow (for ConversationManager)
        self._worker: AIWorker | None = None
        self._pending_user = ""
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scrollable content wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:#000000;")

        content = QWidget()
        content.setStyleSheet("background:#000000;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 60)
        cl.setSpacing(0)

        # ── Hero
        hero = QWidget()
        hero.setStyleSheet("background:#000000;")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(0, 72, 0, 0)
        hl.setSpacing(4)
        hl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        hour = datetime.datetime.now().hour
        greeting = (
            "Good morning" if hour < 12 else
            "Good afternoon" if hour < 17 else
            "Good evening"
        )

        eyebrow = QLabel("YOUR SECOND BRAIN")
        eyebrow.setProperty("role", "eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)

        greet_lbl = QLabel(f"{greeting},")
        greet_lbl.setStyleSheet(
            "color:#ffffff;font-size:52px;font-weight:700;"
            "letter-spacing:-2px;line-height:1.04;background:transparent;")
        greet_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        mind_lbl = QLabel("what's on your mind?")
        mind_lbl.setStyleSheet(
            "color:#0071e3;font-size:52px;font-weight:700;"
            "letter-spacing:-2px;line-height:1.04;background:transparent;")
        mind_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sub_lbl = QLabel(
            "Set reminders, capture tasks & ideas, ask any question \u2014 all in one place.")
        sub_lbl.setProperty("role", "sub")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hl.addWidget(eyebrow)
        hl.addWidget(greet_lbl)
        hl.addWidget(mind_lbl)
        hl.addSpacing(10)
        hl.addWidget(sub_lbl)
        cl.addWidget(hero)

        # ── Stat pills
        self._stats_widget = QWidget()
        self._stats_widget.setStyleSheet("background:#000000;")
        self._stats_row = QHBoxLayout(self._stats_widget)
        self._stats_row.setContentsMargins(80, 36, 80, 0)
        self._stats_row.setSpacing(12)
        cl.addWidget(self._stats_widget)

        # ── Command input
        cmd_wrap = QWidget()
        cmd_wrap.setStyleSheet("background:#000000;")
        cw = QVBoxLayout(cmd_wrap)
        cw.setContentsMargins(80, 32, 80, 0)
        cw.setSpacing(10)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)

        self._input = QLineEdit()
        self._input.setPlaceholderText(
            "Remind me to…  /  Add task: …  /  Idea: …  /  Ask me anything…")
        self._input.setFixedHeight(52)
        self._input.setStyleSheet(
            "background:rgba(255,255,255,0.04);border:1.5px solid rgba(255,255,255,0.1);"
            "border-radius:14px;color:#fff;padding:0 18px;font-size:15px;")
        self._input.returnPressed.connect(self._send)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("Ask")
        self._send_btn.setFixedSize(88, 52)
        self._send_btn.setStyleSheet(
            "background:#0071e3;color:#fff;border:none;"
            "border-radius:14px;font-size:15px;font-weight:600;")
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)

        cw.addLayout(input_row)
        cl.addWidget(cmd_wrap)

        # ── Response card (hidden until first reply)
        resp_wrap = QWidget()
        resp_wrap.setStyleSheet("background:#000000;")
        rv = QHBoxLayout(resp_wrap)
        rv.setContentsMargins(80, 18, 80, 0)

        self._response_card = QFrame()
        self._response_card.setProperty("card", "true")
        self._response_card.setVisible(False)
        rc = QVBoxLayout(self._response_card)
        rc.setContentsMargins(24, 18, 24, 18)
        rc.setSpacing(8)

        self._response_tag = QLabel("MindOS")
        self._response_tag.setStyleSheet(
            "color:rgba(255,255,255,0.28);font-size:10px;font-weight:600;"
            "letter-spacing:0.1em;background:transparent;")
        rc.addWidget(self._response_tag)

        self._response_text = QTextEdit()
        self._response_text.setReadOnly(True)
        self._response_text.setFrameShape(QFrame.Shape.NoFrame)
        self._response_text.setStyleSheet(
            "background:transparent;color:rgba(255,255,255,0.82);"
            "font-size:14px;line-height:1.6;border:none;")
        self._response_text.setMinimumHeight(80)
        self._response_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        rc.addWidget(self._response_text)

        clear_btn = QPushButton("Clear")
        clear_btn.setProperty("action", "ghost")
        clear_btn.setFixedWidth(64)
        clear_btn.clicked.connect(self._clear)
        rc.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        rv.addWidget(self._response_card)
        cl.addWidget(resp_wrap)

        # ── Overview cards (Today / Tasks)
        overview_wrap = QWidget()
        overview_wrap.setStyleSheet("background:#000000;")
        ov = QHBoxLayout(overview_wrap)
        ov.setContentsMargins(80, 28, 80, 0)
        ov.setSpacing(16)

        # Today's reminders card
        self._today_card = QFrame()
        self._today_card.setProperty("card", "true")
        self._today_card_layout = QVBoxLayout(self._today_card)
        self._today_card_layout.setContentsMargins(24, 18, 24, 18)
        self._today_card_layout.setSpacing(0)
        self._today_head = QLabel("\U0001f4c5  Due Today")
        self._today_head.setProperty("role", "card-head")
        self._today_head.setStyleSheet(
            "color:rgba(255,255,255,0.3);font-size:10px;font-weight:600;"
            "letter-spacing:0.1em;background:transparent;margin-bottom:10px;")
        self._today_card_layout.addWidget(self._today_head)
        self._today_items_layout = QVBoxLayout()
        self._today_items_layout.setSpacing(0)
        self._today_card_layout.addLayout(self._today_items_layout)

        # Pending tasks card
        self._task_card = QFrame()
        self._task_card.setProperty("card", "true")
        self._task_card_layout = QVBoxLayout(self._task_card)
        self._task_card_layout.setContentsMargins(24, 18, 24, 18)
        self._task_card_layout.setSpacing(0)
        self._task_head = QLabel("\u2713  Pending Tasks")
        self._task_head.setProperty("role", "card-head")
        self._task_head.setStyleSheet(
            "color:rgba(255,255,255,0.3);font-size:10px;font-weight:600;"
            "letter-spacing:0.1em;background:transparent;margin-bottom:10px;")
        self._task_card_layout.addWidget(self._task_head)
        self._task_items_layout = QVBoxLayout()
        self._task_items_layout.setSpacing(0)
        self._task_card_layout.addLayout(self._task_items_layout)

        ov.addWidget(self._today_card, 1)
        ov.addWidget(self._task_card, 1)
        cl.addWidget(overview_wrap)
        cl.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self):
        tasks    = get_all_tasks()
        pending  = [t for t in tasks if not t["done"]]
        high_ct  = sum(1 for t in pending if t["high"])
        done_ct  = len(tasks) - len(pending)

        reminders    = get_all_reminders()
        active_rem   = [r for r in reminders if not r.done]
        overdue      = [r for r in active_rem if r.is_past]
        today_rem    = [r for r in active_rem if r.is_today]
        upcoming_rem = [r for r in active_rem if not r.is_past and not r.is_today]

        # Stat pills
        while self._stats_row.count():
            item = self._stats_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._stats_row.addWidget(StatPill(str(len(active_rem)), "Reminders", "#0071e3"))
        self._stats_row.addWidget(StatPill(str(len(pending)), "Pending Tasks"))
        self._stats_row.addWidget(StatPill(str(high_ct), "High Priority", "#ff453a"))
        self._stats_row.addWidget(StatPill(str(done_ct), "Completed", "#30d158"))

        # Today's reminders
        self._clear_layout(self._today_items_layout)
        all_today = overdue + today_rem
        if all_today:
            for r in all_today[:5]:
                self._today_items_layout.addWidget(TodayReminderItem(r))
        else:
            lbl = QLabel("Nothing due today.")
            lbl.setStyleSheet(
                "color:rgba(255,255,255,0.18);font-style:italic;"
                "font-size:12.5px;background:transparent;padding:4px 0;")
            self._today_items_layout.addWidget(lbl)

        # Pending tasks
        self._clear_layout(self._task_items_layout)
        if pending:
            for t in pending[:5]:
                color = "#ff453a" if t["high"] else "rgba(255,255,255,0.72)"
                badge = "  [HIGH]" if t["high"] else ""
                lbl = QLabel(f"\u2610 {t['text']}{badge}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(
                    f"color:{color};font-size:12.5px;"
                    "background:transparent;padding:4px 0;letter-spacing:-0.05px;")
                self._task_items_layout.addWidget(lbl)
        else:
            lbl = QLabel("No pending tasks.")
            lbl.setStyleSheet(
                "color:rgba(255,255,255,0.18);font-style:italic;"
                "font-size:12.5px;background:transparent;padding:4px 0;")
            self._task_items_layout.addWidget(lbl)

    # ── AI pipeline (unified with Chat) ───────────────────────────────────────

    def _send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return

        self._input.clear()
        self._input.setEnabled(False)
        self._send_btn.setEnabled(False)
        self._response_card.setVisible(True)
        self._response_text.setPlainText("Working\u2026")
        self._response_tag.setText("MindOS \u00b7 processing")
        self._pending_user = text

        # Pull history from shared ConversationManager
        history = self._mw.conversation_manager.get_history() if self._mw else []

        self._worker = AIWorker(text, history, mode="dashboard")
        self._worker.result_ready.connect(self._on_result)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_result(self, reply: str, new_history: list):
        self._response_text.setPlainText(reply)
        self._response_tag.setText(f'MindOS \u00b7 "{self._pending_user[:70]}"')

        # Persist updated history
        if self._mw:
            self._mw.conversation_manager.set_history(new_history)
            # Refresh all panels so disk state is reflected immediately
            self._mw.refresh_all_views()

    def _on_done(self):
        self._worker = None
        self._input.setEnabled(True)
        self._send_btn.setEnabled(True)
        self._input.setFocus()

    def _clear(self):
        self._response_card.setVisible(False)
        self._response_text.clear()
        self._input.setFocus()
