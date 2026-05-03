"""
ui/main_window.py — Main application window: top nav bar + stacked content area.

Changes from previous version:
  - ConversationManager singleton lives here (self.conversation_manager)
  - refresh_all_views() method refreshes all data-driven panels after any AI turn
  - Views are constructed with main_window=self so they can access both
"""
import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from core.ai_engine          import ollama_status
from core.conversation_manager import ConversationManager
import core.memory_manager as memory_manager

from ui.dashboard      import DashboardView
from ui.chat_view      import ChatView
from ui.tasks_view     import TasksView
from ui.ideas_view     import IdeasView
from ui.graph_view     import GraphView
from ui.reminders_view import RemindersView
from ui.flash_view     import FlashView
from ui.gemini_view    import GeminiView


PAGES = ["Dashboard", "Chat", "Gemini", "Flash", "Reminders", "Tasks", "Ideas", "Graph"]
ICONS = {
    "Dashboard": "⌂",
    "Chat":      "◎",
    "Gemini":    "✨",
    "Flash":     "⚡",
    "Reminders": "🔔",
    "Tasks":     "✓",
    "Ideas":     "✦",
    "Graph":     "◉",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MindOS")
        self.setMinimumSize(1100, 700)
        self.showMaximized()

        # ── Shared state ──────────────────────────────────────────────────────
        self.conversation_manager = ConversationManager()

        self._nav_btns: dict[str, QPushButton] = {}
        self._current_page = "Dashboard"

        self._build_ui()
        self._nav_to("Dashboard", startup=True)

        # Sync vault in background shortly after startup
        QTimer.singleShot(600, self._background_sync)

        # Ollama status poll every 30 s
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(30_000)
        self._update_status()

        # Reminder notification check every 60 s
        self._notification_timer = QTimer()
        self._notification_timer.timeout.connect(self._check_reminders)
        self._notification_timer.start(60_000)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet("background: #000000;")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Nav bar
        nav = QFrame()
        nav.setObjectName("navBar")
        nav.setFixedHeight(52)
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(20, 0, 20, 0)
        nav_layout.setSpacing(4)

        logo = QLabel("  🧠  MindOS")
        logo.setObjectName("navLogo")
        logo.setFixedWidth(130)
        nav_layout.addWidget(logo)

        self._restart_btn = QPushButton("↻ Restart")
        self._restart_btn.setObjectName("restartBtn")
        self._restart_btn.setProperty("nav", "true")
        self._restart_btn.setFixedHeight(34)
        self._restart_btn.setFixedWidth(90)
        self._restart_btn.clicked.connect(self._restart_app)
        nav_layout.addWidget(self._restart_btn)

        nav_layout.addStretch()

        for page in PAGES:
            btn = QPushButton(f"{ICONS[page]}  {page}")
            btn.setProperty("nav", "true")
            btn.setProperty("active", "false")
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _, p=page: self._nav_to(p))
            self._nav_btns[page] = btn
            nav_layout.addWidget(btn)

        nav_layout.addStretch()

        self._status_dot   = QLabel("●")
        self._status_label = QLabel("Checking…")
        self._status_dot.setObjectName("statusDot")
        self._status_label.setObjectName("statusDot")
        nav_layout.addWidget(self._status_dot)
        nav_layout.addWidget(self._status_label)
        nav_layout.addSpacing(8)

        root.addWidget(nav)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255,255,255,0.055); border: none;")
        root.addWidget(sep)

        # ── Content stack — pass self (main_window) to each view
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: #000000;")

        self._views: dict[str, QWidget] = {}
        constructors = {
            "Dashboard": DashboardView,
            "Chat":      ChatView,
            "Gemini":    GeminiView,
            "Flash":     FlashView,
            "Reminders": RemindersView,
            "Tasks":     TasksView,
            "Ideas":     IdeasView,
            "Graph":     GraphView,
        }
        for page, cls in constructors.items():
            # Views that need the main_window reference accept it as first arg
            if page in ("Dashboard", "Chat", "Gemini"):
                view = cls(main_window=self)
            else:
                view = cls()
            self._views[page] = view
            self._stack.addWidget(view)

        root.addWidget(self._stack, 1)

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _nav_to(self, page: str, startup: bool = False):
        self._current_page = page

        for name, btn in self._nav_btns.items():
            btn.setProperty("active", "true" if name == page else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._stack.setCurrentWidget(self._views[page])

        if not startup:
            view = self._views[page]
            if hasattr(view, "refresh"):
                view.refresh()

    # ── Live data refresh ──────────────────────────────────────────────────────

    def refresh_all_views(self) -> None:
        """
        Called after every AI response.
        Re-reads vault files and pushes fresh data into every panel.
        Ensures UI always reflects the current state of disk.
        """
        for page in ("Dashboard", "Tasks", "Reminders", "Ideas"):
            view = self._views.get(page)
            if view and hasattr(view, "refresh"):
                try:
                    view.refresh()
                except Exception as e:
                    print(f"refresh error [{page}]: {e}")

    # ── Background tasks ────────────────────────────────────────────────────────

    def _background_sync(self):
        from PyQt6.QtCore import QThread

        class SyncWorker(QThread):
            def run(self_inner):
                try:
                    memory_manager.sync_vault()
                except Exception:
                    pass

        self._sync_worker = SyncWorker()
        self._sync_worker.start()

    def _update_status(self):
        online = ollama_status()
        if online:
            self._status_dot.setStyleSheet(
                "color: #30d158; background: transparent; font-size: 9px;")
            self._status_label.setText("Ollama online")
            self._status_label.setStyleSheet(
                "color: rgba(255,255,255,0.35); font-size: 11.5px; background: transparent;")
        else:
            self._status_dot.setStyleSheet(
                "color: #ff453a; background: transparent; font-size: 9px;")
            self._status_label.setText("Ollama offline")
            self._status_label.setStyleSheet(
                "color: rgba(255,255,255,0.35); font-size: 11.5px; background: transparent;")

    def _check_reminders(self):
        from core.reminder_manager import get_all_active_reminders, mark_done
        from datetime import datetime
        import requests

        try:
            reminders = get_all_active_reminders()
            now = datetime.now()
            
            for r in reminders:
                # If there's no specific time (all_day), we don't send a push notification
                if r.all_day or not r.dt:
                    continue
                
                if "#gemini" in r.text.lower():
                    if r.dt.year == now.year and r.dt.month == now.month and r.dt.day == now.day:
                        if r.dt.hour == now.hour and r.dt.minute == now.minute:
                            text_clean = r.text.replace("#gemini", "").strip()
                            try:
                                requests.post(
                                    "https://ntfy.sh/mindos_seven",
                                    data=text_clean.encode('utf-8'),
                                    headers={
                                        "Title": "🤖 MindOS Gemini Reminder",
                                        "Tags": "robot,bell",
                                        "Priority": "high"
                                    },
                                    timeout=5
                                )
                            except Exception as e:
                                print(f"Failed to post to ntfy: {e}")
                            
                            # Mark done to avoid spamming the user
                            mark_done(r.text)
                            # Refresh views since the reminder is now done
                            self.refresh_all_views()
        except Exception as e:
            print(f"Reminder background check error: {e}")

    def _restart_app(self):
        import sys
        import subprocess
        from PyQt6.QtWidgets import QApplication
        
        subprocess.Popen([sys.executable] + sys.argv)
        QApplication.instance().quit()

