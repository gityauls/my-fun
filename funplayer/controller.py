from __future__ import annotations

import os

from funplayer.core.playlist import Playlist
from funplayer.core.settings import Settings
from funplayer.core.tracks import expand_paths
from funplayer.engine.decoder import DecodeError
from funplayer.engine.player import State

EMPTY_TITLE = "곡을 추가하세요"
NO_FILES_MSG = "재생할 수 있는 파일이 없습니다"
FAIL_MSG = "열 수 없음: {name}"


class PlayerController:
    def __init__(self, player, settings: Settings) -> None:
        self._player = player
        self._settings = settings
        self.playlist = Playlist()
        self.status = ""
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
    def title(self) -> str:
        current = self.playlist.current
        return current.title if current is not None else EMPTY_TITLE

    def open(self, paths: list[str]) -> None:
        found = expand_paths(paths)
        if not found:
            self.status = NO_FILES_MSG
            return
        self._player.stop()
        self.playlist.replace(found)
        self.play_index(0)

    def add(self, paths: list[str]) -> None:
        found = expand_paths(paths)
        if not found:
            self.status = NO_FILES_MSG
            return
        was_stopped = self._player.state is State.STOPPED
        first = self.playlist.add(found)
        if was_stopped and first is not None:
            self.play_index(first)

    def play_index(self, i: int) -> None:
        self.status = ""
        for _ in range(len(self.playlist)):
            self.playlist.set_current(i)
            track = self.playlist.tracks[i]
            try:
                self._player.load(track.path)
            except DecodeError:
                self.playlist.mark_failed(i)
                self.status = FAIL_MSG.format(name=os.path.basename(track.path))
                nxt = self.playlist.next_index()
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
        nxt = self.playlist.next_index()
        if nxt is None:
            self._player.stop()
        else:
            self.play_index(nxt)

    def prev(self) -> None:
        if self.playlist.index is None:
            return
        _, target = self.playlist.prev_target(self._player.position)
        self.play_index(target)

    def on_track_end(self) -> None:
        if self._player.state is not State.STOPPED:
            return
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
        self.status = ""

    def on_player_error(self, msg: str) -> None:
        self.status = msg

    def _apply_gain(self) -> None:
        gain = 0.0 if self._settings.muted else (self._settings.volume / 100) ** 2
        self._player.set_gain(gain)
