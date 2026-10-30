from __future__ import annotations

import logging
import os

from funplayer.core import taginfo
from funplayer.core.effects import FxSettings
from funplayer.core.m3u import PLAYLIST_EXTS, is_playlist, read_playlist, write_playlist
from funplayer.core.playlist import Playlist
from funplayer.core.settings import REPEAT_MODES, Settings
from funplayer.core.timefmt import format_time
from funplayer.core.tracks import expand_paths
from funplayer.engine import tags
from funplayer.engine.decoder import DecodeError
from funplayer.engine.player import State
from funplayer.radio import RESUME_RADIO_MSG, RadioState

EMPTY_TITLE = "곡을 추가하세요"
NO_FILES_MSG = "재생할 수 있는 파일이 없습니다"
FAIL_MSG = "열 수 없음: {name}"
LOAD_FAIL_MSG = "불러올 수 없음: {name}"
SAVED_MSG = "저장했습니다: {name}"
SAVE_FAIL_MSG = "저장할 수 없음: {name}"
MISSING_MSG = "없는 파일 {n}곡"
DUP_MSG = "중복 곡 {n}개를 지웠습니다"
NO_DUP_MSG = "중복 곡이 없습니다"
REMOVED_MSG = "{n}곡을 지웠습니다"
NOTHING_REMOVED_MSG = "지울 곡이 없습니다"
RESUME_MSG = "이어 듣기: {time}부터"
RESUME_TAIL = 5.0

logger = logging.getLogger(__name__)


class PlayerController:
    def __init__(self, player, settings: Settings, rng=None, session_path=None, read_info=None) -> None:
        self._player = player
        self._settings = settings
        self._read_info = read_info or tags.read_info
        self._session_path = session_path
        self._info_cache: taginfo.TrackInfo | None = None
        self._cued = False
        self._resume_notice = ""
        self._held_position: float | None = None   # 이어 듣기 곡을 못 열었을 때 지켜 둘 위치
        self._radio = None
        self._return_position: float | None = None   # 라디오로 가기 전 곡의 위치: 곡 쪽 [재생] 때 돌아간다
        self.source = "file"                          # 지금 나오는 쪽: "file" 또는 "radio"
        self.playlist = Playlist(rng)
        self.playlist.set_shuffle(settings.shuffle)
        self.status = ""
        self.status_error = False
        self._apply_gain()
        self._player.set_effects(self.effects)

    @property
    def effects(self) -> FxSettings:
        return FxSettings.from_dict(self._settings.fx)

    def set_effects(self, fx: FxSettings, save: bool = True) -> None:
        self._player.set_effects(fx)
        if save:
            self._settings.fx = fx.to_dict()

    @property
    def state(self) -> State:
        return self._player.state

    @property
    def info(self) -> taginfo.TrackInfo | None:
        track = self.playlist.current
        if track is None:
            return None
        if self._info_cache is None or self._info_cache.path != track.path:
            self._info_cache = self._read_info(track.path)
        return self._info_cache

    def info_for(self, index: int) -> taginfo.TrackInfo:
        path = self.playlist.tracks[index].path
        if self._info_cache is not None and self._info_cache.path == path:
            return self._info_cache
        return self._read_info(path)

    @property
    def subtitle(self) -> str:
        if self.source == "radio":
            now = self._radio.now_title
            return "지금: " + now if now else ""
        return taginfo.subtitle(self.info)

    def notify(self, msg: str) -> None:
        self._info(msg)

    def attach_radio(self, radio) -> None:
        self._radio = radio

    def radio_notify(self, msg: str, error: bool = False) -> None:
        """RadioController의 notify: 라디오 안내는 모두 회색이다 (방송을 못 들어도 오류로 칠하지 않는다)."""
        self._info(msg)

    @property
    def radio_live(self) -> bool:
        return self._radio is not None and self._radio.state is not RadioState.IDLE

    def _remember_source(self) -> None:
        if self._radio is None:
            return
        self._settings.last_source = self.source
        current = self._radio.current
        self._settings.last_station = current.id if current is not None else ""

    def play_station(self, station_id: str) -> None:
        if self._radio is None or not self._radio.has_station(station_id):
            return   # 모르는 방송이면 곡을 끊지 않는다
        if self.source == "file":
            if self._player.has_track or self._held_position is not None:
                self._return_position = self._resume_position()
            self._player.unload()   # 실제 앱은 곡과 라디오가 한 플레이어를 쓴다: 두 소리가 겹치지 않게
        self._end_cue()
        self.source = "radio"
        self._radio.play(station_id)
        self._remember_source()

    def _leave_radio(self) -> None:
        """곡 쪽 동작이 시작되면 라디오를 끊고 곡 쪽으로 돌아온다."""
        if self.source != "radio":
            return
        self._radio.stop()
        self.source = "file"
        self._return_position = None
        self._remember_source()

    @property
    def cued(self) -> bool:
        return self._cued

    @property
    def can_seek(self) -> bool:
        if self.source == "radio":
            return False
        return self._player.state is not State.STOPPED or (self._cued and self._player.duration > 0)

    @property
    def position(self) -> float:
        return self._player.position

    @property
    def duration(self) -> float:
        return self._player.duration if len(self.playlist) else 0.0

    @property
    def volume(self) -> int:
        return self._settings.volume

    @property
    def muted(self) -> bool:
        return self._settings.muted

    @property
    def repeat(self) -> str:
        return self._settings.repeat

    @property
    def shuffle(self) -> bool:
        return self._settings.shuffle

    @property
    def _wrap(self) -> bool:
        return self._settings.repeat != "off"

    def _set_status(self, msg: str, error: bool = False) -> None:
        self.status = msg
        self.status_error = error

    def _info(self, msg: str) -> None:
        self._set_status(msg, False)

    def _error(self, msg: str) -> None:
        self._set_status(msg, True)

    def cycle_repeat(self) -> None:
        i = REPEAT_MODES.index(self._settings.repeat)
        self._settings.repeat = REPEAT_MODES[(i + 1) % len(REPEAT_MODES)]

    def toggle_shuffle(self) -> None:
        self._settings.shuffle = not self._settings.shuffle
        self.playlist.set_shuffle(self._settings.shuffle)

    @property
    def title(self) -> str:
        if self.source == "radio":
            station = self._radio.current
            return station.name if station is not None else ""
        current = self.playlist.current
        return current.title if current is not None else EMPTY_TITLE

    def _collect(self, paths: list[str]) -> tuple[list[str], str | None]:
        """음악 파일(폴더 펼침, 1단계 정렬) 뒤에 재생목록 파일의 곡(파일 순서)을 붙인다."""
        found = expand_paths([p for p in paths if not is_playlist(p)])
        error = None
        for p in paths:
            if not is_playlist(p):
                continue
            try:
                found.extend(read_playlist(p))
            except (OSError, ValueError):
                logger.warning("playlist read failed: %s", p, exc_info=True)
                error = error or LOAD_FAIL_MSG.format(name=os.path.basename(p))
        return found, error

    def open(self, paths: list[str]) -> None:
        self._set_status("")
        found, error = self._collect(paths)
        if not found:
            self._error(error or NO_FILES_MSG)
            return
        self._cued = False
        self._player.stop()
        self.playlist.replace(found)
        missing = self._mark_missing(0)
        self.play_index(self.playlist.index)
        self._report_load(error, missing)
        self._remember()

    def add(self, paths: list[str]) -> None:
        self._set_status("")
        found, error = self._collect(paths)
        if not found:
            self._error(error or NO_FILES_MSG)
            return
        # 대기 중이면 일시정지처럼, 라디오가 나오는 중이면 재생 중처럼 덧붙이기만 한다
        was_stopped = self._player.state is State.STOPPED and not self._cued and not self.radio_live
        start = len(self.playlist)
        first = self.playlist.add(found)
        missing = self._mark_missing(start)
        if was_stopped and first is not None:
            self.play_index(first)
        self._report_load(error, missing)
        self._remember(self._resume_position())

    def _mark_missing(self, start: int) -> int:
        count = 0
        for i in range(start, len(self.playlist)):
            if not os.path.exists(self.playlist.tracks[i].path):
                self.playlist.mark_missing(i)
                count += 1
        return count

    def _report_load(self, error: str | None, missing: int) -> None:
        if self.status:
            return
        if error:
            self._error(error)
        elif missing:
            self._info(MISSING_MSG.format(n=missing))

    def save_playlist(self, path: str) -> None:
        if os.path.splitext(path)[1].lower() not in PLAYLIST_EXTS:
            path += ".m3u8"
        name = os.path.basename(path)
        try:
            write_playlist(path, [t.path for t in self.playlist.tracks])
        except (OSError, ValueError):
            logger.warning("playlist save failed: %s", path, exc_info=True)
            self._error(SAVE_FAIL_MSG.format(name=name))
            return
        self._info(SAVED_MSG.format(name=name))

    def remove(self, rows: list[int]) -> None:
        on_radio = self.source == "radio"   # 라디오 중엔 플레이어가 방송을 틀고 있으니 건드리지 않는다
        was_playing = not on_radio and self._player.state is State.PLAYING
        result = self.playlist.remove(rows, wrap=self._wrap)
        if result != "kept":
            self._cued = False
            self._held_position = None
            self._return_position = None
            if not on_radio:
                self._player.stop()
                self._player.unload()
        if result == "next" and was_playing:
            self.play_index(self.playlist.index)
        if not len(self.playlist):
            self._set_status("")   # 목록 비우기와 같게
        self._remember(self._resume_position())

    def remove_duplicates(self) -> None:
        self._remove_auto(self.playlist.duplicate_indices(), DUP_MSG, NO_DUP_MSG)

    def remove_unplayable(self) -> None:
        self._remove_auto(self.playlist.unplayable_indices(), REMOVED_MSG, NOTHING_REMOVED_MSG)

    def _remove_auto(self, rows: list[int], done_msg: str, none_msg: str) -> None:
        self._set_status("")
        if not rows:
            self._info(none_msg)
            return
        self.remove(rows)
        if not self.status:
            self._info(done_msg.format(n=len(rows)))

    def sort(self, by: str) -> None:
        self.playlist.sort(by)
        self._remember(self._resume_position())

    def move(self, rows: list[int], before: int) -> list[int]:
        moved = self.playlist.move(rows, before)
        self._remember(self._resume_position())
        return moved

    def play_index(self, i: int) -> None:
        self._play_index(i)
        self._remember()

    def _play_index(self, i: int, start_at: float = 0.0) -> None:
        """i번 곡부터 열리는 곡을 튼다. start_at은 i번 곡이 열렸을 때만 재생 전에 그 자리로 간다."""
        first = i
        self._leave_radio()
        self._cued = False
        self._held_position = None
        self._set_status("")
        tried: set[int] = set()
        for _ in range(2 * len(self.playlist)):   # 한 바퀴 돌아 다시 만나는 곡도 있어 넉넉히
            self.playlist.set_current(i)
            if i not in tried:
                tried.add(i)
                track = self.playlist.tracks[i]
                try:
                    self._player.load(track.path)
                except DecodeError:
                    if os.path.exists(track.path):
                        self.playlist.mark_failed(i)
                    else:
                        self.playlist.mark_missing(i)
                    self._error(FAIL_MSG.format(name=os.path.basename(track.path)))
                else:
                    self.playlist.mark_ok(i)
                    if i == first and start_at > 0:
                        duration = self._player.duration
                        if not (duration > 0 and duration - start_at < RESUME_TAIL):
                            self._player.seek(start_at)   # 재생 전에 옮겨 0:00이 잠깐 들리지 않게
                    self._player.play()
                    return
            if len(tried) == len(self.playlist):
                break
            nxt = self.playlist.next_index(self._wrap)
            if nxt is None:
                break
            i = nxt
        self._player.stop()

    def toggle(self) -> None:
        if self.source == "radio":
            self._radio.toggle()
        else:
            self._toggle_file()

    @property
    def can_switch_source(self) -> bool:
        """작게 보기 [MP3로]/[라디오로]: 건너갈 쪽에 들을 것이 있는가."""
        if self.source == "radio":
            return len(self.playlist) > 0
        return self._radio is not None and self._switch_station() is not None

    def _switch_station(self) -> str | None:
        """[라디오로]가 들을 방송: 지금(마지막) 방송, 저장된 마지막 방송, 없으면 목록 맨 위."""
        current = self._radio.current
        if current is not None and self._radio.has_station(current.id):
            return current.id
        last = self._settings.last_station
        if last and self._radio.has_station(last):
            return last
        first = self._radio.first_station()
        return first.id if first is not None else None

    def switch_source(self) -> None:
        """작게 보기의 전환 단추. 목록이 없으니 누르면 바로 다른 쪽을 튼다."""
        if not self.can_switch_source:
            return
        if self.source == "radio":
            if self.playlist.index is None:
                self.playlist.set_current(0)
            self._toggle_file()   # 라디오를 끊고 듣던 곡 위치에서(없으면 처음부터)
        else:
            self.play_station(self._switch_station())

    def toggle_for_tab(self, tab: str) -> None:
        """재생목록 탭에서 [재생]: 라디오를 멈춰 두었으면 곡 쪽 [재생]으로 본다."""
        if tab == "playlist" and self.source == "radio" and not self.radio_live:
            self._toggle_file()
        else:
            self.toggle()

    def _toggle_file(self) -> None:
        returning = self._return_position
        unloaded = not self._player.has_track or getattr(self._player, "is_live", False)
        if returning is not None and unloaded and self.playlist.index is not None:
            # 라디오로 가기 전 곡으로 돌아간다: 다시 열고 그 위치에서 이어 간다
            self._play_index(self.playlist.index, start_at=returning)
            self._remember(self._resume_position())
            return
        self._leave_radio()
        state = self._player.state
        if state is State.PLAYING:
            self._player.pause()
        elif state is State.PAUSED:
            self._player.play()
        elif self._cued:
            self._cued = False
            self._player.play()
        elif self.playlist.index is not None:
            self.play_index(self.playlist.index)

    def stop(self) -> None:
        if self.source == "radio":
            self._radio.stop()   # 연결을 끊고 들은 시간을 0으로; 방송국 선택은 남는다
            return
        self._end_cue()
        self._player.stop()

    def _end_cue(self) -> None:
        """대기(불러와 자리 잡고 아직 시작 안 함)를 끝낸다. 이어 듣기 안내가 그대로면 지운다."""
        if self._cued:
            self._cued = False
            self._drop_resume_notice()

    def _drop_resume_notice(self) -> None:
        if self._resume_notice and self.status == self._resume_notice:
            self._set_status("")
        self._resume_notice = ""

    def next(self) -> None:
        if self.source == "radio":
            self._radio.step(1)
            return
        nxt = self.playlist.next_index(self._wrap)
        if nxt is None:
            self._end_cue()
            self._player.stop()
        else:
            self.play_index(nxt)

    def prev(self) -> None:
        if self.source == "radio":
            self._radio.step(-1)
            return
        if self.playlist.index is None:
            return
        _, target = self.playlist.prev_target(self._player.position, self._wrap)
        self.play_index(target)

    def on_track_end(self) -> None:
        if self.source == "radio" or self._player.state is not State.STOPPED:
            return
        if self._settings.repeat == "one" and self.playlist.index is not None:
            self.play_index(self.playlist.index)
        else:
            self.next()

    def seek_by(self, direction: int) -> None:
        if not self.can_seek:
            return
        if self._cued:
            self._drop_resume_notice()
        target = max(0.0, self._player.position + direction * self._settings.seek_step)
        duration = self._player.duration
        if duration > 0 and target >= duration:
            self.next()
        else:
            self._player.seek(target)

    def seek_to(self, sec: float) -> None:
        if not self.can_seek:
            return
        if self._cued:
            self._drop_resume_notice()
        self._player.seek(min(max(sec, 0.0), self._player.duration))

    def set_volume(self, v: int) -> None:
        self._settings.volume = v
        self._apply_gain()

    def toggle_mute(self) -> None:
        self._settings.muted = not self._settings.muted
        self._apply_gain()

    def clear(self) -> None:
        self._cued = False
        self._held_position = None
        self._return_position = None
        if self.source != "radio":   # 라디오 중엔 방송을 끊지 않는다
            self._player.stop()
            self._player.unload()
        self.playlist.clear()
        self._set_status("")
        self._remember()

    def _resume_position(self) -> float:
        if self.source == "radio" and self._return_position is not None:
            return self._return_position
        if self._held_position is not None:
            return self._held_position
        if self.source == "radio":   # 플레이어는 방송을 틀고 있다: 그 위치는 곡의 것이 아니다
            return 0.0
        if self._player.state is State.STOPPED and not self._cued:
            return 0.0
        return self._player.position

    def _remember(self, position: float = 0.0) -> None:
        if not self._session_path:
            return
        if not len(self.playlist):
            try:
                os.remove(self._session_path)
            except OSError:
                pass
            self._settings.last_track = ""
            self._settings.last_position = 0.0
            return
        try:
            write_playlist(self._session_path, [t.path for t in self.playlist.tracks])
        except (OSError, ValueError):
            logger.warning("session save failed: %s", self._session_path, exc_info=True)
        current = self.playlist.current
        self._settings.last_track = current.path if current is not None else ""
        self._settings.last_position = position

    def save_session(self) -> None:
        self._remember_source()
        if self.source == "radio" and self._return_position is None:
            # 돌아갈 곡 위치가 없으면(라디오로 갈 때 열린 곡이 없었다) 저장된 위치를 그대로 둔다.
            # 정렬·옮기기는 이때 0을 쓰지만, 곡이 열려 있지 않았으니 잃는 위치는 없다.
            self._remember(self._settings.last_position)
        else:
            self._remember(self._resume_position())

    def restore_session(self) -> None:
        if self._restore_radio():
            return
        restored = self._restore_list()
        if restored is None:
            return
        i, position = restored
        path = self.playlist.tracks[i].path
        try:
            self._player.load(path)
        except DecodeError:
            if os.path.exists(path):
                self.playlist.mark_failed(i)
            else:
                self.playlist.mark_missing(i)
            self._held_position = position   # USB를 뺀 채 켰다 꺼도 저장된 자리를 잃지 않게
            return
        self.playlist.mark_ok(i)
        duration = self._player.duration
        if duration > 0 and duration - position < RESUME_TAIL:
            position = 0.0
        if position > 0:
            self._player.seek(position)
            self._resume_notice = RESUME_MSG.format(time=format_time(position))
            self._info(self._resume_notice)
        self._cued = True

    def _restore_radio(self) -> bool:
        """라디오로 끈 경우: 목록과 지난 곡만 고르고(곡은 열지 않음) 방송국을 고른 채 접속하지 않는다."""
        if self._radio is None or self._settings.last_source != "radio":
            return False
        want = self._settings.last_station
        self._radio.cue(want)
        station = self._radio.current
        if station is None or station.id != want:
            return False
        restored = self._restore_list()
        self._return_position = restored[1] if restored is not None else None
        self.source = "radio"
        self._info(RESUME_RADIO_MSG.format(name=station.name))
        return True

    def _restore_list(self) -> tuple[int, float] | None:
        """저장된 목록을 불러와 지난 곡을 고른다. (줄, 이어 들을 위치)를 돌려준다."""
        if not self._session_path or not os.path.isfile(self._session_path):
            return None
        try:
            paths = read_playlist(self._session_path)
        except (OSError, ValueError):
            logger.warning("session read failed: %s", self._session_path, exc_info=True)
            return None
        if not paths:
            return None
        self.playlist.replace(paths)
        self._mark_missing(0)
        position = self._settings.last_position
        i = self.playlist.index
        want = self._settings.last_track
        if want:
            key = os.path.normcase(os.path.abspath(want))
            for row, track in enumerate(self.playlist.tracks):
                if os.path.normcase(os.path.abspath(track.path)) == key:
                    i = row
                    break
            else:
                position = 0.0
        else:
            position = 0.0
        self.playlist.set_current(i)
        self.playlist.set_shuffle(self.shuffle)
        return i, position

    def on_player_error(self, msg: str) -> None:
        self._error(msg)

    def _apply_gain(self) -> None:
        gain = 0.0 if self._settings.muted else (self._settings.volume / 100) ** 2
        self._player.set_gain(gain)
