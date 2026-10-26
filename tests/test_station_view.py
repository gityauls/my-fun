from PyQt5.QtCore import QMimeData, QPointF, Qt
from PyQt5.QtGui import QDropEvent
from PyQt5.QtTest import QTest
from funplayer.core.stations import StationList
from funplayer.ui.station_view import STATION_MIME, StationView

def test_groups_and_one_click_plays(qapp):
    v = StationView(); sl = StationList(); v.set_stations(sl, ["favorites", "domestic", "user"])
    top = [v.topLevelItem(i).text(0) for i in range(v.topLevelItemCount())]
    assert top[0] == "국내 방송" and top[1].startswith("해외 추천 · ")
    hits = []; v.station_activated.connect(hits.append)
    dom = v.topLevelItem(0); assert dom.isExpanded() and not v.topLevelItem(1).isExpanded()
    v.resize(400, 400); v.show()
    rect = v.visualItemRect(dom.child(3)); QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=rect.center())
    assert hits == ["kbs-25"]

def test_double_click_starts_once(qapp):
    v = StationView(); v.set_stations(StationList(), ["domestic"]); v.resize(400, 400); v.show()
    hits = []; v.station_activated.connect(hits.append)
    pos = v.visualItemRect(v.topLevelItem(0).child(3)).center()
    QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=pos); QTest.mouseDClick(v.viewport(), Qt.LeftButton, pos=pos)
    assert hits == ["kbs-25"]

def test_group_row_click_only_toggles(qapp):
    v = StationView(); v.set_stations(StationList(), []); hits = []; v.station_activated.connect(hits.append)
    v.resize(400, 400); v.show()
    g = v.topLevelItem(1); QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=v.visualItemRect(g).center())
    assert g.isExpanded() and hits == []

def test_enter_plays_current(qapp):
    v = StationView(); v.set_stations(StationList(), ["domestic"]); hits = []; v.station_activated.connect(hits.append)
    v.setCurrentItem(v.topLevelItem(0).child(1)); QTest.keyClick(v, Qt.Key_Return)
    assert hits == ["kbs-22"]

def test_context_menu_favorite_rename_remove_restore(qapp, monkeypatch):
    import funplayer.ui.station_view as sv
    v = StationView(); sl = StationList(); v.set_stations(sl, ["favorites", "domestic"]); changed = []
    v.changed.connect(lambda: changed.append(1))
    v.setCurrentItem(v.topLevelItem(0).child(0)); v.context_menu.aboutToShow.emit()
    assert [a.text() for a in v.context_menu.actions()] == ["듣기", "즐겨찾기", "이름 바꾸기…", "지우기", "", "기본 방송 다시 보이기"]
    v.actions["favorite"].trigger(); assert v.topLevelItem(0).text(0) == "★ 즐겨찾기" and sl.is_favorite("kbs-21")
    monkeypatch.setattr(sv, "ask_name", lambda parent, current: "1R")
    v.setCurrentItem(v.topLevelItem(0).child(0)); v.actions["rename"].trigger(); assert sl.get("kbs-21").name == "1R"
    v.setCurrentItem(v.topLevelItem(0).child(0)); v.actions["remove"].trigger(); assert sl.get("kbs-21") is None
    v.actions["restore"].trigger(); assert sl.get("kbs-21") is not None and len(changed) == 4

def test_favorite_action_reflects_state(qapp):
    v = StationView(); sl = StationList(); sl.set_favorite("kbs-21", True); v.set_stations(sl, ["favorites"])
    v.setCurrentItem(v.topLevelItem(0).child(0)); v.context_menu.aboutToShow.emit()
    assert v.actions["favorite"].isChecked()

def test_set_current_marks_row(qapp):
    v = StationView(); v.set_stations(StationList(), ["domestic"]); v.set_current("kbs-25")
    row = v.topLevelItem(0).child(3)
    assert row.text(0).startswith("▶ ") and row.font(0).bold()
    v.rebuild(); assert v.topLevelItem(0).child(3).text(0).startswith("▶ ")
    v.set_current(None); assert not v.topLevelItem(0).child(3).text(0).startswith("▶ ")

def test_open_groups_reported(qapp):
    v = StationView(); v.set_stations(StationList(), ["domestic"]); got = []
    v.open_groups_changed.connect(got.append)
    g = v.topLevelItem(1); g.setExpanded(True)
    assert got and "domestic" in got[-1] and g.data(0, Qt.UserRole + 1) in got[-1]

def test_drop_reorders_within_group_only(qapp):
    v = StationView(); sl = StationList(); v.set_stations(sl, ["domestic"]); v.resize(400, 400); v.show()
    dom = v.topLevelItem(0)
    def drop(src_id, item, top=True):
        md = QMimeData(); md.setData(STATION_MIME, src_id.encode())
        r = v.visualItemRect(item); y = r.top() + 1 if top else r.bottom() - 1
        v.dropEvent(QDropEvent(QPointF(5, y), Qt.MoveAction, md, Qt.LeftButton, Qt.NoModifier))
    drop("kbs-25", dom.child(0))
    assert [s.id for s in sl.groups()[0][2]][0] == "kbs-25"
    order = [s.id for s in sl.visible()]
    drop("kbs-25", v.topLevelItem(1))   # 묶음 줄 위: 무시
    assert [s.id for s in sl.visible()] == order
