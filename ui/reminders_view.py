"""
ui/reminders_view.py — Active reminders read-only view.

Shows ONLY active (non-completed) reminders grouped by: Overdue / Today / Upcoming.
Each reminder has Edit and Delete buttons.
To add a new reminder → use the Dashboard input.
"""
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QDialog, QCheckBox,
    QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal

# New import sources (reminder_manager is no longer the canonical module)
from core.memory_manager import Reminder, load_reminders
from core.tool_executor  import save_all_reminders_raw as save_all_reminders

try:
    from dateutil import parser as du_parser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False


# ── Edit dialog ───────────────────────────────────────────────────────────────

class EditReminderDialog(QDialog):
    def __init__(self, reminder: Reminder, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Reminder")
        self.setMinimumWidth(460)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog { background:#0d0d0d; }
            QLabel { color:rgba(255,255,255,0.42); font-size:11px; font-weight:600;
                     letter-spacing:0.08em; background:transparent; }
            QLineEdit { background:rgba(255,255,255,0.05); border:1.5px solid rgba(255,255,255,0.1);
                        border-radius:10px; color:#fff; padding:10px 14px; font-size:14px; }
            QLineEdit:focus { border-color:#0071e3; }
            QCheckBox { color:rgba(255,255,255,0.62); font-size:13px; background:transparent; }
            QCheckBox::indicator { width:16px; height:16px; border:1.5px solid rgba(255,255,255,0.22);
                                   border-radius:4px; background:transparent; }
            QCheckBox::indicator:checked { background:#0071e3; border-color:#0071e3; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 22)
        root.setSpacing(14)

        hdr = QLabel("Edit Reminder")
        hdr.setStyleSheet("color:#fff;font-size:17px;font-weight:600;"
                          "letter-spacing:-0.3px;background:transparent;")
        root.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,0.07);border:none;max-height:1px;")
        root.addWidget(sep)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet("color:rgba(255,255,255,0.35);font-size:10.5px;font-weight:600;"
                            "letter-spacing:0.08em;background:transparent;margin-bottom:-6px;")
            return l

        root.addWidget(lbl("Reminder"))
        self._text = QLineEdit(reminder.text)
        self._text.setPlaceholderText("What to remind you about…")
        root.addWidget(self._text)

        root.addWidget(lbl("Date"))
        try:
            dv = reminder.dt.strftime("%B %-d, %Y")
        except ValueError:
            dv = reminder.dt.strftime("%B %d, %Y")
        self._date = QLineEdit(dv)
        self._date.setPlaceholderText("April 20, 2026 / tomorrow / next Monday")
        root.addWidget(self._date)

        self._allday = QCheckBox("All day (no specific time)")
        self._allday.setChecked(reminder.all_day)
        self._allday.toggled.connect(self._toggle_time)
        root.addWidget(self._allday)

        root.addWidget(lbl("Time"))
        tv = "" if reminder.all_day else reminder.dt.strftime("%I:%M %p")
        self._time = QLineEdit(tv)
        self._time.setPlaceholderText("3:00 PM / 15:00 / 9am")
        self._time.setEnabled(not reminder.all_day)
        root.addWidget(self._time)

        self._err = QLabel("")
        self._err.setStyleSheet("color:#ff453a;font-size:12px;background:transparent;")
        self._err.setVisible(False)
        root.addWidget(self._err)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet("background:rgba(255,255,255,0.07);color:rgba(255,255,255,0.7);"
                             "border:none;border-radius:980px;padding:9px 20px;font-size:14px;")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Changes")
        save.setStyleSheet("background:#0071e3;color:#fff;border:none;"
                           "border-radius:980px;padding:9px 22px;font-size:14px;font-weight:500;")
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

        self._result: Reminder | None = None

    def _toggle_time(self, checked):
        self._time.setEnabled(not checked)
        self._time.setPlaceholderText(
            "(all day — no time)" if checked else "3:00 PM / 15:00 / 9am")
        if checked:
            self._time.clear()

    def _save(self):
        import re
        from datetime import date as ddate, timedelta

        text = self._text.text().strip()
        date_s = self._date.text().strip()
        time_s = self._time.text().strip()
        all_day = self._allday.isChecked()

        if not text:
            self._show("Reminder text cannot be empty.")
            return
        if not date_s:
            self._show("Please enter a date.")
            return

        # Parse date
        d = None
        sl = date_s.lower()
        if sl == "today":
            d = ddate.today()
        elif sl == "tomorrow":
            d = ddate.today() + timedelta(days=1)
        elif HAS_DATEUTIL:
            try:
                d = du_parser.parse(date_s, default=datetime.now()).date()
            except Exception:
                pass
        if d is None:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y",
                        "%b %d, %Y", "%B %d %Y", "%b %d %Y", "%B %d", "%b %d"):
                try:
                    parsed = datetime.strptime(date_s, fmt)
                    d = parsed.date()
                    if d.year == 1900:
                        from datetime import date as ddate2
                        d = d.replace(year=ddate2.today().year)
                    break
                except ValueError:
                    continue
        if d is None:
            self._show(f"Couldn't understand date: '{date_s}'")
            return

        # Parse time
        if all_day or not time_s:
            dt = datetime(d.year, d.month, d.day)
            all_day = True
        else:
            m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)?", time_s)
            if not m:
                self._show(f"Couldn't understand time: '{time_s}'")
                return
            h, mi = int(m.group(1)), int(m.group(2) or 0)
            ampm = (m.group(3) or "").lower()
            if ampm == "pm" and h != 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
            dt = datetime(d.year, d.month, d.day, h, mi)

        self._result = Reminder(text=text, dt=dt, all_day=all_day, done=False)
        self.accept()

    def _show(self, msg):
        self._err.setText(f"⚠ {msg}")
        self._err.setVisible(True)

    @property
    def result_reminder(self):
        return self._result


# ── Single reminder row ───────────────────────────────────────────────────────

class ReminderItem(QFrame):
    edit_requested   = pyqtSignal(object)
    delete_requested = pyqtSignal(object)

    def __init__(self, reminder: Reminder, parent=None):
        super().__init__(parent)
        self._r = reminder
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._build()

    def _build(self):
        r = self._r
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 12, 0, 12)
        row.setSpacing(14)

        # Status dot
        dot = QLabel()
        dot.setFixedSize(11, 11)
        if r.is_past:
            dot.setStyleSheet("background:#ff453a;border-radius:5px;")
        elif r.is_today:
            dot.setStyleSheet("background:#0071e3;border-radius:5px;")
        else:
            dot.setStyleSheet(
                "border:1.5px solid rgba(255,255,255,0.2);border-radius:5px;"
                "background:transparent;")
        row.addWidget(dot)

        # Text column
        col = QVBoxLayout()
        col.setSpacing(3)

        name = QLabel(r.text)
        name.setWordWrap(True)
        name.setStyleSheet(
            "color:rgba(255,255,255,0.88);font-size:14px;"
            "letter-spacing:-0.1px;background:transparent;")
        col.addWidget(name)

        try:
            day = r.dt.strftime("%A, %B %-d, %Y")
        except ValueError:
            day = r.dt.strftime("%A, %B %d, %Y")
        time_part = "(all day)" if r.all_day else r.dt.strftime("%I:%M %p")
        badge = (" · ⚠ OVERDUE" if r.is_past else
                 " · TODAY"    if r.is_today else "")
        when = QLabel(f"{day}  ·  {time_part}{badge}")
        c = "#ff453a" if r.is_past else ("#0071e3" if r.is_today else "rgba(255,255,255,0.32)")
        when.setStyleSheet(
            f"color:{c};font-size:11px;font-weight:500;"
            f"letter-spacing:0.01em;background:transparent;")
        col.addWidget(when)
        row.addLayout(col, 1)

        # Buttons
        edit = QPushButton("Edit")
        edit.setFixedSize(56, 28)
        edit.setStyleSheet(
            "background:rgba(255,255,255,0.07);color:rgba(255,255,255,0.6);"
            "border:none;border-radius:7px;font-size:12px;font-weight:500;")
        edit.clicked.connect(lambda: self.edit_requested.emit(self._r))
        row.addWidget(edit)

        delete = QPushButton("Delete")
        delete.setFixedSize(62, 28)
        delete.setStyleSheet(
            "background:rgba(255,69,58,0.1);color:#ff453a;"
            "border:none;border-radius:7px;font-size:12px;font-weight:500;")
        delete.clicked.connect(lambda: self.delete_requested.emit(self._r))
        row.addWidget(delete)

        outer.addLayout(row)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,0.055);border:none;max-height:1px;")
        outer.addWidget(sep)


# ── Section heading ───────────────────────────────────────────────────────────

def _section_lbl(text, color="rgba(255,255,255,0.28)"):
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{color};font-size:10px;font-weight:600;"
        f"letter-spacing:0.1em;background:transparent;padding:14px 0 4px;")
    return l


# ── Main view ─────────────────────────────────────────────────────────────────

class RemindersView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._reminders: list[Reminder] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet("background:#000000;")
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(48, 52, 48, 24)
        hl.setSpacing(4)

        eyebrow = QLabel("Time-Based Memory")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("Reminders")
        title.setProperty("role", "page-title")
        sub = QLabel("All your active reminders. Use Dashboard to add new ones.")
        sub.setProperty("role", "sub")

        hl.addWidget(eyebrow)
        hl.addWidget(title)
        hl.addWidget(sub)
        root.addWidget(hdr)

        # Scrollable list
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

        # List card
        self._card = QFrame()
        self._card.setProperty("card", "true")
        self._card_layout = QVBoxLayout(self._card)
        self._card_layout.setContentsMargins(24, 18, 24, 18)
        self._card_layout.setSpacing(0)

        self._count_lbl = QLabel()
        self._count_lbl.setProperty("role", "card-head")
        self._card_layout.addWidget(self._count_lbl)

        self._list_layout = QVBoxLayout()
        self._list_layout.setContentsMargins(0, 4, 0, 0)
        self._list_layout.setSpacing(0)
        self._card_layout.addLayout(self._list_layout)

        bl.addWidget(self._card)
        bl.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_edit(self, reminder: Reminder):
        dlg = EditReminderDialog(reminder, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_reminder:
            new_r = dlg.result_reminder
            updated, replaced = [], False
            for r in self._reminders:
                if not replaced and r.text == reminder.text and r.dt == reminder.dt:
                    updated.append(new_r)
                    replaced = True
                else:
                    updated.append(r)
            if not replaced:
                updated.append(new_r)
            self._reminders = updated
            save_all_reminders(self._reminders)
            self.refresh()

    def _on_delete(self, reminder: Reminder):
        self._reminders = [
            r for r in self._reminders
            if not (r.text == reminder.text and r.dt == reminder.dt)
        ]
        save_all_reminders(self._reminders)
        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        self._reminders = load_reminders()
        active = [r for r in self._reminders if not r.done]

        n = len(active)
        self._count_lbl.setText(f"{n} active reminder{'s' if n != 1 else ''}")

        # Clear list
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not active:
            empty = QLabel(
                "No active reminders.\nUse the Dashboard to set one — "
                "just type \"Remind me to…\"")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "color:rgba(255,255,255,0.18);font-style:italic;"
                "font-size:13px;background:transparent;padding:20px 0;")
            self._list_layout.addWidget(empty)
            return

        overdue  = [r for r in active if r.is_past]
        today    = [r for r in active if r.is_today]
        upcoming = [r for r in active if not r.is_past and not r.is_today]

        if overdue:
            self._list_layout.addWidget(_section_lbl("⚠  Overdue", "#ff453a"))
            for r in overdue:
                self._add_row(r)
        if today:
            self._list_layout.addWidget(_section_lbl("Today", "#0071e3"))
            for r in today:
                self._add_row(r)
        if upcoming:
            self._list_layout.addWidget(
                _section_lbl("Upcoming", "rgba(255,255,255,0.28)"))
            for r in upcoming:
                self._add_row(r)

    def _add_row(self, r: Reminder):
        row = ReminderItem(r)
        row.edit_requested.connect(self._on_edit)
        row.delete_requested.connect(self._on_delete)
        self._list_layout.addWidget(row)
