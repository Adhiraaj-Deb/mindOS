"""
ui/graph_view.py — Interactive knowledge graph using QGraphicsScene.
Nodes = vault .md files  |  Edges = [[wikilink]] relationships
Features: zoom, pan, draggable nodes, glowing colours per folder.
"""
import os
import re
import math

import networkx as nx
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsLineItem, QGraphicsTextItem, QGraphicsItem,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QPainter, QFont,
    QLinearGradient, QRadialGradient, QTransform, QWheelEvent,
)

from core.file_utils import get_all_md_files, VAULT_PATH

# ── Colour palette (folder → glow colour) ─────────────────────────────────────
FOLDER_COLORS = {
    "00_Dashboard": "#0071e3",
    "01_Daily":     "#30d158",
    "02_Tasks":     "#ff453a",
    "03_Projects":  "#ff9f0a",
    "04_Knowledge": "#bf5af2",
    "05_Ideas":     "#ffd60a",
    "06_People":    "#64d2ff",
    "07_Memory":    "#ff375f",
    "_root":        "#888888",
    "_linked":      "#3a3a3a",
}
DEFAULT_COLOR = "#0071e3"


# ── Node item ─────────────────────────────────────────────────────────────────
class NodeItem(QGraphicsEllipseItem):
    def __init__(self, name: str, color: str, size: float = 18):
        r = size / 2
        super().__init__(-r, -r, size, size)
        self.node_name = name
        self.edges: list["EdgeItem"] = []

        # Appearance
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(Qt.PenStyle.NoPen))

        # Interaction flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        # Glow effect
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(22)
        glow.setColor(QColor(color))
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)

        # Label
        self._label = QGraphicsTextItem(name, self)
        font = QFont("Inter", 8)
        self._label.setFont(font)
        self._label.setDefaultTextColor(QColor(255, 255, 255, 160))
        lw = self._label.boundingRect().width()
        self._label.setPos(-lw / 2, r + 3)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_position()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event):
        self.setScale(1.25)
        self._label.setDefaultTextColor(QColor(255, 255, 255, 230))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setScale(1.0)
        self._label.setDefaultTextColor(QColor(255, 255, 255, 160))
        super().hoverLeaveEvent(event)


# ── Edge item ─────────────────────────────────────────────────────────────────
class EdgeItem(QGraphicsLineItem):
    def __init__(self, source: NodeItem, target: NodeItem):
        super().__init__()
        self.source = source
        self.target = target
        self.setPen(QPen(QColor(60, 60, 60, 160), 1.2, Qt.PenStyle.SolidLine))
        self.setZValue(-1)  # behind nodes
        source.edges.append(self)
        target.edges.append(self)
        self.update_position()

    def update_position(self):
        sx, sy = self.source.pos().x(), self.source.pos().y()
        tx, ty = self.target.pos().x(), self.target.pos().y()
        self.setLine(sx, sy, tx, ty)


# ── Graph scene ───────────────────────────────────────────────────────────────
class GraphScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setBackgroundBrush(QBrush(QColor("#000000")))


# ── Zoomable / pannable view ──────────────────────────────────────────────────
class GraphicsView(QGraphicsView):
    def __init__(self, scene: GraphScene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setBackgroundBrush(QBrush(QColor("#000000")))
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._panning = False
        self._pan_start = QPointF()
        self._zoom_level = 1.0

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.14 if event.angleDelta().y() > 0 else 1 / 1.14
        self._zoom_level *= factor
        self._zoom_level = max(0.1, min(self._zoom_level, 8.0))
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item is None:
                self._panning = True
                self._pan_start = self.mapToScene(event.pos())
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            current = self.mapToScene(event.pos())
            delta = current - self._pan_start
            # move scene rect origin
            rect = self.sceneRect()
            self.setSceneRect(rect.translated(-delta.x(), -delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ── Main graph view widget ────────────────────────────────────────────────────
class GraphView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_graph()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(100)
        header.setObjectName("graphHeader")
        header.setStyleSheet("""
            #graphHeader { background: #000000; padding: 0 48px; }
        """)
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(48, 28, 48, 10)
        h_layout.setSpacing(4)

        eyebrow = QLabel("Vault Visualization")
        eyebrow.setProperty("role", "eyebrow")
        title = QLabel("Knowledge Graph")
        title.setProperty("role", "page-title")
        sub = QLabel("Your vault as a living network of connected thought.")
        sub.setProperty("role", "sub")

        h_layout.addWidget(eyebrow)
        h_layout.addWidget(title)
        h_layout.addWidget(sub)
        layout.addWidget(header)

        # Legend
        self._legend_row = QHBoxLayout()
        self._legend_row.setContentsMargins(48, 6, 48, 12)
        self._legend_row.setSpacing(16)
        self._legend_row.addStretch()
        legend_widget = QWidget()
        legend_widget.setLayout(self._legend_row)
        layout.addWidget(legend_widget)

        # Graph area
        self._scene = GraphScene()
        self._view = GraphicsView(self._scene)
        self._view.setStyleSheet("background: #000000; border: none;")
        layout.addWidget(self._view, 1)

    def _build_legend(self, used_folders: set):
        # Clear old
        while self._legend_row.count():
            item = self._legend_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for folder, color in FOLDER_COLORS.items():
            if folder.startswith("_") or folder not in used_folders:
                continue
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
            lbl = QLabel(folder)
            lbl.setStyleSheet("color: rgba(255,255,255,0.4); font-size: 11px; background: transparent;")
            row = QHBoxLayout()
            row.setSpacing(4)
            row.addWidget(dot)
            row.addWidget(lbl)
            w = QWidget()
            w.setLayout(row)
            self._legend_row.addWidget(w)
        self._legend_row.addStretch()

    def _load_graph(self):
        self._scene.clear()
        md_files = get_all_md_files()

        G = nx.Graph()
        file_map: dict[str, str] = {}   # name → file_path
        folder_map: dict[str, str] = {} # name → folder
        wc_map: dict[str, int] = {}     # name → word count

        vault_root = os.path.basename(VAULT_PATH)

        for fp in md_files:
            name   = os.path.splitext(os.path.basename(fp))[0]
            parent = os.path.basename(os.path.dirname(fp))
            folder = parent if parent != vault_root else "_root"
            file_map[name]   = fp
            folder_map[name] = folder
            try:
                content = open(fp, encoding="utf-8").read()
            except Exception:
                content = ""
            wc_map[name] = len(content.split())
            G.add_node(name)
            for lk in re.findall(r"\[\[([^\]|#]+)", content):
                lk = lk.strip()
                if lk:
                    if lk not in folder_map:
                        folder_map[lk] = "_linked"
                    G.add_node(lk)
                    G.add_edge(name, lk)

        if not G.nodes:
            no_data = QGraphicsTextItem("No notes found in vault.")
            no_data.setDefaultTextColor(QColor(255, 255, 255, 80))
            self._scene.addItem(no_data)
            return

        # Force-directed layout
        pos = nx.spring_layout(G, k=3.5, iterations=80, seed=42)
        scale = 480

        used_folders: set[str] = set(folder_map.values())
        self._build_legend(used_folders)

        nodes: dict[str, NodeItem] = {}

        # Draw edges first (lower Z)
        for u, v in G.edges():
            if u in nodes:
                src = nodes[u]
            else:
                c = FOLDER_COLORS.get(folder_map.get(u, "_linked"), DEFAULT_COLOR)
                wc = wc_map.get(u, 0)
                sz = max(12, min(36, 12 + wc // 60))
                x, y = pos[u]
                src = NodeItem(u, c, sz)
                src.setPos(x * scale, y * scale)
                self._scene.addItem(src)
                nodes[u] = src

            if v in nodes:
                tgt = nodes[v]
            else:
                c = FOLDER_COLORS.get(folder_map.get(v, "_linked"), DEFAULT_COLOR)
                wc = wc_map.get(v, 0)
                sz = max(12, min(36, 12 + wc // 60))
                x, y = pos[v]
                tgt = NodeItem(v, c, sz)
                tgt.setPos(x * scale, y * scale)
                self._scene.addItem(tgt)
                nodes[v] = tgt

            edge = EdgeItem(src, tgt)
            self._scene.addItem(edge)

        # Add any isolated nodes
        for name in G.nodes():
            if name not in nodes:
                c = FOLDER_COLORS.get(folder_map.get(name, "_linked"), DEFAULT_COLOR)
                wc = wc_map.get(name, 0)
                sz = max(12, min(36, 12 + wc // 60))
                x, y = pos[name]
                node = NodeItem(name, c, sz)
                node.setPos(x * scale, y * scale)
                self._scene.addItem(node)
                nodes[name] = node

        # Fit view
        self._view.fitInView(
            self._scene.itemsBoundingRect().adjusted(-60, -60, 60, 60),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def refresh(self):
        """Reload graph from vault."""
        self._load_graph()
