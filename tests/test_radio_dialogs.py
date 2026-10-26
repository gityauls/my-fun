import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QDialog
from funplayer.ui.radio_dialogs import AddUrlDialog, valid_url

def test_add_url_dialog_validates(qapp):
    d = AddUrlDialog(); d.url_edit.setText("ftp://x"); d.add_button.click()
    assert d.error_label.text() == "주소가 올바르지 않습니다" and d.result() == 0 and d.result_value() is None
    d.name_edit.setText(" 우리 동네 "); d.url_edit.setText(" https://s.example/live.mp3 "); d.add_button.click()
    assert d.result() == QDialog.Accepted and d.result_value() == ("우리 동네", "https://s.example/live.mp3")

def test_dialog_texts(qapp):
    d = AddUrlDialog()
    assert d.windowTitle() == "주소 넣기" and (d.add_button.text(), d.cancel_button.text()) == ("넣기", "취소")
    assert d.hint_label.text() == "http·https 방송 주소, .m3u·.pls·.m3u8 주소를 넣을 수 있습니다."
    assert d.error_label.text() == "" and d.add_button.isDefault() and d.isModal()

def test_enter_in_field_adds(qapp):
    d = AddUrlDialog(); d.show(); d.url_edit.setText("http://a.b/x"); d.url_edit.setFocus()
    QTest.keyClick(d.url_edit, Qt.Key_Return)
    assert d.result() == QDialog.Accepted and d.result_value() == ("", "http://a.b/x")

@pytest.mark.parametrize("u,ok", [("http://a", True), ("https://a.b/c", True), ("http://", False), ("a.b", False), ("", False)])
def test_valid_url(u, ok):
    assert valid_url(u) is ok
