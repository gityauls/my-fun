from __future__ import annotations

import pytest

from funplayer.core.tagguess import clean_search_title, guess_from_filename


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


@pytest.mark.parametrize("raw, expected", [
    ("02. I Miss You.mp3", "I Miss You"),
    ("I Miss You", "I Miss You"),
    ("7 - 그대향기", "그대향기"),
    ("1999", "1999"),
    ("", ""),
])
def test_clean_search_title(raw, expected):
    assert clean_search_title(raw) == expected
