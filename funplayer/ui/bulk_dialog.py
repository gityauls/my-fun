"""여러 곡 태그 창 (5-D): 탭에서 채우는 방법을 고르고, 미리 보기 표에서 확인한 뒤 한 번에 저장한다."""
from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QShortcut, QSizePolicy, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from funplayer.core import bulktag, renamer
from funplayer.core.taginfo import TrackInfo
from funplayer.engine.tagwrite import KEEP, picture_mime
from funplayer.ui.colors import CHANGED_BG, ERROR_COLOR, INFO_COLOR, RENAME_OK_COLOR
from funplayer.ui.info_dialog import GENRES, MAX_PICTURE, TrackInfoDialog

COLUMNS = [("파일 이름", None), ("가수", "artist"), ("제목", "title"), ("앨범", "album"), ("트랙", "track"),
           ("새 파일 이름", None)]
NEW_NAME_COL = 5
COMMON = [("가수", "artist"), ("앨범", "album"), ("년도", "year"), ("장르", "genre")]
NAME_PATTERNS = [("자동 짐작  ([가수]제목 · 가수 - 제목 · 앞 번호는 트랙)", bulktag.AUTO),
                 ("%가수% - %제목%", None), ("[%가수%]%제목%", None), ("[%가수%]%트랙%.%제목%", None),
                 ("%트랙%. %제목%", None), ("%트랙% %가수% - %제목%", None)]
LINE_PATTERNS = [("자동  (앞 번호는 트랙, 나머지는 제목)", bulktag.AUTO), ("%제목%", None),
                 ("%트랙%. %제목%", None), ("%가수% - %제목%", None)]
TAB_COMMON, TAB_NAME, TAB_PASTE, TAB_TRACK, TAB_RENAME = range(5)
MANY = "(여러 값 · 그대로 둠)"


class _Row:
    def __init__(self, info: TrackInfo) -> None:
        self.path = info.path
        self.orig = {k: getattr(info, k) or "" for k in bulktag.FIELDS}


class BulkTagDialog(QDialog):
    def __init__(self, infos: list[TrackInfo], parent=None, save_many=None, rename_many=None,
                 undo_many=None, read_info=None, after_change=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("여러 곡 태그")
        mp3 = [i for i in infos if i.path.lower().endswith(".mp3")]
        self.skipped = len(infos) - len(mp3)
        self.rows = [_Row(i) for i in mp3]
        self._save_many = save_many
        self._rename_many = rename_many
        self._undo_many = undo_many
        self._read_info = read_info
        self._after_change = after_change or (lambda: None)
        self.manual: dict[tuple[int, str], str] = {}
        self.picture: bytes | None = None
        self.last_renames: list[tuple[str, str]] = []
        self._visited: set[int] = set()
        self._message = ("", INFO_COLOR)
        self._filling = True   # 만드는 동안 칸들이 보내는 신호로 refresh가 돌지 않게
        self._build()
        self._filling = False
        self.refresh()

    # ---- 만들기 ----
    def _build(self) -> None:
        v = QVBoxLayout(self)
        v.setSpacing(8)
        self.head = QLabel()
        v.addWidget(self.head)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._common_tab(), "공통 칸")
        self.tabs.addTab(self._name_tab(), "파일 이름 → 태그")
        self.tabs.addTab(self._paste_tab(), "붙여 넣기 → 태그")
        self.tabs.addTab(self._track_tab(), "트랙 번호")
        self.tabs.addTab(self._rename_tab(), "파일 이름 바꾸기")
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)   # 남는 높이는 미리 보기 표로
        v.addWidget(self.tabs)
        v.addWidget(QLabel(f"<b>미리 보기</b> <span style='color:{INFO_COLOR};'>· 노란 칸 = 저장하면 바뀔 값 · "
                           "칸을 두 번 눌러 직접 고칠 수 있습니다</span>"))
        t = self.table = QTableWidget(len(self.rows), len(COLUMNS))
        t.setHorizontalHeaderLabels([c for c, _ in COLUMNS])
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        h = t.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, width in ((1, 110), (2, 150), (3, 110), (4, 44), (5, 220)):
            t.setColumnWidth(col, width)
        t.itemChanged.connect(self._cell_edited)
        t.setMinimumHeight(180)
        v.addWidget(t, 1)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        v.addWidget(self.message_label)
        b = QHBoxLayout()
        b.addStretch(1)
        self.save_button = QPushButton()
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save)
        close = QPushButton("닫기")
        close.clicked.connect(self.close)
        b.addWidget(self.save_button)
        b.addWidget(close)
        v.addLayout(b)
        paste = QShortcut(QKeySequence.Paste, self)
        paste.setContext(Qt.WidgetWithChildrenShortcut)
        paste.activated.connect(self._paste)
        self.resize(760, 560)

    def _tab_page(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        return w, lay

    def _use_box(self, text: str) -> QCheckBox:
        box = QCheckBox(text)
        box.toggled.connect(self.refresh)
        return box

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
        self.picture_label = QLabel("Ctrl+V로 붙여 넣기도 됩니다")
        self.picture_label.setStyleSheet(f"color: {INFO_COLOR};")
        g.addWidget(self.picture_box, 0, 2)
        g.addWidget(pick, 1, 2)
        g.addWidget(self.picture_label, 2, 2, 2, 1, Qt.AlignTop)
        g.setColumnStretch(1, 1)
        return w

    def _name_tab(self) -> QWidget:
        w, lay = self._tab_page()
        self.name_on = self._use_box("이 방법으로 채우기")
        lay.addWidget(self.name_on)
        row = QHBoxLayout()
        row.addWidget(QLabel("이름 모양"))
        self.name_pattern = QComboBox()
        self.name_pattern.setEditable(True)
        for text, _ in NAME_PATTERNS:
            self.name_pattern.addItem(text)
        self.name_pattern.setMinimumWidth(380)
        self.name_pattern.currentTextChanged.connect(self.refresh)
        row.addWidget(self.name_pattern)
        row.addStretch(1)
        lay.addLayout(row)
        hint = QLabel("직접 쓸 수 있는 낱말: %가수% %제목% %앨범% %년도% %장르% %트랙%")
        hint.setStyleSheet(f"color: {INFO_COLOR};")
        lay.addWidget(hint)
        opts = QHBoxLayout()
        self.only_empty = QCheckBox("비어 있는 칸만 채우기")
        self.underscores = QCheckBox("밑줄(_)을 빈칸으로")
        self.underscores.setChecked(True)
        for box in (self.only_empty, self.underscores):
            box.toggled.connect(self.refresh)
            opts.addWidget(box)
        opts.addStretch(1)
        lay.addLayout(opts)
        lay.addStretch(1)
        return w

    def _paste_tab(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(10, 8, 10, 8)
        self.paste_text = QPlainTextEdit()
        self.paste_text.setPlaceholderText("1. 첫 곡 제목\n2. 둘째 곡 제목\n…")
        self.paste_text.setFixedSize(260, 112)   # 탭 높이는 가장 큰 탭을 따르니 낮게 둔다
        self.paste_text.textChanged.connect(self._paste_changed)
        h.addWidget(self.paste_text)
        side = QVBoxLayout()
        self.paste_on = self._use_box("이 방법으로 채우기")
        side.addWidget(self.paste_on)
        row = QHBoxLayout()
        row.addWidget(QLabel("줄 모양"))
        self.line_pattern = QComboBox()
        self.line_pattern.setEditable(True)
        for text, _ in LINE_PATTERNS:
            self.line_pattern.addItem(text)
        self.line_pattern.currentTextChanged.connect(self.refresh)
        row.addWidget(self.line_pattern, 1)
        side.addLayout(row)
        hint = QLabel("지니·멜론 앨범 화면의 곡 목록을 복사해 붙여 넣으세요.\n윗줄부터 아래 표의 곡에 차례로 들어갑니다.")
        hint.setStyleSheet(f"color: {INFO_COLOR};")
        side.addWidget(hint)
        moves = QHBoxLayout()
        up, down = QPushButton("↑ 곡 순서 올리기"), QPushButton("↓ 내리기")
        up.clicked.connect(lambda: self.move_row(-1))
        down.clicked.connect(lambda: self.move_row(1))
        moves.addWidget(up)
        moves.addWidget(down)
        moves.addStretch(1)
        side.addLayout(moves)
        side.addStretch(1)
        h.addLayout(side, 1)
        return w

    def _track_tab(self) -> QWidget:
        w, lay = self._tab_page()
        self.track_on = self._use_box("표의 순서대로 트랙 번호 매기기")
        lay.addWidget(self.track_on)
        row = QHBoxLayout()
        row.addWidget(QLabel("시작 번호"))
        self.track_start = QSpinBox()
        self.track_start.setRange(1, 999)
        self.track_start.valueChanged.connect(self.refresh)
        row.addWidget(self.track_start)
        self.track_total = QCheckBox("전체 곡 수 붙이기 (예: 3/12)")
        self.track_total.toggled.connect(self.refresh)
        row.addWidget(self.track_total)
        row.addStretch(1)
        lay.addLayout(row)
        hint = QLabel("순서는 '붙여 넣기 → 태그' 탭의 올리기·내리기로 바꿀 수 있습니다.")
        hint.setStyleSheet(f"color: {INFO_COLOR};")
        lay.addWidget(hint)
        lay.addStretch(1)
        return w

    def _rename_tab(self) -> QWidget:
        w, lay = self._tab_page()
        info = QLabel("저장된 태그로 고른 곡 모두를 <b>가수 - 제목.mp3</b>로 바꿉니다. 같은 폴더 안에서 이름만 바꾸고, "
                      "같은 이름의 파일이 있으면 그 곡은 건너뜁니다. 새 이름은 아래 표 맨 오른쪽 칸에 보입니다.")
        info.setWordWrap(True)
        lay.addWidget(info)
        row = QHBoxLayout()
        self.rename_button = QPushButton()
        self.rename_button.clicked.connect(self.rename)
        self.undo_button = QPushButton("한 번에 되돌리기")
        self.undo_button.clicked.connect(self.undo_renames)
        row.addWidget(self.rename_button)
        row.addWidget(self.undo_button)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _shared(self, key: str) -> str:
        values = {r.orig[key] for r in self.rows}
        return values.pop() if len(values) == 1 else ""

    # ---- 값 계산 ----
    def _name_pattern_value(self) -> str:
        text = self.name_pattern.currentText().strip()
        return next((p for t, p in NAME_PATTERNS if t == text and p), text)

    def _line_pattern_value(self) -> str:
        text = self.line_pattern.currentText().strip()
        return next((p for t, p in LINE_PATTERNS if t == text and p), text)

    def paste_values(self) -> list[dict[str, str]] | None:
        """붙여 넣기 값. 쓰지 않으면 None, 모양이 틀리면 PatternError."""
        if not self.paste_on.isChecked():
            return None
        return bulktag.from_lines(self.paste_text.toPlainText(), self._line_pattern_value())

    def pending(self) -> list[dict[str, str]]:
        """곡마다 저장하면 될 값 (원래 값 + 각 탭 + 직접 고친 칸)."""
        name_on = self.name_on.isChecked()
        pattern = self._name_pattern_value() if name_on else ""
        try:
            lines = self.paste_values()
        except bulktag.PatternError:
            lines = None
        if lines is not None and len(lines) != len(self.rows):
            lines = None
        tracks = (bulktag.track_numbers(len(self.rows), self.track_start.value(), self.track_total.isChecked())
                  if self.track_on.isChecked() else None)
        common = {k: self.common_edits[k].text().strip() for k, box in self.common_boxes.items() if box.isChecked()}
        out = []
        for i, row in enumerate(self.rows):
            values = dict(row.orig)
            if name_on:
                try:
                    guessed = bulktag.from_filename(row.path, pattern, self.underscores.isChecked())
                except bulktag.PatternError:
                    guessed = {}
                values = bulktag.merge(values, guessed, self.only_empty.isChecked())
            if lines is not None:
                values = bulktag.merge(values, lines[i])
            if tracks is not None:
                values["track"] = tracks[i]
            values = bulktag.merge(values, common)
            for (r, k), v in self.manual.items():
                if r == i:
                    values[k] = v
            out.append(values)
        return out

    def changes(self) -> list[dict[str, str]]:
        return [{k: v for k, v in p.items() if v != row.orig[k]} for p, row in zip(self.pending(), self.rows)]

    def _picture_on(self) -> bool:
        return self.picture_box.isChecked() and self.picture is not None

    def _problem(self) -> str:
        """저장을 막는 까닭 (없으면 "")."""
        if self.name_on.isChecked():
            try:
                pattern = self._name_pattern_value()
                if pattern != bulktag.AUTO:
                    bulktag.compile_pattern(pattern)
            except bulktag.PatternError as e:
                return f"이름 모양: {e}"
        try:
            lines = self.paste_values()
        except bulktag.PatternError as e:
            return f"줄 모양: {e}"
        if lines is not None and len(lines) != len(self.rows):
            return f"{len(lines)}줄 · {len(self.rows)}곡: 줄 수와 곡 수가 같아야 저장할 수 있습니다"
        return ""

    # ---- 화면 ----
    def refresh(self) -> None:
        if self._filling:
            return
        self._filling = True
        try:
            pending = self.pending()
            changes = [{k: v for k, v in p.items() if v != row.orig[k]} for p, row in zip(pending, self.rows)]
            on_rename = self.tabs.currentIndex() == TAB_RENAME
            self.table.setColumnHidden(NEW_NAME_COL, not on_rename)
            for i, (row, values, changed) in enumerate(zip(self.rows, pending, changes)):
                for col, (_, key) in enumerate(COLUMNS):
                    if col == 0:
                        self._set_cell(i, col, os.path.basename(row.path), False, QColor(INFO_COLOR))
                    elif col == NEW_NAME_COL:
                        self._set_cell(i, col, self._new_name_text(row), False)
                    else:
                        self._set_cell(i, col, values[key], key in changed, editable=True)
            n = sum(1 for c in changes if c) if not self._picture_on() else len(self.rows)
            problem = self._problem()
            self.save_button.setText(f"저장 ({n}곡)")
            self.save_button.setEnabled(n > 0 and not problem)
            unsaved = n > 0
            targets = len(self.rename_pairs())
            self.rename_button.setText("먼저 [저장]을 누르세요" if unsaved else f"파일 이름 바꾸기 ({targets}곡)")
            self.rename_button.setEnabled(not unsaved and targets > 0)
            self.undo_button.setVisible(bool(self.last_renames))
            head = f"<b>여러 곡 태그</b> <span style='color:{INFO_COLOR};'>· 고른 곡 {len(self.rows)}곡"
            if self.skipped:
                head += f" (MP3가 아닌 {self.skipped}곡은 뺐습니다)"
            self.head.setText(head + "</span>")
            text, color = (problem, ERROR_COLOR) if problem else self._message
            self.message_label.setText(text)
            self.message_label.setStyleSheet(f"color: {color};")
        finally:
            self._filling = False

    def _set_cell(self, r: int, c: int, text: str, changed: bool, color: QColor | None = None,
                  editable: bool = False) -> None:
        item = self.table.item(r, c)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(r, c, item)
        item.setText(text)
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        item.setFlags(flags | Qt.ItemIsEditable if editable else flags)
        item.setBackground(QColor(CHANGED_BG) if changed else QColor(0, 0, 0, 0))
        item.setForeground(color if color is not None else self.palette().text().color())

    def _new_name_text(self, row: _Row) -> str:
        target = self._target(row)
        if target is None:
            return "(가수·제목이 있어야 합니다)"
        if target == row.path:
            return "(지금 이름과 같음)"
        if renamer.conflict(row.path, target):
            return f"{os.path.basename(target)}  (같은 이름 있음)"
        return os.path.basename(target)

    @staticmethod
    def _target(row: _Row) -> str | None:
        return renamer.target_path(row.path, row.orig["artist"], row.orig["title"])

    def rename_pairs(self) -> list[tuple[str, str]]:
        pairs = []
        for row in self.rows:
            target = self._target(row)
            if target is not None and target != row.path and not renamer.conflict(row.path, target):
                pairs.append((row.path, target))
        return pairs

    def _tab_changed(self, index: int) -> None:
        if index not in self._visited:
            self._visited.add(index)
            if index == TAB_NAME:
                self.name_on.setChecked(True)
            elif index == TAB_TRACK:
                self.track_on.setChecked(True)
        self.refresh()

    def _paste_changed(self) -> None:
        if self.paste_text.toPlainText().strip() and not self.paste_on.isChecked():
            self.paste_on.setChecked(True)
        else:
            self.refresh()

    def _cell_edited(self, item: QTableWidgetItem) -> None:
        if self._filling:
            return
        key = COLUMNS[item.column()][1]
        if key is None or item.column() == NEW_NAME_COL:
            return
        self.manual[(item.row(), key)] = item.text().strip()
        self.refresh()

    def move_row(self, step: int) -> None:
        i = self.table.currentRow()
        j = i + step
        if not (0 <= i < len(self.rows) and 0 <= j < len(self.rows)):
            return
        self.rows[i], self.rows[j] = self.rows[j], self.rows[i]
        swapped = {}
        for (r, k), v in self.manual.items():
            swapped[(j if r == i else i if r == j else r, k)] = v
        self.manual = swapped
        self.refresh()
        self.table.selectRow(j)

    # ---- 그림 ----
    def set_picture(self, data: bytes) -> bool:
        if picture_mime(data) is None:
            return self._say("jpg·png 그림만 넣을 수 있습니다", ERROR_COLOR)
        if len(data) > MAX_PICTURE:
            return self._say("그림이 너무 큽니다 (10 MB까지)", ERROR_COLOR)
        self.picture = data
        self.picture_label.setText(f"고른 그림 ({len(data) // 1024} KB)")
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
            self.set_picture(data)

    def _say(self, text: str, color: str) -> bool:
        self._message = (text, color)
        self.refresh()
        return False

    # ---- 저장·이름 바꾸기 ----
    def save(self) -> None:
        if self._problem() or self._save_many is None:
            return
        picture = self.picture if self._picture_on() else KEEP
        changes = self.changes()
        items = [(row.path, c) for row, c in zip(self.rows, changes) if c or picture is not KEEP]
        if not items:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = self._save_many(items, picture)
        finally:
            QApplication.restoreOverrideCursor()
        failed = {p for p, _ in result.failed}
        for row, change in zip(self.rows, changes):
            if row.path in failed:
                continue
            if self._read_info is not None:
                row.orig = _Row(self._read_info(row.path)).orig
            else:
                row.orig.update(change)
        self.manual = {k: v for k, v in self.manual.items() if self.rows[k[0]].path in failed}
        for box in (self.name_on, self.paste_on, self.track_on, self.picture_box, *self.common_boxes.values()):
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)
        self._visited = {self.tabs.currentIndex()}
        self._message = self._result_text("저장했습니다", result)
        self._after_change()
        self.refresh()

    def rename(self) -> None:
        pairs = self.rename_pairs()
        if not pairs or self._rename_many is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = self._rename_many(pairs)
        finally:
            QApplication.restoreOverrideCursor()
        self._move_paths(result.done)
        self.last_renames = list(result.done)
        self._message = self._result_text("파일 이름을 바꿨습니다", result)
        self._after_change()
        self.refresh()

    def undo_renames(self) -> None:
        if not self.last_renames or self._undo_many is None:
            return
        result = self._undo_many(self.last_renames)
        self._move_paths(result.done)
        self.last_renames = []
        self._message = self._result_text("파일 이름을 되돌렸습니다", result)
        self._after_change()
        self.refresh()

    def _move_paths(self, done: list[tuple[str, str]]) -> None:
        moved = {os.path.normcase(a): b for a, b in done}
        for row in self.rows:
            row.path = moved.get(os.path.normcase(row.path), row.path)

    @staticmethod
    def _result_text(done_text: str, result) -> tuple[str, str]:
        if not result.failed:
            return f"{len(result.done)}곡 {done_text}", RENAME_OK_COLOR
        names = ", ".join(os.path.basename(p) for p, _ in result.failed[:3])
        more = " 등" if len(result.failed) > 3 else ""
        reason = result.failed[0][1]
        return (f"{len(result.done)}곡 {done_text}. {len(result.failed)}곡은 못 했습니다: {names}{more} ({reason})",
                ERROR_COLOR)
