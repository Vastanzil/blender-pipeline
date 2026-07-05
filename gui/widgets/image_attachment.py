"""
gui/widgets/image_attachment.py
Thumbnail strip widget for attaching reference images to the AI prompt.
Supports file dialog, drag-and-drop, and per-image remove buttons.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QLabel,
                              QScrollArea, QFileDialog, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent


_THUMB_SIZE = 64
_ACCEPTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


class _Thumb(QWidget):
    removed = pyqtSignal(str)  # emits file path

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        lbl = QLabel()
        px = QPixmap(path)
        if not px.isNull():
            px = px.scaled(_THUMB_SIZE, _THUMB_SIZE,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        lbl.setPixmap(px)
        lbl.setToolTip(path)
        layout.addWidget(lbl)

        rm = QPushButton("✕")
        rm.setFixedSize(16, 16)
        rm.setStyleSheet("font-size:9px; padding:0; border-radius:8px;")
        rm.clicked.connect(lambda: self.removed.emit(self._path))
        layout.addWidget(rm, 0, Qt.AlignmentFlag.AlignTop)

        self.setFixedHeight(_THUMB_SIZE + 8)


class ImageAttachmentWidget(QWidget):
    """Horizontal thumbnail strip for attaching reference images."""

    images_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: list[str] = []
        self.setAcceptDrops(True)
        self._build()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self._add_btn = QPushButton("📎 Add Image")
        self._add_btn.setFixedHeight(28)
        self._add_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._add_btn.clicked.connect(self._browse)
        outer.addWidget(self._add_btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(_THUMB_SIZE + 20)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._strip_widget = QWidget()
        self._strip_layout = QHBoxLayout(self._strip_widget)
        self._strip_layout.setContentsMargins(0, 0, 0, 0)
        self._strip_layout.setSpacing(4)
        self._strip_layout.addStretch()

        scroll.setWidget(self._strip_widget)
        outer.addWidget(scroll, 1)

        self.setFixedHeight(_THUMB_SIZE + 24)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def images(self) -> list[str]:
        return list(self._paths)

    def clear(self):
        self._paths.clear()
        self._rebuild_strip()
        self.images_changed.emit()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _browse(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select reference images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        for p in paths:
            self._add(p)

    def _add(self, path: str):
        if path in self._paths:
            return
        if Path(path).suffix.lower() not in _ACCEPTED_EXTS:
            return
        self._paths.append(path)
        self._rebuild_strip()
        self.images_changed.emit()

    def _remove(self, path: str):
        if path in self._paths:
            self._paths.remove(path)
            self._rebuild_strip()
            self.images_changed.emit()

    def _rebuild_strip(self):
        # Remove all thumb widgets (leave the stretch at the end)
        while self._strip_layout.count() > 1:
            item = self._strip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for path in self._paths:
            thumb = _Thumb(path, self._strip_widget)
            thumb.removed.connect(self._remove)
            self._strip_layout.insertWidget(self._strip_layout.count() - 1, thumb)

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self._add(path)
