from __future__ import annotations

import logging
import math
import os
import subprocess

from PyQt5.QtCore import QPointF, QSize, Qt
from PyQt5.QtGui import QPixmap, QTextLayout, QTextOption
from PyQt5.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout,
)

from funplayer.core.taginfo import TrackInfo, format_line, format_size
from funplayer.core.timefmt import format_time
from funplayer.ui.cover import art_pixmap

log = logging.getLogger(__name__)

DASH = "—"
ART_SIZE = 160
FIELDS = ["제목", "가수", "앨범", "년도", "장르", "트랙", "길이", "형식", "크기"]
# 값 칸 최소 폭의 기준: 흔한 형식 줄 가운데 가장 긴 모양이 한 줄에 들어가게 한다
WIDEST_FORMAT = "MP3 · 320 kbps · 44.1 kHz · 스테레오"


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


class PathBox(QPlainTextEdit):
    """경로 칸: 빈칸이 없어도 아무 데서나 줄을 바꾸고, 줄 수만큼 높이를 맞춘 읽기 전용 글 상자."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setFocusPolicy(Qt.ClickFocus)   # 눌렀을 때만 포커스: Ctrl+C 복사는 되고 Tab 순서는 그대로
        self.setFrameShape(QFrame.NoFrame)
        self.viewport().setAutoFillBackground(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDocumentMargin(0)
        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.document().documentLayout().documentSizeChanged.connect(lambda _size: self.updateGeometry())

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self.setPlainText(text)
        self.updateGeometry()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        # QPlainTextDocumentLayout과 같은 방법(같은 글꼴·줄바꿈, 줄 간격 포함)으로 줄을 놓아 높이를 잰다
        doc = self.document()
        margin = doc.documentMargin()
        frame = 2 * self.frameWidth()
        layout = QTextLayout(self.toPlainText(), doc.defaultFont())
        layout.setTextOption(doc.defaultTextOption())
        layout.beginLayout()
        height = 0.0
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLeadingIncluded(True)
            line.setLineWidth(max(1.0, width - frame - 2 * margin))
            line.setPosition(QPointF(margin, height))
            height += line.height()
        layout.endLayout()
        height = max(height, float(self.fontMetrics().lineSpacing()))
        return math.ceil(height + 2 * margin) + frame + 1   # +1: 스크롤 계산이 보는 칸은 뷰포트보다 1px 작다

    def sizeHint(self) -> QSize:
        w = self.fontMetrics().averageCharWidth() * 30
        return QSize(w, self.heightForWidth(w))

    def minimumSizeHint(self) -> QSize:
        w = self.fontMetrics().averageCharWidth() * 10
        return QSize(w, self.heightForWidth(10 ** 6))


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
        grid.setRowStretch(len(FIELDS), 1)   # 줄들을 위로 모으고 남는 높이는 맨 아래 빈 줄이 갖는다
        fm = self.value_labels["형식"].fontMetrics()
        grid.setColumnMinimumWidth(1, fm.horizontalAdvance(WIDEST_FORMAT) + fm.averageCharWidth())

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self.art_label, 0, Qt.AlignTop)
        top.addLayout(grid, 1)

        path_name = QLabel("경로")
        path_name.setStyleSheet("color: #5F6368;")
        self.path_label = PathBox()
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
        self.adjustSize()   # 줄바꿈된 값까지 다 보이는 높이로
        need = self.layout().totalHeightForWidth(self.width())
        if self.height() < need:   # adjustSize는 화면 높이의 2/3에서 자르므로 모자라면 더 키운다
            self.resize(self.width(), need)
