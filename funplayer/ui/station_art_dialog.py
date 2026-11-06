"""방송 그림 바꾸기 창."""
from __future__ import annotations

import os
from typing import Callable
from urllib.parse import quote

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QImage, QKeySequence
from PyQt5.QtWidgets import (QApplication, QDialog, QFileDialog, QLabel, QPushButton, QShortcut,
                             QVBoxLayout)

from funplayer.core.themes import DEFAULT_THEME, get_theme
from funplayer.ui.cover import radio_art_for, rounded_art
from funplayer.ui.info_dialog import MAX_PICTURE
from funplayer.ui.station_art import StationArt

PREVIEW = 150
PREVIEW_RADIUS = 18
SEARCH_URL = "https://www.google.com/search?tbm=isch&q="
IMAGE_FILES = "그림 (*.jpg *.jpeg *.png *.webp *.bmp)"


def search_url(name: str) -> str:
    return SEARCH_URL + quote(f"{name} 로고")


class StationArtDialog(QDialog):
    changed = pyqtSignal()

    def __init__(self, art: StationArt, station_id: str, name: str, parent=None,
                 open_url: Callable[[QUrl], object] = QDesktopServices.openUrl) -> None:
        super().__init__(parent)
        self.setWindowTitle("방송 그림 바꾸기")
        self.setAcceptDrops(True)
        self._art = art
        self._id = station_id
        self._name = name
        self._open_url = open_url
        col = QVBoxLayout(self)
        col.setSpacing(8)
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW, PREVIEW)
        col.addWidget(self.preview, 0, Qt.AlignHCenter)
        title = QLabel(name)
        title.setAlignment(Qt.AlignCenter)
        col.addWidget(title)
        self.search_button = self._button(col, "이미지 검색 (브라우저로 열기)", self.search)
        self.paste_button = self._button(col, "복사한 그림 넣기 (Ctrl+V)", self.paste)
        self.file_button = self._button(col, "파일에서 넣기…", self.pick_file)
        self.reset_button = self._button(col, "기본 그림으로 되돌리기", self.reset)
        self.hint = QLabel("그림 파일을 이 창에 끌어다 놓아도 됩니다.")
        col.addWidget(self.hint)
        self.close_button = self._button(col, "닫기", self.accept)
        QShortcut(QKeySequence.Paste, self, activated=self.paste)
        self._refresh()

    @staticmethod
    def _button(col: QVBoxLayout, text: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.setAutoDefault(False)
        b.clicked.connect(lambda _=False: slot())
        col.addWidget(b)
        return b

    def _refresh(self) -> None:
        theme = get_theme(DEFAULT_THEME)
        src = self._art.pixmap(self._id)
        pm = (rounded_art(src, PREVIEW, PREVIEW_RADIUS, theme) if src is not None
              else radio_art_for(theme, PREVIEW, PREVIEW_RADIUS))
        self.preview.setPixmap(pm)
        self.reset_button.setEnabled(self._art.has_user(self._id))

    def _say(self, text: str) -> None:
        self.hint.setText(text)

    def _store(self, img: QImage) -> bool:
        if img.isNull():
            self._say("그림을 읽지 못했습니다")
            return False
        if not self._art.save(self._id, img):
            self._say("그림을 저장하지 못했습니다")
            return False
        self._say("그림을 넣었습니다")
        self._refresh()
        self.changed.emit()
        return True

    def _store_file(self, path: str) -> bool:
        try:
            if os.path.getsize(path) > MAX_PICTURE:
                self._say("그림이 너무 큽니다 (10 MB까지)")
                return False
        except OSError:
            self._say("그림을 읽지 못했습니다")
            return False
        return self._store(QImage(path))

    def search(self) -> None:
        self._open_url(QUrl(search_url(self._name)))
        self._say("그림을 복사한 뒤 여기서 Ctrl+V를 누르세요")

    def paste(self) -> bool:
        mime = QApplication.clipboard().mimeData()
        if mime is not None and mime.hasImage():
            return self._store(QImage(mime.imageData()))
        if mime is not None:
            for url in mime.urls():
                if url.isLocalFile():
                    return self._store_file(url.toLocalFile())
        self._say("복사한 그림이 없습니다 (브라우저에서 그림 우클릭 → 이미지 복사)")
        return False

    def pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "그림 넣기", "", IMAGE_FILES)
        if path:
            self._store_file(path)

    def reset(self) -> None:
        self._art.clear(self._id)
        self._say("기본 그림으로 되돌렸습니다")
        self._refresh()
        self.changed.emit()

    def dragEnterEvent(self, event) -> None:
        mime = event.mimeData()
        if mime.hasImage() or any(u.isLocalFile() for u in mime.urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        for url in mime.urls():
            if url.isLocalFile():
                self._store_file(url.toLocalFile())
                event.acceptProposedAction()
                return
        if mime.hasImage():
            self._store(QImage(mime.imageData()))
            event.acceptProposedAction()
