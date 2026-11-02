"""여러 곡 태그 창 (5-D): '이름 정리'로 가수 - 제목 통일, '공통 칸'으로 앨범·장르·년도·그림을 한 번에."""
from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QShortcut, QSizePolicy, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from funplayer.core import bulktag, renamer
from funplayer.core.taginfo import TrackInfo
from funplayer.engine.tagwrite import KEEP, picture_mime
from funplayer.ui.colors import CHANGED_BG, ERROR_COLOR, INFO_COLOR, RENAME_OK_COLOR
from funplayer.ui.info_dialog import GENRES, MAX_PICTURE, TrackInfoDialog

TAB_NAMES, TAB_COMMON = range(2)
COL_FILE, COL_ARTIST, COL_TITLE, COL_ALBUM, COL_COVER, COL_NEW, COL_NOTE = range(7)
HEADERS = ["지금 파일 이름", "가수", "제목", "앨범", "그림", "새 파일 이름", "알림"]
COMMON = [("가수", "artist"), ("앨범", "album"), ("년도", "year"), ("장르", "genre")]
MANY = "(여러 값 · 그대로 둠)"
UNSURE_BG = "#FFE2C2"
UNSURE_FG = "#8A4B00"


class _Row:
    def __init__(self, info: TrackInfo, has_cover: bool | None) -> None:
        self.path = info.path
        self.orig = {k: getattr(info, k) or "" for k in bulktag.FIELDS}
        self.has_cover = has_cover
        self.guess = bulktag.Tidy("", "", bulktag.SURE)
        self.swapped = False
        self.confirmed = False   # 사용자가 앞뒤 바꾸기·맞음·직접 고침으로 확인함
        self.edits: dict[str, str] = {}

    def names(self) -> tuple[str, str]:
        artist, title = self.guess.artist, self.guess.title
        if self.swapped:
            artist, title = title, artist
        return self.edits.get("artist", artist), self.edits.get("title", title)

    @property
    def unsure(self) -> bool:
        return self.guess.unsure and not self.confirmed


class BulkTagDialog(QDialog):
    def __init__(self, infos: list[TrackInfo], parent=None, save_many=None, rename_many=None,
                 undo_many=None, read_info=None, has_cover=None, after_change=None,
                 start_tab: int = TAB_NAMES) -> None:
        super().__init__(parent)
        self.setWindowTitle("여러 곡 태그")
        mp3 = [i for i in infos if i.path.lower().endswith(".mp3")]
        self.skipped = len(infos) - len(mp3)
        self._has_cover = has_cover
        self.rows = [_Row(i, has_cover(i.path) if has_cover else None) for i in mp3]
        self._save_many = save_many
        self._rename_many = rename_many
        self._undo_many = undo_many
        self._read_info = read_info
        self._after_change = after_change or (lambda: None)
        self.picture: bytes | None = None
        self.last_renames: list[tuple[str, str]] = []
        self._message = ("", INFO_COLOR)
        self._filling = True   # 만드는 동안 칸들이 보내는 신호로 refresh가 돌지 않게
        self._guess_all()
        self._build()
        self._filling = False
        self.tabs.setCurrentIndex(start_tab)
        self.refresh()

    # ---- 만들기 ----
    def _build(self) -> None:
        v = QVBoxLayout(self)
        v.setSpacing(8)
        self.head = QLabel()
        v.addWidget(self.head)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._names_tab(), "이름 정리 (가수 - 제목)")
        self.tabs.addTab(self._common_tab(), "공통 칸 (앨범·장르·그림)")
        self.tabs.currentChanged.connect(self.refresh)
        self.tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)   # 남는 높이는 표로
        v.addWidget(self.tabs)
        t = self.table = QTableWidget(len(self.rows), len(HEADERS))
        t.setHorizontalHeaderLabels(HEADERS)
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.ExtendedSelection)
        t.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        for col, width in ((COL_FILE, 210), (COL_ARTIST, 110), (COL_TITLE, 150), (COL_ALBUM, 110),
                           (COL_COVER, 44), (COL_NEW, 230)):
            t.setColumnWidth(col, width)
        t.horizontalHeader().setSectionResizeMode(COL_NOTE, QHeaderView.Stretch)
        t.itemChanged.connect(self._cell_edited)
        t.setMinimumHeight(200)
        v.addWidget(t, 1)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        v.addWidget(self.message_label)
        b = QHBoxLayout()
        self.swap_button = QPushButton("↔ 앞뒤 바꾸기")
        self.swap_button.clicked.connect(self.swap_selected)
        self.ok_button = QPushButton("이대로 맞음")
        self.ok_button.clicked.connect(self.confirm_selected)
        self.undo_button = QPushButton("이름 한 번에 되돌리기")
        self.undo_button.clicked.connect(self.undo_renames)
        b.addWidget(self.swap_button)
        b.addWidget(self.ok_button)
        b.addWidget(self.undo_button)
        b.addStretch(1)
        self.go_button = QPushButton()
        self.go_button.setDefault(True)
        self.go_button.clicked.connect(self.go)
        close = QPushButton("닫기")
        close.clicked.connect(self.close)
        b.addWidget(self.go_button)
        b.addWidget(close)
        v.addLayout(b)
        paste = QShortcut(QKeySequence.Paste, self)
        paste.setContext(Qt.WidgetWithChildrenShortcut)
        paste.activated.connect(self._paste)
        self.resize(980, 600)

    def _names_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        info = QLabel("파일 이름에서 가수와 제목을 찾아 <b>태그에 넣고, 파일 이름을 '가수 - 제목'으로</b> 한 번에 바꿉니다. "
                      "앞 번호(02.)와 괄호 군말은 뺍니다. 트랙 번호는 건드리지 않습니다.")
        info.setWordWrap(True)
        lay.addWidget(info)
        hint = QLabel("주황 줄은 가수·제목 순서를 모르는 곡입니다. 줄을 고르고(여러 줄 가능) [↔ 앞뒤 바꾸기] 또는 "
                      "[이대로 맞음]을 누르세요. 칸을 두 번 눌러 직접 고쳐도 됩니다. 주황 줄은 확인해야 바뀝니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {UNSURE_FG};")
        lay.addWidget(hint)
        return w

    def _common_tab(self) -> QWidget:
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(10, 8, 10, 8)
        self.common_boxes: dict[str, QCheckBox] = {}
        self.common_edits: dict[str, QLineEdit] = {}
        for r, (label, key) in enumerate(COMMON):
            box = QCheckBox(label)
            if key == "genre":
                combo = QComboBox()
                combo.setEditable(True)
                combo.addItems(GENRES)
                combo.setEditText(self._shared(key))
                edit = combo.lineEdit()
                g.addWidget(combo, r, 1)
            else:
                edit = QLineEdit(self._shared(key))
                g.addWidget(edit, r, 1)
            edit.setPlaceholderText(MANY)
            edit.textEdited.connect(lambda _t, b=box: b.setChecked(True))
            edit.textChanged.connect(self.refresh)
            box.toggled.connect(self.refresh)
            g.addWidget(box, r, 0)
            self.common_boxes[key], self.common_edits[key] = box, edit
        self.picture_box = QCheckBox("그림")
        self.picture_box.toggled.connect(self.refresh)
        pick = QPushButton("그림 넣기…")
        pick.clicked.connect(self._pick_picture)
        self.picture_label = QLabel("그림을 복사한 뒤 Ctrl+V도 됩니다")
        self.picture_label.setStyleSheet(f"color: {INFO_COLOR};")
        g.addWidget(self.picture_box, 0, 2)
        g.addWidget(pick, 1, 2)
        g.addWidget(self.picture_label, 2, 2, 2, 1, Qt.AlignTop)
        g.setColumnStretch(1, 1)
        return w

    def _shared(self, key: str) -> str:
        values = {r.orig[key] for r in self.rows}
        return values.pop() if len(values) == 1 else ""

    def _guess_all(self) -> None:
        stems = [os.path.splitext(os.path.basename(r.path))[0] for r in self.rows]
        guesses = bulktag.tidy_names(stems, [r.orig["artist"] for r in self.rows], [r.orig["title"] for r in self.rows])
        for row, guess in zip(self.rows, guesses):
            row.guess, row.swapped, row.confirmed, row.edits = guess, False, False, {}

    # ---- 값 계산 ----
    def _target(self, row: _Row) -> str | None:
        artist, title = row.names()
        return renamer.target_path(row.path, artist, title) if artist and title else None

    def name_plan(self) -> list[tuple[_Row, dict[str, str], str | None, str]]:
        """이름 정리 탭: 곡마다 (줄, 바뀔 태그, 새 경로 또는 None, 알림). 주황 줄·겹치는 이름은 빼 둔다."""
        plan = []
        for row in self.rows:
            artist, title = row.names()
            fields = {k: v for k, v in (("artist", artist), ("title", title)) if v != row.orig[k]}
            target = self._target(row)
            if row.unsure:
                plan.append((row, {}, None, row.guess.note))
                continue
            if not artist or not title:
                plan.append((row, {}, None, bulktag.NOTES[bulktag.NO_ARTIST]))
                continue
            note = row.guess.note if not row.confirmed else ""
            if target == row.path:
                target = None
            elif target is not None and renamer.conflict(row.path, target):
                plan.append((row, fields, None, "같은 이름의 파일이 있어 이름은 그대로 둡니다"))
                continue
            plan.append((row, fields, target, note))
        return plan

    def _common_values(self) -> dict[str, str]:
        return {k: self.common_edits[k].text().strip() for k, box in self.common_boxes.items() if box.isChecked()}

    def _picture_on(self) -> bool:
        return self.picture_box.isChecked() and self.picture is not None

    # ---- 화면 ----
    def refresh(self) -> None:
        if self._filling:
            return
        self._filling = True
        try:
            on_names = self.tabs.currentIndex() == TAB_NAMES
            plan = self.name_plan()
            common = self._common_values()
            picture = self._picture_on()
            for i, (row, fields, target, note) in enumerate(plan):
                orange = on_names and row.unsure
                if on_names:
                    artist, title = row.names()
                    album = row.orig["album"]
                    changed = set(fields)
                    new = (os.path.basename(target) if target else
                           "(지금 이름과 같음)" if self._target(row) == row.path else "—")
                else:
                    artist = common.get("artist", row.orig["artist"])
                    title, album = row.orig["title"], common.get("album", row.orig["album"])
                    changed = {k for k, v in common.items() if v != row.orig[k]}
                    new, note = "", ""
                self._cell(i, COL_FILE, os.path.basename(row.path), QColor(INFO_COLOR), orange=orange)
                self._cell(i, COL_ARTIST, artist, changed="artist" in changed, editable=on_names, orange=orange)
                self._cell(i, COL_TITLE, title, changed="title" in changed, editable=on_names, orange=orange)
                self._cell(i, COL_ALBUM, album, changed="album" in changed, orange=orange)
                if picture and not on_names:
                    self._cell(i, COL_COVER, "넣음", changed=True)
                elif row.has_cover is None:
                    self._cell(i, COL_COVER, "", orange=orange)
                else:
                    self._cell(i, COL_COVER, "있음" if row.has_cover else "없음",
                               None if row.has_cover else QColor(ERROR_COLOR), orange=orange)
                self._cell(i, COL_NEW, new, QColor(INFO_COLOR) if new.startswith("(") else None, orange=orange)
                self._cell(i, COL_NOTE, note, QColor(UNSURE_FG) if row.unsure else QColor(INFO_COLOR),
                           orange=orange)
            self.table.setColumnHidden(COL_NEW, not on_names)
            self.table.setColumnHidden(COL_NOTE, not on_names)
            if on_names:
                n = sum(1 for _, fields, target, _ in plan if fields or target)
                self.go_button.setText(f"태그 저장 + 이름 바꾸기 ({n}곡)")
            else:
                n = len(self.rows) if picture else sum(
                    1 for r in self.rows if any(v != r.orig[k] for k, v in common.items()))
                self.go_button.setText(f"저장 ({n}곡)")
            self.go_button.setEnabled(n > 0)
            self.swap_button.setVisible(on_names)
            self.ok_button.setVisible(on_names)
            self.undo_button.setVisible(bool(self.last_renames))
            unsure = sum(1 for r in self.rows if r.unsure)
            head = f"<b>여러 곡 태그</b> <span style='color:{INFO_COLOR};'>· 고른 곡 {len(self.rows)}곡"
            if on_names and unsure:
                head += f" · <span style='color:{UNSURE_FG};'>확인할 곡 {unsure}곡</span>"
            if self.skipped:
                head += f" · MP3가 아닌 {self.skipped}곡은 뺐습니다"
            self.head.setText(head + "</span>")
            text, color = self._message
            self.message_label.setText(text)
            self.message_label.setStyleSheet(f"color: {color};")
        finally:
            self._filling = False

    def _cell(self, r: int, c: int, text: str, color: QColor | None = None, changed: bool = False,
              editable: bool = False, orange: bool = False) -> None:
        item = self.table.item(r, c)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(r, c, item)
        item.setText(text)
        item.setToolTip(text if len(text) > 12 else "")
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        item.setFlags(flags | Qt.ItemIsEditable if editable else flags)
        bg = UNSURE_BG if orange else CHANGED_BG if changed else None
        item.setBackground(QColor(bg) if bg else QColor(0, 0, 0, 0))
        item.setForeground(color if color is not None else self.palette().text().color())

    def selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self.table.selectedIndexes()})

    def swap_selected(self) -> None:
        for i in self.selected_rows():
            row = self.rows[i]
            row.swapped = not row.swapped
            row.edits.clear()
            row.confirmed = True
        self.refresh()

    def confirm_selected(self) -> None:
        for i in self.selected_rows():
            self.rows[i].confirmed = True
        self.refresh()

    def _cell_edited(self, item: QTableWidgetItem) -> None:
        if self._filling:
            return
        key = {COL_ARTIST: "artist", COL_TITLE: "title"}.get(item.column())
        if key is None:
            return
        row = self.rows[item.row()]
        row.edits[key] = item.text().strip()
        row.confirmed = True
        self.refresh()

    # ---- 그림 ----
    def set_picture(self, data: bytes) -> bool:
        if picture_mime(data) is None:
            return self._say("jpg·png 그림만 넣을 수 있습니다", ERROR_COLOR)
        if len(data) > MAX_PICTURE:
            return self._say("그림이 너무 큽니다 (10 MB까지)", ERROR_COLOR)
        self.picture = data
        self.picture_label.setText(f"고른 그림 ({max(1, len(data) // 1024)} KB)")
        self.picture_box.setChecked(True)
        self._message = ("", INFO_COLOR)
        self.refresh()
        return True

    def _pick_picture(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "그림 넣기", "", "그림 (*.jpg *.jpeg *.png)")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_PICTURE + 1)
        except OSError:
            self._say("그림 파일을 읽지 못했습니다", ERROR_COLOR)
            return
        self.set_picture(data)

    def _paste(self) -> None:
        focus = QApplication.focusWidget()
        mime = QApplication.clipboard().mimeData()
        if isinstance(focus, (QLineEdit, QPlainTextEdit)) and mime is not None and mime.hasText():
            focus.paste()   # 글자 칸에서는 글자가 먼저
            return
        data = TrackInfoDialog._mime_image_bytes(mime) if mime is not None else None
        if data is not None:
            self.tabs.setCurrentIndex(TAB_COMMON)
            self.set_picture(data)

    def _say(self, text: str, color: str) -> bool:
        self._message = (text, color)
        self.refresh()
        return False

    # ---- 실행 ----
    def go(self) -> None:
        if self.tabs.currentIndex() == TAB_NAMES:
            self.apply_names()
        else:
            self.save_common()

    def _busy(self, fn, *args):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            return fn(*args)
        finally:
            QApplication.restoreOverrideCursor()

    def apply_names(self) -> None:
        if self._save_many is None:
            return
        plan = [(row, fields, target) for row, fields, target, _ in self.name_plan() if fields or target]
        if not plan:
            return
        saved = self._busy(self._save_many, [(row.path, fields) for row, fields, _ in plan if fields])
        failed = {p for p, _ in saved.failed}
        pairs = [(row.path, target) for row, _, target in plan if target and row.path not in failed]
        renamed = self._busy(self._rename_many, pairs) if pairs and self._rename_many else None
        done_renames = list(renamed.done) if renamed else []
        self._move_paths(done_renames)
        self.last_renames = done_renames
        self._reread()
        problems = list(saved.failed) + (list(renamed.failed) if renamed else [])
        tagged = len(saved.done)
        text = f"태그 {tagged}곡 저장, 파일 이름 {len(done_renames)}곡 바꿈"
        self._message = self._with_problems(text, problems)
        self._after_change()
        self.refresh()

    def save_common(self) -> None:
        if self._save_many is None:
            return
        common = self._common_values()
        picture = self.picture if self._picture_on() else KEEP
        items = []
        for row in self.rows:
            fields = {k: v for k, v in common.items() if v != row.orig[k]}
            if fields or picture is not KEEP:
                items.append((row.path, fields))
        if not items:
            return
        result = self._busy(self._save_many, items, picture)
        for box in (self.picture_box, *self.common_boxes.values()):
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)
        self._reread()
        self._message = self._with_problems(f"{len(result.done)}곡 저장했습니다", list(result.failed))
        self._after_change()
        self.refresh()

    def undo_renames(self) -> None:
        if not self.last_renames or self._undo_many is None:
            return
        result = self._busy(self._undo_many, self.last_renames)
        self._move_paths(result.done)
        self.last_renames = []
        self._reread()
        self._message = self._with_problems(f"파일 이름 {len(result.done)}곡을 되돌렸습니다", list(result.failed))
        self._after_change()
        self.refresh()

    def _reread(self) -> None:
        """파일에서 다시 읽어 원래 값으로 삼고, 이름 정리를 새로 짐작한다."""
        for row in self.rows:
            if self._read_info is not None:
                row.orig = {k: getattr(self._read_info(row.path), k) or "" for k in bulktag.FIELDS}
            if self._has_cover is not None:
                row.has_cover = self._has_cover(row.path)
        self._guess_all()

    def _move_paths(self, done: list[tuple[str, str]]) -> None:
        moved = {os.path.normcase(a): b for a, b in done}
        for row in self.rows:
            row.path = moved.get(os.path.normcase(row.path), row.path)

    @staticmethod
    def _with_problems(text: str, problems: list[tuple[str, str]]) -> tuple[str, str]:
        if not problems:
            return text, RENAME_OK_COLOR
        names = ", ".join(os.path.basename(p) for p, _ in problems[:3])
        more = " 등" if len(problems) > 3 else ""
        return f"{text}. {len(problems)}곡은 못 했습니다: {names}{more} ({problems[0][1]})", ERROR_COLOR
