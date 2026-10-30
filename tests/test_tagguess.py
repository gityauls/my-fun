from __future__ import annotations

import pytest

from funplayer.core.tagguess import guess_from_filename


@pytest.mark.parametrize("path, expected", [
    ("[서지원] I Miss You.mp3", ("서지원", "I Miss You")),
    ("(홍대클럽)Benny Benassi - I Love My Sex(노래진짜좋음) - 클럽음악.mp3", ("Benny Benassi", "I Love My Sex")),
    ("가수 - 제목.mp3", ("가수", "제목")),
    ("그냥제목.mp3", ("", "그냥제목")),
    ("", ("", "")),
    (r"C:\music\_가수_ - _제목_.mp3", ("가수", "제목")),
])
def test_guess(path, expected):
    assert guess_from_filename(path) == expected
