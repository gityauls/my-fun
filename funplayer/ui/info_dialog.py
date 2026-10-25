from __future__ import annotations

import logging
import os
import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from funplayer.core.taginfo import TrackInfo, format_line, format_size
from funplayer.core.timefmt import format_time
from funplayer.ui.cover import art_pixmap

log = logging.getLogger(__name__)

DASH = "—"
ART_SIZE = 160
FIELDS = ["제목", "가수", "앨범", "년도", "장르", "트랙", "길이", "형식", "크기"]


# 탐색기에서 파일을 고른 채 열고, 파일이 없으면 폴더를 연다
def reveal_in_explorer(path: str) -> None:
    try:
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            folder = os.path.dirname(path)
            if os.path.isdir(folder):
                os.startfile(folder)
    except OSError as e:
        log.warning("탐색기를 열지 못했습니다: %s", e)


def _selectable(label: QLabel) -> QLabel:
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


class TrackInfoDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("곡 정보")
        self.setModal(False)
        self._path = ""

        self.art_label = QLabel()
        self.art_label.setFixedSize(ART_SIZE, ART_SIZE)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setColumnStretch(1, 1)
        self.value_labels: dict[str, QLabel] = {}
        for row, key in enumerate(FIELDS):
            name = QLabel(key)
            name.setStyleSheet("color: #5F6368;")
            value = _selectable(QLabel(DASH))
            value.setWordWrap(True)
            grid.addWidget(name, row, 0, Qt.AlignTop)
            grid.addWidget(value, row, 1)
            self.value_labels[key] = value

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self.art_label, 0, Qt.AlignTop)
        top.addLayout(grid, 1)

        path_name = QLabel("경로")
        path_name.setStyleSheet("color: #5F6368;")
        self.path_label = _selectable(QLabel())
        self.path_label.setWordWrap(True)
        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        path_row.addWidget(path_name, 0, Qt.AlignTop)
        path_row.addWidget(self.path_label, 1)

        self.folder_button = QPushButton("폴더 열기")
        self.close_button = QPushButton("닫기")
        self.close_button.setDefault(True)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.folder_button)
        buttons.addWidget(self.close_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)
        root.addLayout(top)
        root.addLayout(path_row)
        root.addLayout(buttons)

        self.folder_button.clicked.connect(lambda _=False: reveal_in_explorer(self._path))
        self.close_button.clicked.connect(self.close)
        self.setMinimumWidth(460)

    def show_info(self, info: TrackInfo, cover: QPixmap | None) -> None:
        self._path = info.path
        self.art_label.setPixmap(art_pixmap(cover, ART_SIZE))
        values = {
            "제목": info.title, "가수": info.artist, "앨범": info.album,
            "년도": info.year, "장르": info.genre, "트랙": info.track,
            "길이": format_time(info.duration) if info.duration > 0 else "",
            "형식": format_line(info), "크기": format_size(info.size),
        }
        for key, label in self.value_labels.items():
            label.setText(values[key] or DASH)
        self.path_label.setText(info.path)
        self.folder_button.setEnabled(
            os.path.isfile(info.path) or os.path.isdir(os.path.dirname(info.path)))
