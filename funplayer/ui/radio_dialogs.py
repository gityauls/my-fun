from __future__ import annotations

from urllib.parse import urlsplit

from PyQt5.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QVBoxLayout)

from funplayer.ui.colors import ERROR_COLOR, INFO_COLOR

BAD_URL_MSG = "주소가 올바르지 않습니다"
HINT_MSG = "http·https 방송 주소, .m3u·.pls·.m3u8 주소를 넣을 수 있습니다."


def valid_url(text: str) -> bool:
    """http 또는 https로 시작하고 호스트가 있으면 올바른 주소로 본다."""
    try:
        parts = urlsplit(text.strip())
        return parts.scheme.lower() in ("http", "https") and bool(parts.hostname)
    except ValueError:
        return False


class AddUrlDialog(QDialog):
    """[주소 넣기…] 창. 이름(비워도 됨)과 주소를 받는다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("주소 넣기")
        self.setModal(True)
        self._value: tuple[str, str] | None = None
        self.name_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self.hint_label = QLabel(HINT_MSG)
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(f"color: {INFO_COLOR};")
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {ERROR_COLOR};")
        self.add_button = QPushButton("넣기")
        self.add_button.setDefault(True)
        self.cancel_button = QPushButton("취소")
        form = QFormLayout()
        form.addRow("이름", self.name_edit)
        form.addRow("주소", self.url_edit)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.cancel_button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)
        self.add_button.clicked.connect(self._add)
        self.cancel_button.clicked.connect(self.reject)
        self.name_edit.returnPressed.connect(self._add)
        self.url_edit.returnPressed.connect(self._add)
        self.resize(420, self.sizeHint().height())

    def _add(self) -> None:
        url = self.url_edit.text().strip()
        if not valid_url(url):
            self.error_label.setText(BAD_URL_MSG)
            return
        self.error_label.setText("")
        self._value = (self.name_edit.text().strip(), url)
        self.accept()

    def result_value(self) -> tuple[str, str] | None:
        return self._value
