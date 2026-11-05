from PyQt5.QtCore import QMimeData, QPointF, Qt
from PyQt5.QtGui import QDropEvent
from PyQt5.QtTest import QTest
from funplayer.core.stations import StationList
from funplayer.ui.station_view import STATION_MIME, StationView

def test_groups_and_one_click_plays(qapp):
    v = StationView(); sl = StationList(); v.set_stations(sl, ["favorites", "kr:big3", "user"])
    top = [v.topLevelItem(i).text(0) for i in range(v.topLevelItemCount())]
    assert top[0] == "국내 · KBS·MBC·SBS (12)" and top[1].startswith("국내 · EBS")
    hits = []; v.station_activated.connect(hits.append)
    dom = v.topLevelItem(0); assert dom.isExpanded() and not v.topLevelItem(1).isExpanded()
    v.resize(400, 400); v.show()
    rect = v.visualItemRect(dom.child(4)); QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=rect.center())
    assert hits == ["kbs-25"]

def test_double_click_starts_once(qapp):
    v = StationView(); v.set_stations(StationList(), ["kr:big3"]); v.resize(400, 400); v.show()
    hits = []; v.station_activated.connect(hits.append)
    pos = v.visualItemRect(v.topLevelItem(0).child(4)).center()
    QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=pos); QTest.mouseDClick(v.viewport(), Qt.LeftButton, pos=pos)
    assert hits == ["kbs-25"]

def test_group_row_click_only_toggles(qapp):
    v = StationView(); v.set_stations(StationList(), []); hits = []; v.station_activated.connect(hits.append)
    v.resize(400, 400); v.show()
    g = v.topLevelItem(1); QTest.mouseClick(v.viewport(), Qt.LeftButton, pos=v.visualItemRect(g).center())
    assert g.isExpanded() and hits == []

def test_enter_plays_current(qapp):
    v = StationView(); v.set_stations(StationList(), ["kr:big3"]); hits = []; v.station_activated.connect(hits.append)
    v.setCurrentItem(v.topLevelItem(0).child(1)); QTest.keyClick(v, Qt.Key_Return)
    assert hits == ["kbs-22"]

def test_context_menu_favorite_rename_remove_restore(qapp, monkeypatch):
    import funplayer.ui.station_view as sv
    v = StationView(); sl = StationList(); v.set_stations(sl, ["favorites", "kr:big3"]); changed = []
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
    v = StationView(); v.set_stations(StationList(), ["kr:big3"]); v.set_current("kbs-25")
    row = v.topLevelItem(0).child(4)
    assert row.text(0).startswith("▶ ") and row.font(0).bold()
    v.rebuild(); assert v.topLevelItem(0).child(4).text(0).startswith("▶ ")
    v.set_current(None); assert not v.topLevelItem(0).child(4).text(0).startswith("▶ ")

def test_open_groups_reported(qapp):
    v = StationView(); v.set_stations(StationList(), ["kr:big3"]); got = []
    v.open_groups_changed.connect(got.append)
    g = v.topLevelItem(1); g.setExpanded(True)
    assert got and "kr:big3" in got[-1] and g.data(0, Qt.UserRole + 1) in got[-1]

def test_drop_reorders_within_group_only(qapp):
    v = StationView(); sl = StationList(); v.set_stations(sl, ["kr:big3"]); v.resize(400, 400); v.show()
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

def test_set_theme_recolours_in_place_and_keeps_scroll(qapp):
    from PyQt5.QtGui import QColor
    from funplayer.core.themes import get_theme
    v = StationView(); sl = StationList(); sl.set_favorite("kbs-25", True)
    v.set_stations(sl, ["favorites", "kr:big3", "user"]); v.resize(300, 200); v.show()
    bar = v.verticalScrollBar(); assert bar.maximum() > 0
    bar.setValue(bar.maximum() // 2); kept = bar.value()
    item = v.topLevelItem(1); fills = []; real = v._fill; v._fill = lambda: fills.append(1)
    t = get_theme("dark"); v.set_theme(t)
    assert fills == [] and bar.value() == kept and v.topLevelItem(1) is item
    assert v.topLevelItem(0).foreground(0).color() == QColor(t.fav)
    assert item.foreground(0).color() == QColor(t.mute)
    assert item.child(0).foreground(1).color() == QColor(t.mute)
    v._fill = real; v._fill()                  # 다시 채워도 같은 색이다
    assert v.topLevelItem(1).foreground(0).color() == QColor(t.mute)

def test_context_menu_is_named_for_the_panel_style(qapp):
    assert StationView().context_menu.objectName() == "themed"
