from __future__ import annotations

import logging
import math
import os
import subprocess

from PyQt5.QtCore import QPointF, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QTextLayout, QTextOption
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from funplayer.core.taginfo import TrackInfo, format_line, format_size
from funplayer.core.timefmt import format_time
from funplayer.engine.tagwrite import KEEP, REMOVE, picture_mime
from funplayer.ui.colors import CHANGED_BG, CHANGED_BORDER, ERROR_COLOR, INFO_COLOR, NOTE_COLOR
from funplayer.ui.cover import art_pixmap

log = logging.getLogger(__name__)

DASH = "—"
ART_SIZE = 120
MAX_PICTURE = 10 * 1024 * 1024
FIELD_KEYS = {"제목": "title", "가수": "artist", "앨범": "album", "년도": "year", "장르": "genre", "트랙": "track"}
GENRES = ["발라드", "댄스", "록", "팝", "힙합", "알앤비", "재즈", "클래식", "일렉트로닉", "트로트", "어쿠스틱",
          "블루스", "인디", "OST"]
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
    """곡 정보 창. editable=True면 여섯 칸·그림을 고칠 수 있고, 저장·지우기는 신호로 알린다(쓰기는 패널 몫)."""

    save_requested = pyqtSignal(str, dict, object)   # 경로, 바뀐 칸만, 그림(KEEP/REMOVE/바이트)
    clear_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("곡 정보")
        self.setModal(False)
        self._path = ""
        self._info: TrackInfo | None = None
        self._cover: QPixmap | None = None
        self._editable = False
        self._orig: dict[str, str] = {}
        self._picture: object = KEEP
        self._transient: tuple[str, str] | None = None   # (글, 색): 저장했습니다 / 오류
        self._note = ""
        self._discarding = False

        self.art_label = QLabel()
        self.art_label.setFixedSize(ART_SIZE, ART_SIZE)
        self.pick_button = QPushButton("그림 넣기…")
        self.remove_pic_button = QPushButton("빼기")
        pic_row = QHBoxLayout()
        pic_row.setSpacing(4)
        pic_row.addWidget(self.pick_button)
        pic_row.addWidget(self.remove_pic_button)
        art_box = QVBoxLayout()
        art_box.setSpacing(4)
        art_box.addWidget(self.art_label)
        art_box.addLayout(pic_row)
        art_box.addStretch(1)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setColumnStretch(1, 1)
        self.value_labels: dict[str, QLabel] = {}
        self.edits: dict[str, QLineEdit | QComboBox] = {}
        for row, key in enumerate(FIELDS):
            name = QLabel(key)
            name.setStyleSheet(f"color: {INFO_COLOR};")
            value = _selectable(QLabel(DASH))
            value.setWordWrap(True)
            grid.addWidget(name, row, 0, Qt.AlignTop)
            grid.addWidget(value, row, 1)   # 고칠 수 없을 때 보이는 글자
            self.value_labels[key] = value
            field = FIELD_KEYS.get(key)
            if field:   # 고칠 수 있을 때 같은 자리에 보이는 입력 칸
                if field == "genre":
                    edit: QLineEdit | QComboBox = QComboBox()
                    edit.setEditable(True)
                    edit.addItems(GENRES)
                    edit.setInsertPolicy(QComboBox.NoInsert)
                    edit.setEditText("")
                else:
                    edit = QLineEdit()
                if field in ("year", "track"):
                    edit.setMaximumWidth(70)
                    grid.addWidget(edit, row, 1, Qt.AlignLeft)
                else:
                    grid.addWidget(edit, row, 1)
                edit.hide()
                self.edits[field] = edit
        grid.setRowStretch(len(FIELDS), 1)   # 줄들을 위로 모으고 남는 높이는 맨 아래 빈 줄이 갖는다
        fm = self.value_labels["형식"].fontMetrics()
        grid.setColumnMinimumWidth(1, fm.horizontalAdvance(WIDEST_FORMAT) + fm.averageCharWidth())

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addLayout(art_box)
        top.addLayout(grid, 1)

        path_name = QLabel("경로")
        path_name.setStyleSheet(f"color: {INFO_COLOR};")
        self.path_label = PathBox()
        path_row = QHBoxLayout()
        path_row.setSpacing(10)
        path_row.addWidget(path_name, 0, Qt.AlignTop)
        path_row.addWidget(self.path_label, 1)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.hide()

        self.confirm_bar = QWidget()
        bar = QHBoxLayout(self.confirm_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar_text = QLabel("태그와 그림을 모두 지웁니다. 소리는 그대로입니다.")
        bar_text.setWordWrap(True)
        self.confirm_button = QPushButton("지우기")
        self.cancel_button = QPushButton("그만두기")
        bar.addWidget(bar_text, 1)
        bar.addWidget(self.confirm_button)
        bar.addWidget(self.cancel_button)
        self.confirm_bar.hide()

        self.clear_button = QPushButton("태그 모두 지우기…")
        self.folder_button = QPushButton("폴더 열기")
        self.save_button = QPushButton("저장")
        self.save_button.setDefault(True)
        self.close_button = QPushButton("닫기")
        buttons = QHBoxLayout()
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        buttons.addWidget(self.folder_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.close_button)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)
        root.addLayout(top)
        root.addLayout(path_row)
        root.addWidget(self.message_label)
        root.addWidget(self.confirm_bar)
        root.addLayout(buttons)

        for edit in self.edits.values():
            if isinstance(edit, QComboBox):
                edit.editTextChanged.connect(self._on_edited)
            else:
                edit.textChanged.connect(self._on_edited)
        self.pick_button.clicked.connect(lambda _=False: self._pick_picture())
        self.remove_pic_button.clicked.connect(lambda _=False: self._remove_picture())
        self.clear_button.clicked.connect(lambda _=False: self.confirm_bar.show())
        self.cancel_button.clicked.connect(lambda _=False: self.confirm_bar.hide())
        self.confirm_button.clicked.connect(lambda _=False: self._confirm_clear())
        self.save_button.clicked.connect(lambda _=False: self._save())
        self.folder_button.clicked.connect(lambda _=False: reveal_in_explorer(self._path))
        self.close_button.clicked.connect(self.close)

    # ---- 채우기 ----
    def show_info(self, info: TrackInfo, cover: QPixmap | None, editable: bool = False,
                  note: str = "") -> bool:
        """채운다. 저장 안 한 칸이 있는 채 다른 곡으로 바꾸려는데 사용자가 아니라고 하면 False."""
        if self.is_dirty() and info.path != self._path and not self.confirm_discard():
            return False
        self._info, self._cover = info, cover
        self._path = info.path
        self._editable = editable
        self._note = note
        self._transient = None
        self._populate()
        return True

    def saved(self, info: TrackInfo, cover: QPixmap | None) -> None:
        self._info, self._cover = info, cover
        self._path = info.path
        self._populate()
        self._transient = ("저장했습니다", INFO_COLOR)
        self._refresh_state()

    def failed(self, message: str) -> None:
        self._transient = (message, ERROR_COLOR)
        self._refresh_state()

    def _populate(self) -> None:
        info = self._info
        assert info is not None
        self._picture = KEEP
        self._transient = None
        self.confirm_bar.hide()
        self._orig = {
            "title": info.title, "artist": info.artist, "album": info.album,
            "year": info.year, "genre": info.genre, "track": info.track,
        }
        values = {
            "제목": info.title, "가수": info.artist, "앨범": info.album,
            "년도": info.year, "장르": info.genre, "트랙": info.track,
            "길이": format_time(info.duration) if info.duration > 0 else "",
            "형식": format_line(info), "크기": format_size(info.size),
        }
        for key, label in self.value_labels.items():
            label.setText(values[key] or DASH)
        for key, edit in self.edits.items():
            value = self._orig[key]
            if isinstance(edit, QComboBox):
                edit.blockSignals(True)
                edit.setEditText(value)
                edit.blockSignals(False)
                edit.lineEdit().setReadOnly(not self._editable)
                edit.setEnabled(self._editable)
            else:
                edit.blockSignals(True)
                edit.setText(value)
                edit.blockSignals(False)
                edit.setReadOnly(not self._editable)
        for key, label in self.value_labels.items():   # 고칠 수 없을 때는 지금처럼 글자로 보인다
            field = FIELD_KEYS.get(key)
            if field:
                label.setVisible(not self._editable)
                self.edits[field].setVisible(self._editable)
        self.setAcceptDrops(self._editable)
        self.path_label.setText(info.path)
        self.folder_button.setEnabled(
            os.path.isfile(info.path) or os.path.isdir(os.path.dirname(info.path)))
        self._refresh_state()
        self.adjustSize()   # 줄바꿈된 값까지 다 보이는 높이로
        need = self.layout().totalHeightForWidth(self.width())
        if self.height() < need:   # adjustSize는 화면 높이의 2/3에서 자르므로 모자라면 더 키운다
            self.resize(self.width(), need)

    # ---- 바뀐 값 ----
    def _current(self, key: str) -> str:
        edit = self.edits[key]
        text = edit.currentText() if isinstance(edit, QComboBox) else edit.text()
        return text.strip()

    def _changed_fields(self) -> dict[str, str]:
        return {k: self._current(k) for k in self.edits if self._current(k) != self._orig.get(k, "").strip()}

    def is_dirty(self) -> bool:
        return self._editable and (bool(self._changed_fields()) or self._picture is not KEEP)

    def _on_edited(self, *_args) -> None:
        self._transient = None
        self._refresh_state()

    def _refresh_state(self) -> None:
        editable = self._editable
        changed = self._changed_fields() if editable else {}
        for key, edit in self.edits.items():
            style = f"background: {CHANGED_BG};" if key in changed else ""
            (edit.lineEdit() if isinstance(edit, QComboBox) else edit).setStyleSheet(style)
        pic_changed = editable and self._picture is not KEEP
        self.art_label.setStyleSheet(f"border: 2px solid {CHANGED_BORDER};" if pic_changed else "")
        if isinstance(self._picture, bytes):
            pm = QPixmap()
            pm.loadFromData(self._picture)
            self.art_label.setPixmap(art_pixmap(pm if not pm.isNull() else None, ART_SIZE))
        elif self._picture is REMOVE:
            self.art_label.setPixmap(art_pixmap(None, ART_SIZE))
        else:
            self.art_label.setPixmap(art_pixmap(self._cover, ART_SIZE))
        has_embedded = bool(self._info and self._info.picture)
        for w in (self.pick_button, self.remove_pic_button, self.clear_button, self.save_button):
            w.setVisible(editable)
        self.remove_pic_button.setEnabled(
            isinstance(self._picture, bytes) or (has_embedded and self._picture is not REMOVE))
        self.save_button.setEnabled(editable and self.is_dirty())
        if not editable:
            self.confirm_bar.hide()
        if self._transient:
            text, color = self._transient
        elif editable and self.is_dirty():
            text, color = "노란 칸 = 바뀐 값 (아직 저장 안 됨)", NOTE_COLOR
        elif editable:
            text, color = "", INFO_COLOR
        else:
            text, color = self._note, INFO_COLOR
        self.message_label.setText(text)
        self.message_label.setStyleSheet(f"color: {color};")
        self.message_label.setVisible(bool(text))

    # ---- 그림 ----
    def set_picture_bytes(self, data: bytes) -> bool:
        if not self._editable:
            return False
        if picture_mime(data) is None:
            return self._picture_error("jpg·png 그림만 넣을 수 있습니다")
        if len(data) > MAX_PICTURE:
            return self._picture_error("그림이 너무 큽니다 (10 MB까지)")
        self._picture = data
        self._transient = None
        self._refresh_state()
        return True

    def _picture_error(self, text: str) -> bool:
        self._transient = (text, ERROR_COLOR)
        self._refresh_state()
        return False

    def _load_picture_file(self, path: str) -> None:
        try:
            if os.path.getsize(path) > MAX_PICTURE:
                self._picture_error("그림이 너무 큽니다 (10 MB까지)")
                return
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            self._picture_error("그림 파일을 읽지 못했습니다")
            return
        self.set_picture_bytes(data)

    def _pick_picture(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "그림 넣기", "", "그림 (*.jpg *.jpeg *.png)")
        if path:
            self._load_picture_file(path)

    def _remove_picture(self) -> None:
        has_embedded = bool(self._info and self._info.picture)
        self._picture = REMOVE if has_embedded else KEEP
        self._transient = None
        self._refresh_state()

    @staticmethod
    def _dropped_file(event) -> str | None:
        urls = event.mimeData().urls()
        if len(urls) != 1 or not urls[0].isLocalFile():
            return None
        path = urls[0].toLocalFile()
        return path if path.lower().endswith((".jpg", ".jpeg", ".png")) else None

    def dragEnterEvent(self, event) -> None:
        if self._editable and event.mimeData().hasUrls() and self._dropped_file(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        path = self._dropped_file(event) if self._editable else None
        if path:
            event.acceptProposedAction()
            self._load_picture_file(path)
        else:
            super().dropEvent(event)

    # ---- 저장·지우기 ----
    def _save(self) -> None:
        if self.is_dirty():
            self.save_requested.emit(self._path, self._changed_fields(), self._picture)

    def _confirm_clear(self) -> None:
        self.confirm_bar.hide()
        self.clear_requested.emit(self._path)

    # ---- 닫기 ----
    def confirm_discard(self) -> bool:
        answer = QMessageBox.question(self, "곡 정보", "저장 안 한 내용이 있습니다. 버릴까요?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def _close_with_discard(self, close_super) -> bool:
        """저장 안 한 칸이 있으면 묻고, 닫기로 했으면 값을 처음대로 되돌린다. 닫지 않으면 False."""
        if self._discarding:
            return True
        dirty = self.is_dirty()
        if dirty and not self.confirm_discard():
            return False
        self._discarding = True   # 안쪽 reject/closeEvent가 다시 묻지 않게
        try:
            close_super()
        finally:
            self._discarding = False
        if dirty and self._info is not None:
            self._populate()   # 버린 값은 사라지고 처음 값으로 돌아간다
        return True

    def closeEvent(self, event) -> None:
        if self._discarding:
            super().closeEvent(event)
        elif not self._close_with_discard(lambda: super(TrackInfoDialog, self).closeEvent(event)):
            event.ignore()

    def reject(self) -> None:   # Esc도 같은 길로
        if self._discarding:
            super().reject()
        else:
            self._close_with_discard(lambda: super(TrackInfoDialog, self).reject())
