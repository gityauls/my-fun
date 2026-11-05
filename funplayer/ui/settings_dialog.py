"""Settings dialog (stage 5.5): pick the colour theme. Picking previews live (the panel listens
to `themePicked`); the panel saves on accept and restores on reject."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
                             QVBoxLayout)

from funplayer.core.themes import THEMES, Theme

DOT = 14
GAP = 4
DOT_FIELDS = ("g2", "acc", "acc2", "tint", "track")


def solid_colors(theme: Theme) -> list[QColor]:
    """The theme's dot colours, skipping gradients and translucent values."""
    out = []
    for name in DOT_FIELDS:
        value = getattr(theme, name)
        if value.startswith("#") and QColor.isValidColor(value):
            out.append(QColor(value))
    return out


def dots_icon(theme: Theme) -> QIcon:
    colors = solid_colors(theme)
    width = max(1, len(colors) * DOT + max(0, len(colors) - 1) * GAP)
    pm = QPixmap(width, DOT)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(0, 0, 0, 40))
    for i, c in enumerate(colors):
        p.setBrush(c)
        p.drawEllipse(i * (DOT + GAP), 0, DOT - 1, DOT - 1)
    p.end()
    return QIcon(pm)


class SettingsDialog(QDialog):
    themePicked = pyqtSignal(str)

    def __init__(self, current_id: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.original_id = current_id
        col = QVBoxLayout(self)
        col.addWidget(QLabel("색 테마"))
        self.theme_list = QListWidget()
        self.theme_list.setIconSize(QSize(5 * DOT + 4 * GAP, DOT))
        self.theme_list.setMinimumWidth(300)
        for t in THEMES:
            item = QListWidgetItem(dots_icon(t), t.name)
            item.setData(Qt.UserRole, t.id)
            item.setToolTip(t.desc)
            self.theme_list.addItem(item)
        col.addWidget(self.theme_list)
        self.select(current_id)
        self.theme_list.currentRowChanged.connect(self._row_changed)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("확인")
        buttons.button(QDialogButtonBox.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        col.addWidget(buttons)
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        self.cancel_button = buttons.button(QDialogButtonBox.Cancel)

    def select(self, theme_id: str) -> None:
        """Move the highlight without announcing it."""
        self.theme_list.blockSignals(True)
        for row in range(self.theme_list.count()):
            if self.theme_list.item(row).data(Qt.UserRole) == theme_id:
                self.theme_list.setCurrentRow(row)
        self.theme_list.blockSignals(False)

    def selected_id(self) -> str:
        item = self.theme_list.currentItem()
        return item.data(Qt.UserRole) if item is not None else self.original_id

    def _row_changed(self, row: int) -> None:
        if row >= 0:
            self.themePicked.emit(self.theme_list.item(row).data(Qt.UserRole))
