"""여러 곡 태그 창 (5-D): '이름 정리'로 가수 - 제목 통일, '공통 칸'으로 앨범·장르·년도·그림을 한 번에,
'그림 찾기'로 그림 없는 곡마다 따로 찾은 그림을 한 번에."""
from __future__ import annotations

import os

from PyQt5.QtCore import QSize, Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QShortcut, QSizePolicy, QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from funplayer import websearch
from funplayer.core import bulktag, renamer
from funplayer.core.taginfo import TrackInfo
from funplayer.engine.tagwrite import KEEP, picture_mime
from funplayer.ui.colors import CHANGED_BG, ERROR_COLOR, INFO_COLOR, RENAME_OK_COLOR
from funplayer.ui.info_dialog import GENRES, MAX_PICTURE, TrackInfoDialog

TAB_NAMES, TAB_COMMON, TAB_COVERS = range(3)
COL_FILE, COL_ARTIST, COL_TITLE, COL_ALBUM, COL_COVER, COL_NEW, COL_NOTE = range(7)
HEADERS = ["지금 파일 이름", "가수", "제목", "앨범", "그림", "새 파일 이름", "알림"]
COMMON = [("가수", "artist"), ("앨범", "album"), ("년도", "year"), ("장르", "genre")]
MANY = "(여러 값 · 그대로 둠)"
UNSURE_BG = "#FFE2C2"
UNSURE_FG = "#8A4B00"
COPY_ONLY = (COL_FILE, COL_NEW, COL_NOTE)   # 고칠 수는 없고 긁어 복사만
CV_CHECK, CV_PIC, CV_SONG, CV_SOURCE, CV_NOTE = range(5)
COVER_HEADERS = ["넣기", "그림", "곡 (가수 - 제목)", "찾은 곳", "찾은 앨범 / 알림"]
THUMB = 48
# 그림 찾기 탭의 곡 상태
CV_HAVE, CV_WAIT, CV_BUSY, CV_SURE, CV_MAYBE, CV_NONE, CV_ERROR, CV_DONE = (
    "have", "wait", "busy", "sure", "maybe", "none", "error", "done")
CV_NOTES = {
    CV_HAVE: "그림 있음 · 찾지 않음",
    CV_WAIT: "찾을 차례",
    CV_BUSY: "찾는 중…",
    CV_NONE: "못 찾음 · 우클릭 → 지니·멜론에서 찾기 → 복사한 그림을 이 곡에 넣기",
    CV_ERROR: "인터넷에 연결하지 못함 · [다시 찾기]",
    CV_DONE: "넣었습니다",
}


class _CopyOnlyDelegate(QStyledItemDelegate):
    """두 번 누르면 읽기 전용 글자 칸을 띄워 마우스로 긁어 복사할 수 있게 한다. 값은 바뀌지 않는다."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setReadOnly(True)
        return editor

    def setEditorData(self, editor, index) -> None:
        editor.setText(index.data() or "")
        editor.selectAll()

    def setModelData(self, editor, model, index) -> None:
        pass


class _Row:
    def __init__(self, info: TrackInfo, has_cover: bool | None) -> None:
        self.path = info.path
        self.orig = {k: getattr(info, k) or "" for k in bulktag.FIELDS}
        self.has_cover = has_cover
        self.guess = bulktag.Tidy("", "", bulktag.SURE)
        self.swapped = False
        self.confirmed = False   # 사용자가 앞뒤 바꾸기·맞음·직접 고침으로 확인함
        self.edits: dict[str, str] = {}
        self.cover_state = CV_HAVE if has_cover else CV_WAIT
        self.hit = None          # coverfind.Hit
        self.cover_on = False    # 그림 찾기 탭의 넣기 체크
        self.thumb: QPixmap | None = None

    def search_names(self) -> tuple[str, str]:
        """그림 찾기에 쓸 가수·제목: 태그가 있으면 태그, 없으면 파일 이름에서 짐작한 값."""
        artist, title = self.orig["artist"], self.orig["title"]
        if artist and title:
            return artist, title
        guess = self.names()
        return artist or guess[0], title or guess[1]

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
                 start_tab: int = TAB_NAMES, open_url=None, find_cover=None, run_async=None) -> None:
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
        self._open_url = open_url or (lambda url: QDesktopServices.openUrl(QUrl(url)))
        self.picture: bytes | None = None
        self._find_cover = find_cover      # (가수, 제목) -> coverfind.Hit | None, 뒤에서 돈다
        self._run_async = run_async
        self._cover_queue: list[_Row] = []
        self._cover_running = False
        self._cover_started = False
        self._stopped = False
        self.last_renames: list[tuple[str, str]] = []
        self._message = ("", INFO_COLOR)
        self._filling = True   # 만드는 동안 칸들이 보내는 신호로 refresh가 돌지 않게
        self._guess_all()
        self._build()
        self._filling = False
        self.tabs.setCurrentIndex(start_tab)   # 그림 찾기 탭이면 _tab_changed가 찾기를 시작한다
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
        self.tabs.addTab(self._covers_tab(), "그림 찾기 (곡마다)")
        self.tabs.currentChanged.connect(self._tab_changed)
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
        self._copy_delegate = _CopyOnlyDelegate(t)
        for col in COPY_ONLY:
            t.setItemDelegateForColumn(col, self._copy_delegate)
        copy = QShortcut(QKeySequence.Copy, t)
        copy.setContext(Qt.WidgetShortcut)
        copy.activated.connect(self.copy_cell)
        t.setMinimumHeight(200)
        t.setContextMenuPolicy(Qt.CustomContextMenu)
        t.customContextMenuRequested.connect(self._row_menu)
        v.addWidget(t, 1)
        c = self.cover_table = QTableWidget(len(self.rows), len(COVER_HEADERS))
        c.setHorizontalHeaderLabels(COVER_HEADERS)
        c.verticalHeader().setVisible(False)
        c.verticalHeader().setDefaultSectionSize(THUMB + 6)
        c.setSelectionBehavior(QAbstractItemView.SelectRows)
        c.setEditTriggers(QAbstractItemView.NoEditTriggers)
        c.setIconSize(QSize(THUMB, THUMB))
        for col, width in ((CV_CHECK, 44), (CV_PIC, THUMB + 14), (CV_SONG, 260), (CV_SOURCE, 100)):
            c.setColumnWidth(col, width)
        c.horizontalHeader().setSectionResizeMode(CV_NOTE, QHeaderView.Stretch)
        c.itemChanged.connect(self._cover_checked)
        c.setMinimumHeight(200)
        c.setContextMenuPolicy(Qt.CustomContextMenu)
        c.customContextMenuRequested.connect(self._cover_row_menu)
        v.addWidget(c, 1)
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
        self.research_button = QPushButton("다시 찾기")
        self.research_button.clicked.connect(self.research_covers)
        b.addWidget(self.research_button)
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

    def _tab_changed(self, index: int) -> None:
        if index == TAB_COVERS and not self._filling:
            self.start_cover_search()
        self.refresh()

    def _names_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        info = QLabel("파일 이름에서 가수와 제목을 찾아 <b>태그에 넣고, 파일 이름을 '가수 - 제목'으로</b> 한 번에 바꿉니다. "
                      "앞 번호(02.)와 괄호 군말은 뺍니다. 트랙 번호는 건드리지 않습니다.")
        info.setWordWrap(True)
        lay.addWidget(info)
        hint = QLabel("주황 줄은 가수·제목 순서를 모르는 곡입니다. 줄을 고르고(여러 줄 가능) [↔ 앞뒤 바꾸기] 또는 "
                      "[이대로 맞음]을 누르세요. 칸을 두 번 눌러 직접 고쳐도 됩니다. 주황 줄은 확인해야 바뀝니다.<br>"
                      "지금 파일 이름 칸을 두 번 누르면 글자를 긁어 복사할 수 있습니다 (칸을 고르고 Ctrl+C도 됨).")
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

    def _covers_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        info = QLabel("그림 없는 곡마다 <b>가수·제목으로 따로 찾아</b> 곡마다 맞는 그림을 넣습니다. "
                      "가요는 애플 뮤직 → MusicBrainz, 해외 곡은 MusicBrainz → 애플 뮤직 순서로 찾습니다.")
        info.setWordWrap(True)
        lay.addWidget(info)
        hint = QLabel("주황 줄은 비슷하지만 확실하지 않은 그림입니다(체크가 꺼져 있음). 그림을 보고 맞으면 체크하세요. "
                      "못 찾은 곡은 우클릭 → 지니에서 찾기 / 멜론에서 찾기.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {UNSURE_FG};")
        lay.addWidget(hint)
        self.cover_progress = QLabel()
        self.cover_progress.setStyleSheet(f"color: {INFO_COLOR};")
        lay.addWidget(self.cover_progress)
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
            on_covers = self.tabs.currentIndex() == TAB_COVERS
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
            self.table.setVisible(not on_covers)
            self.cover_table.setVisible(on_covers)
            self._refresh_covers()
            if on_covers:
                n = len(self._covers_to_put())
                self.go_button.setText(f"체크한 곡에 그림 넣기 ({n}곡)")
            elif on_names:
                n = sum(1 for _, fields, target, _ in plan if fields or target)
                self.go_button.setText(f"태그 저장 + 이름 바꾸기 ({n}곡)")
            else:
                n = len(self.rows) if picture else sum(
                    1 for r in self.rows if any(v != r.orig[k] for k, v in common.items()))
                self.go_button.setText(f"저장 ({n}곡)")
            self.go_button.setEnabled(n > 0)
            self.swap_button.setVisible(on_names)
            self.ok_button.setVisible(on_names)
            self.undo_button.setVisible(bool(self.last_renames) and not on_covers)
            self.research_button.setVisible(on_covers)
            self.research_button.setEnabled(not self._cover_running and any(
                r.cover_state in (CV_NONE, CV_ERROR) for r in self.rows))
            unsure = sum(1 for r in self.rows if r.unsure)
            head = f"<b>여러 곡 태그</b> <span style='color:{INFO_COLOR};'>· 고른 곡 {len(self.rows)}곡"
            if on_covers:
                missing = sum(1 for r in self.rows if r.cover_state != CV_HAVE)
                head += f" · 그림 없는 곡 {missing}곡"
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

    def _refresh_covers(self) -> None:
        counts = dict.fromkeys((CV_HAVE, CV_WAIT, CV_BUSY, CV_SURE, CV_MAYBE, CV_NONE, CV_ERROR, CV_DONE), 0)
        for i, row in enumerate(self.rows):
            counts[row.cover_state] += 1
            self._cover_row(i, row)
        todo = counts[CV_WAIT] + counts[CV_BUSY]
        if todo:
            parts = [f"찾는 중 · {todo}곡 남음 (찾는 동안 창을 써도 됩니다)"]
        elif self._find_cover is None:
            parts = ["그림 찾기를 쓸 수 없습니다"]
        else:
            parts = ["다 찾았습니다"]
        for state, label in ((CV_SURE, "찾음"), (CV_MAYBE, "확인할 곡"), (CV_NONE, "못 찾음"),
                             (CV_ERROR, "인터넷 안 됨"), (CV_DONE, "넣음")):
            if counts[state]:
                parts.append(f"{label} {counts[state]}곡")
        self.cover_progress.setText(" · ".join(parts))

    def _cover_row(self, i: int, row: _Row) -> None:
        t = self.cover_table
        items = []
        for c in range(len(COVER_HEADERS)):
            item = t.item(i, c)
            if item is None:
                item = QTableWidgetItem()
                t.setItem(i, c, item)
            items.append(item)
        check, pic, song, source, note = items
        state, hit = row.cover_state, row.hit
        found_state = state in (CV_SURE, CV_MAYBE)
        orange = state == CV_MAYBE and not row.cover_on
        if found_state:
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            check.setCheckState(Qt.Checked if row.cover_on else Qt.Unchecked)
        else:
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            check.setData(Qt.CheckStateRole, None)
        if row.thumb is not None and state in (CV_SURE, CV_MAYBE, CV_DONE):
            pic.setData(Qt.DecorationRole, row.thumb)
            pic.setText("")
        else:
            pic.setData(Qt.DecorationRole, None)
            pic.setText("있음" if state == CV_HAVE else "" if state in (CV_WAIT, CV_BUSY) else "없음")
        pic.setTextAlignment(Qt.AlignCenter)
        artist, title = row.search_names()
        song.setText(f"{artist} - {title}" if artist and title else title or os.path.basename(row.path))
        song.setToolTip(os.path.basename(row.path))
        source.setText(hit.source if hit is not None and state in (CV_SURE, CV_MAYBE, CV_DONE) else "")
        if found_state:
            found = " · ".join(p for p in (hit.album, hit.year) if p)
            text = found if state == CV_SURE else " · ".join(
                p for p in (f"찾은 곡 '{hit.artist} - {hit.title}'", found, "확인") if p)
        else:
            text = CV_NOTES[state]
        note.setText(text)
        note.setToolTip(text if len(text) > 30 else "")
        normal = self.palette().text().color()
        for item in items:
            item.setBackground(QColor(UNSURE_BG) if orange else QColor(0, 0, 0, 0))
        pic.setForeground(QColor(ERROR_COLOR) if pic.text() == "없음" else QColor(INFO_COLOR))
        song.setForeground(QColor(ERROR_COLOR) if state in (CV_NONE, CV_ERROR) else normal)
        source.setForeground(normal)
        note.setForeground(QColor(UNSURE_FG) if state == CV_MAYBE else
                           QColor(RENAME_OK_COLOR) if state == CV_DONE else QColor(INFO_COLOR))

    def _cover_checked(self, item: QTableWidgetItem) -> None:
        if self._filling or item.column() != CV_CHECK:
            return
        row = self.rows[item.row()]
        if row.cover_state in (CV_SURE, CV_MAYBE):
            row.cover_on = item.checkState() == Qt.Checked
            self.refresh()

    def _covers_to_put(self) -> list[_Row]:
        return [r for r in self.rows if r.cover_on and r.cover_state in (CV_SURE, CV_MAYBE) and r.hit is not None]

    def _cell(self, r: int, c: int, text: str, color: QColor | None = None, changed: bool = False,
              editable: bool = False, orange: bool = False) -> None:
        item = self.table.item(r, c)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(r, c, item)
        item.setText(text)
        item.setToolTip(text if len(text) > 12 else "")
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        item.setFlags(flags | Qt.ItemIsEditable if editable or c in COPY_ONLY else flags)
        bg = UNSURE_BG if orange else CHANGED_BG if changed else None
        item.setBackground(QColor(bg) if bg else QColor(0, 0, 0, 0))
        item.setForeground(color if color is not None else self.palette().text().color())

    # ---- 줄 우클릭: 웹에서 찾기, 이 곡에만 그림 ----
    def row_menu(self, row: int) -> QMenu:
        menu = QMenu(self)
        for site, label in websearch.SITE_LABELS:
            menu.addAction(label, lambda s=site: self.search(row, s))
        menu.addSeparator()
        paste = menu.addAction("복사한 그림을 이 곡에 넣기", lambda: self.paste_picture_to(row))
        mime = QApplication.clipboard().mimeData()
        paste.setEnabled(mime is not None and TrackInfoDialog._mime_image_bytes(mime) is not None)
        menu.addAction("그림 파일을 이 곡에 넣기…", lambda: self._pick_picture_for(row))
        return menu

    def _row_menu(self, pos) -> None:
        row = self.table.rowAt(pos.y())
        if 0 <= row < len(self.rows):
            self.row_menu(row).exec_(self.table.viewport().mapToGlobal(pos))

    def _cover_row_menu(self, pos) -> None:
        row = self.cover_table.rowAt(pos.y())
        if 0 <= row < len(self.rows):
            self.row_menu(row).exec_(self.cover_table.viewport().mapToGlobal(pos))

    def search(self, row: int, site: str) -> None:
        """그 곡의 가수·제목(이름 정리 탭에서 본 값)으로 브라우저에서 찾는다."""
        r = self.rows[row]
        tab = self.tabs.currentIndex()
        artist, title = (r.names() if tab == TAB_NAMES else r.search_names() if tab == TAB_COVERS
                         else (r.orig["artist"], r.orig["title"]))
        terms = websearch.search_terms(artist, title, r.path)
        if terms:
            self._open_url(websearch.search_url(site, terms))

    def paste_picture_to(self, row: int) -> None:
        mime = QApplication.clipboard().mimeData()
        data = TrackInfoDialog._mime_image_bytes(mime) if mime is not None else None
        if data is None:
            self._say("복사한 그림이 없습니다 (브라우저에서 그림 우클릭 → 이미지 복사)", ERROR_COLOR)
            return
        self.save_picture_to(row, data)

    def _pick_picture_for(self, row: int) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "그림 넣기", "", "그림 (*.jpg *.jpeg *.png)")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read(MAX_PICTURE + 1)
        except OSError:
            self._say("그림 파일을 읽지 못했습니다", ERROR_COLOR)
            return
        self.save_picture_to(row, data)

    def save_picture_to(self, row: int, data: bytes) -> None:
        """그 곡 하나에만 그림을 바로 저장한다 (다른 곡·고친 칸은 그대로)."""
        if picture_mime(data) is None:
            self._say("jpg·png 그림만 넣을 수 있습니다", ERROR_COLOR)
            return
        if len(data) > MAX_PICTURE:
            self._say("그림이 너무 큽니다 (10 MB까지)", ERROR_COLOR)
            return
        if self._save_many is None:
            return
        r = self.rows[row]
        result = self._busy(self._save_many, [(r.path, {})], data)
        if self._has_cover is not None:
            r.has_cover = self._has_cover(r.path)
        if not result.failed:
            self._mark_put(r, data)
        name = os.path.basename(r.path)
        self._message = self._with_problems(f"그림을 넣었습니다: {name}", list(result.failed))
        self._after_change()
        self.refresh()

    def copy_cell(self) -> None:
        item = self.table.currentItem()
        if item is not None and item.text():
            QApplication.clipboard().setText(item.text())

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
        elif self.tabs.currentIndex() == TAB_COVERS:
            self.apply_covers()
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

    # ---- 그림 찾기 ----
    def start_cover_search(self) -> None:
        """그림 없는 곡을 하나씩 뒤에서 찾는다 (처음 한 번만; 다시 찾기는 research_covers)."""
        if self._cover_started:
            return
        self._cover_started = True
        self._queue_covers([r for r in self.rows if r.cover_state == CV_WAIT])

    def research_covers(self) -> None:
        self._queue_covers([r for r in self.rows if r.cover_state in (CV_NONE, CV_ERROR)])

    def _queue_covers(self, rows: list[_Row]) -> None:
        if self._find_cover is None or self._run_async is None:
            self.refresh()
            return
        for r in rows:
            r.cover_state = CV_WAIT
            if r not in self._cover_queue:
                self._cover_queue.append(r)
        self._next_cover()

    def _next_cover(self) -> None:
        if self._cover_running or self._stopped:
            return
        while self._cover_queue and self._cover_queue[0].cover_state != CV_WAIT:
            self._cover_queue.pop(0)
        if not self._cover_queue:
            self.refresh()
            return
        row = self._cover_queue.pop(0)
        row.cover_state = CV_BUSY
        self._cover_running = True
        artist, title = row.search_names()
        find = self._find_cover
        self.refresh()
        self._run_async(lambda: find(artist, title), lambda hit, error: self._cover_found(row, hit, error))

    def _cover_found(self, row: _Row, hit, error) -> None:
        self._cover_running = False
        if self._stopped:
            return
        if row.cover_state == CV_BUSY:   # 찾는 사이 사용자가 직접 넣었으면 그대로 둔다
            if error is not None:
                row.cover_state = CV_ERROR
            elif hit is None:
                row.cover_state = CV_NONE
            else:
                row.hit = hit
                row.thumb = self._thumb(hit.image)
                row.cover_state = CV_SURE if hit.sure else CV_MAYBE
                row.cover_on = hit.sure
        self.refresh()
        self._next_cover()

    @staticmethod
    def _thumb(data: bytes) -> QPixmap | None:
        pm = QPixmap()
        if not pm.loadFromData(data):
            return None
        return pm.scaled(THUMB, THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _mark_put(self, row: _Row, data: bytes) -> None:
        row.cover_state = CV_DONE
        row.cover_on = False
        row.thumb = self._thumb(data) or row.thumb

    def apply_covers(self) -> None:
        """체크한 곡마다 그 곡에서 찾은 그림을 넣는다 (곡마다 다른 그림)."""
        if self._save_many is None:
            return
        rows = self._covers_to_put()
        if not rows:
            return
        problems: list[tuple[str, str]] = []
        done = 0
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for r in rows:
                result = self._save_many([(r.path, {})], r.hit.image)
                if result.failed:
                    problems += list(result.failed)
                    continue
                done += 1
                if self._has_cover is not None:
                    r.has_cover = self._has_cover(r.path)
                self._mark_put(r, r.hit.image)
        finally:
            QApplication.restoreOverrideCursor()
        self._message = self._with_problems(f"그림 {done}곡 넣었습니다 (곡마다 찾은 그림)", problems)
        self._after_change()
        self.refresh()

    def closeEvent(self, event) -> None:
        self._stopped = True   # 남은 곡은 찾지 않는다 (찾던 한 곡의 결과는 버린다)
        super().closeEvent(event)

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
