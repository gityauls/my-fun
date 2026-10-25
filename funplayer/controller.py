from __future__ import annotations

import logging
import os

from funplayer.core.m3u import PLAYLIST_EXTS, is_playlist, read_playlist, write_playlist
from funplayer.core.playlist import Playlist
from funplayer.core.settings import REPEAT_MODES, Settings
from funplayer.core.tracks import expand_paths
from funplayer.engine.decoder import DecodeError
from funplayer.engine.player import State

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

logger = logging.getLogger(__name__)


class PlayerController:
    def __init__(self, player, settings: Settings, rng=None) -> None:
        self._player = player
        self._settings = settings
        self.playlist = Playlist(rng)
        self.playlist.set_shuffle(settings.shuffle)
        self.status = ""
        self.status_error = False
        self._apply_gain()

    @property
    def state(self) -> State:
        return self._player.state

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
            except OSError:
                logger.warning("playlist read failed: %s", p, exc_info=True)
                error = error or LOAD_FAIL_MSG.format(name=os.path.basename(p))
        return found, error

    def open(self, paths: list[str]) -> None:
        self._set_status("")
        found, error = self._collect(paths)
        if not found:
            self._error(error or NO_FILES_MSG)
            return
        self._player.stop()
        self.playlist.replace(found)
        missing = self._mark_missing(0)
        self.play_index(self.playlist.index)
        self._report_load(error, missing)

    def add(self, paths: list[str]) -> None:
        self._set_status("")
        found, error = self._collect(paths)
        if not found:
            self._error(error or NO_FILES_MSG)
            return
        was_stopped = self._player.state is State.STOPPED
        start = len(self.playlist)
        first = self.playlist.add(found)
        missing = self._mark_missing(start)
        if was_stopped and first is not None:
            self.play_index(first)
        self._report_load(error, missing)

    def _mark_missing(self, start: int) -> int:
        count = 0
        for i in range(start, len(self.playlist)):
            if not os.path.exists(self.playlist.tracks[i].path):
                self.playlist.mark_failed(i)
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
        except OSError:
            logger.warning("playlist save failed: %s", path, exc_info=True)
            self._error(SAVE_FAIL_MSG.format(name=name))
            return
        self._info(SAVED_MSG.format(name=name))

    def remove(self, rows: list[int]) -> None:
        was_playing = self._player.state is State.PLAYING
        result = self.playlist.remove(rows, wrap=self._wrap)
        if result != "kept":
            self._player.stop()
            self._player.unload()
        if result == "next" and was_playing:
            self.play_index(self.playlist.index)

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

    def move(self, rows: list[int], before: int) -> list[int]:
        return self.playlist.move(rows, before)

    def play_index(self, i: int) -> None:
        self._set_status("")
        for _ in range(len(self.playlist)):
            self.playlist.set_current(i)
            track = self.playlist.tracks[i]
            try:
                self._player.load(track.path)
            except DecodeError:
                self.playlist.mark_failed(i)
                self._error(FAIL_MSG.format(name=os.path.basename(track.path)))
                nxt = self.playlist.next_index(self._wrap)
                if nxt is None:
                    break
                i = nxt
                continue
            self._player.play()
            return
        self._player.stop()

    def toggle(self) -> None:
        state = self._player.state
        if state is State.PLAYING:
            self._player.pause()
        elif state is State.PAUSED:
            self._player.play()
        elif self.playlist.index is not None:
            self.play_index(self.playlist.index)

    def stop(self) -> None:
        self._player.stop()

    def next(self) -> None:
        nxt = self.playlist.next_index(self._wrap)
        if nxt is None:
            self._player.stop()
        else:
            self.play_index(nxt)

    def prev(self) -> None:
        if self.playlist.index is None:
            return
        _, target = self.playlist.prev_target(self._player.position, self._wrap)
        self.play_index(target)

    def on_track_end(self) -> None:
        if self._player.state is not State.STOPPED:
            return
        if self._settings.repeat == "one" and self.playlist.index is not None:
            self.play_index(self.playlist.index)
        else:
            self.next()

    def seek_by(self, direction: int) -> None:
        if self._player.state is State.STOPPED:
            return
        target = max(0.0, self._player.position + direction * self._settings.seek_step)
        duration = self._player.duration
        if duration > 0 and target >= duration:
            self.next()
        else:
            self._player.seek(target)

    def seek_to(self, sec: float) -> None:
        if self._player.state is State.STOPPED:
            return
        self._player.seek(min(max(sec, 0.0), self._player.duration))

    def set_volume(self, v: int) -> None:
        self._settings.volume = v
        self._apply_gain()

    def toggle_mute(self) -> None:
        self._settings.muted = not self._settings.muted
        self._apply_gain()

    def clear(self) -> None:
        self._player.stop()
        self._player.unload()
        self.playlist.clear()
        self._set_status("")

    def on_player_error(self, msg: str) -> None:
        self._error(msg)

    def _apply_gain(self) -> None:
        gain = 0.0 if self._settings.muted else (self._settings.volume / 100) ** 2
        self._player.set_gain(gain)
