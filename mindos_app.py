"""
mindos_app.py — MindOS Desktop Application Entry Point.

Run:
    python mindos_app.py

Or from .venv:
    .venv\\Scripts\\python mindos_app.py
"""
import os
import sys

# ── venv bootstrapper ─────────────────────────────────────────────────────────
_HERE    = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(_HERE, ".venv", "Scripts", "python.exe")
if os.path.exists(_VENV_PY) and os.path.abspath(sys.executable).lower() != _VENV_PY.lower():
    import subprocess
    sys.exit(subprocess.call([_VENV_PY, __file__] + sys.argv[1:]))

# ── ensure project root is on sys.path ────────────────────────────────────────
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── suppress noisy warnings ───────────────────────────────────────────────────
import warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# ── PyQt6 ────────────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow


def _load_stylesheet(app: QApplication) -> None:
    qss_path = os.path.join(_HERE, "assets", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("MindOS")
    app.setApplicationDisplayName("MindOS")
    app.setOrganizationName("MindOS")

    # High-DPI is always enabled in Qt6 — no setAttribute needed

    # System font hint
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    _load_stylesheet(app)

    window = MainWindow()
    window.show()
    window.raise_()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
