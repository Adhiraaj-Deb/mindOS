"""
main.py — MindOS single entry point.

Usage:  python main.py
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# ── Ensure project root on sys.path ─────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── venv auto-bootstrap (optional convenience) ───────────────────────────────────
_VENV_PY = os.path.join(_HERE, ".venv", "Scripts", "python.exe")
if os.path.exists(_VENV_PY) and os.path.abspath(sys.executable).lower() != _VENV_PY.lower():
    import subprocess
    sys.exit(subprocess.call([_VENV_PY, __file__] + sys.argv[1:]))

# ── Imports (after potential venv re-exec) ───────────────────────────────────────
from config import (
    TASKS_FILE, IDEAS_FILE, MEMORY_FILE, REMINDERS_FILE,
    OLLAMA_BASE_URL, GEMINI_MEMORY_FILE
)


def ensure_vault_structure() -> None:
    """Create all required vault files and parent directories if they don't exist."""
    vault_files = {
        TASKS_FILE:     "# Tasks\n",
        IDEAS_FILE:     "# Ideas\n",
        MEMORY_FILE:    "# Memory\n",
        REMINDERS_FILE: "# Reminders\n",
        GEMINI_MEMORY_FILE: "# Gemini Memory\n",
    }
    for filepath, header in vault_files.items():
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(header + "\n")


def check_ollama(app) -> None:
    """Start Ollama natively in the background if it's currently offline."""
    import requests
    import subprocess
    import sys
    try:
        r = requests.get(OLLAMA_BASE_URL, timeout=1)
        if r.status_code == 200:
            return  # already running
    except Exception:
        pass
        
    # If not running, launch it silently without creating a command prompt window
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000 # CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True
            
        subprocess.Popen(["ollama", "serve"], **kwargs)
    except Exception as e:
        print(f"Failed to auto-start Ollama daemon: {e}")


def main() -> int:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont

    # Ensure all vault files exist before UI starts
    ensure_vault_structure()

    app = QApplication(sys.argv)
    app.setApplicationName("MindOS")
    app.setApplicationDisplayName("MindOS")
    app.setOrganizationName("MindOS")

    # Load QSS stylesheet
    qss_path = os.path.join(_HERE, "assets", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # System font
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    # Import and create main window
    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    window.raise_()

    # Non-blocking Ollama check AFTER the window is shown
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(800, lambda: check_ollama(app))

    # Background World Knowledge Daemon
    from core.world_observer import sync_world_state_async
    QTimer.singleShot(1500, sync_world_state_async)  # Fetch immediately async
    
    world_timer = QTimer(app)
    world_timer.timeout.connect(sync_world_state_async)
    world_timer.start(3600000)  # Re-fetch every 60 minutes

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
