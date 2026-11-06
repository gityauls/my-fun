from PyQt5.QtCore import QMimeData, QPointF, Qt
from PyQt5.QtGui import QColor, QDropEvent
from PyQt5.QtTest import QTest
from funplayer.core.stations import StationList
from funplayer.ui.playlist_view import ROLE_CURRENT, ROLE_TITLE, ROW_HEIGHT
from funplayer.ui.station_view import GROUP_HEIGHT, ROLE_COUNT, STATION_MIME, StationView

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
    assert [a.text() for a in v.context_menu.actions()] == ["듣기", "즐겨찾기", "이름 바꾸기…", "방송 그림 바꾸기…", "지우기", "", "기본 방송 다시 보이기"]
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
    assert row.data(0, ROLE_CURRENT) and not row.text(0).startswith("▶ ")
    v.rebuild(); assert v.topLevelItem(0).child(4).data(0, ROLE_CURRENT)
    v.set_current(None); assert not v.topLevelItem(0).child(4).data(0, ROLE_CURRENT)

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
    assert item.foreground(0).color() == QColor(t.ink)
    assert v.itemDelegate().theme is t         # 방송 줄은 그릴 때 테마를 따른다
    v._fill = real; v._fill()                  # 다시 채워도 같은 색이다
    assert v.topLevelItem(1).foreground(0).color() == QColor(t.ink)

def test_context_menu_is_named_for_the_panel_style(qapp):
    assert StationView().context_menu.objectName() == "themed"


# ---- 시안의 라디오 화면 ----

def drawn_view(theme="light", width=360):
    from funplayer.core.themes import get_theme
    v = StationView(); v.set_stations(StationList(), ["kr:big3"]); v.set_theme(get_theme(theme))
    v.resize(width, 400); v.show()
    return v, get_theme(theme)

def colors_in(img, rect):
    return {img.pixelColor(x, y).name() for x in range(rect.left(), rect.right() + 1)
            for y in range(rect.top(), rect.bottom() + 1)}

def test_rows_are_one_column_with_mockup_heights(qapp):
    v, _ = drawn_view()
    group = v.topLevelItem(0); row = group.child(0)
    assert v.columnCount() == 1 and row.text(1) == ""        # 방송사 칸은 없다
    assert (v.visualItemRect(group).height(), v.visualItemRect(row).height()) == (GROUP_HEIGHT, ROW_HEIGHT) == (32, 34)
    assert v.visualItemRect(row).left() == 0 and v.visualItemRect(row).width() == v.viewport().width()

def test_group_keeps_full_text_and_splits_the_count(qapp):
    v, _ = drawn_view()
    group = v.topLevelItem(0)
    assert group.text(0) == "국내 · KBS·MBC·SBS (12)"
    assert group.data(0, ROLE_TITLE) == "국내 · KBS·MBC·SBS" and group.data(0, ROLE_COUNT) == 12

def test_group_chevron_follows_expansion(qapp):
    v, t = drawn_view()
    group = v.topLevelItem(0)
    box = v.visualItemRect(group).adjusted(0, 0, -v.viewport().width() + 30, 0)
    opened = v.viewport().grab().toImage().copy(box)
    group.setExpanded(False); qapp.processEvents()
    closed = v.viewport().grab().toImage().copy(box)
    assert QColor(t.mute).name() in colors_in(closed, closed.rect()) and closed != opened

def test_playing_row_has_tint_mark_and_filled_live_chip(qapp):
    v, t = drawn_view()
    row = v.topLevelItem(0).child(2)
    plain = v.viewport().grab().toImage()
    v.set_current(row.data(0, Qt.UserRole)); qapp.processEvents()
    img = v.viewport().grab().toImage(); rect = v.visualItemRect(row)
    assert row.data(0, ROLE_CURRENT) and QColor(t.tint).name() in colors_in(img, rect)
    assert QColor(t.tint).name() not in colors_in(plain, rect)
    assert QColor(t.row_fg).name() in colors_in(img, rect.adjusted(10, 0, -rect.width() + 24, 0))   # 막대
    assert QColor(t.acc).name() in colors_in(img, rect.adjusted(rect.width() - 60, 0, 0, 0))        # 칩
    v.set_current(None); qapp.processEvents()
    assert not row.data(0, ROLE_CURRENT)
    assert QColor(t.tint).name() not in colors_in(v.viewport().grab().toImage(), rect)

def test_playing_row_survives_rebuild_and_uses_bold_title(qapp):
    v, _ = drawn_view()
    v.set_current("kbs-25"); v.rebuild()
    row = v.topLevelItem(0).child(4); assert row.data(0, ROLE_CURRENT)
    d = v.itemDelegate(); seen = {}; real = d.title_font
    d.title_font = lambda base, cur: seen.setdefault(cur, real(base, cur))   # offscreen은 글꼴을 픽셀로 못 잰다
    v.viewport().grab()
    assert seen[True].bold() and not seen[False].bold()

def test_rgba_tint_paints_in_the_row(qapp):
    from dataclasses import replace
    from funplayer.core.themes import get_theme
    v, _ = drawn_view()
    t = replace(get_theme("light"), tint="rgba(255,0,0,1)"); v.set_theme(t)
    row = v.topLevelItem(0).child(1); v.set_current(row.data(0, Qt.UserRole)); qapp.processEvents()
    assert "#ff0000" in colors_in(v.viewport().grab().toImage(), v.visualItemRect(row))

def test_selected_row_is_tinted_like_the_playlist(qapp):
    v, t = drawn_view()
    row = v.topLevelItem(0).child(1); v.setCurrentItem(row); qapp.processEvents()
    assert QColor(t.tint).name() in colors_in(v.viewport().grab().toImage(), v.visualItemRect(row))

def test_long_name_is_elided_before_the_chip(qapp):
    v, _ = drawn_view(width=200)
    row = v.topLevelItem(0).child(0); row.setData(0, ROLE_TITLE, "아주 긴 방송 이름 " * 8)
    v.set_current(row.data(0, Qt.UserRole)); qapp.processEvents()
    assert v.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert v.visualItemRect(row).width() <= v.viewport().width()
