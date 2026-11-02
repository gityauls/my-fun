import pytest

from funplayer.core.bulktag import (
    AUTO, PatternError, compile_pattern, from_filename, from_lines, guess_auto, match_pattern, merge, track_numbers,
)


@pytest.mark.parametrize("name, want", [
    ("[As_One]너만은모르길.mp3", {"artist": "As One", "title": "너만은모르길"}),
    ("[As_ One]02.그녀의 게임.mp3", {"artist": "As One", "title": "그녀의 게임", "track": "2"}),
    ("[015B] 텅빈 거리에서.mp3", {"artist": "015B", "title": "텅빈 거리에서"}),
    ("DJDOC - remember.mp3", {"artist": "DJDOC", "title": "remember"}),
    ("(홍대클럽)Benny Benassi - I Love My Sex(노래진짜좋음) - 클럽음악.mp3",
     {"artist": "Benny Benassi", "title": "I Love My Sex"}),
    ("03. 서지원 - I Miss You.mp3", {"artist": "서지원", "title": "I Miss You", "track": "3"}),
    ("멜로망스 - 선물.mp3", {"artist": "멜로망스", "title": "선물"}),
    ("그냥제목.mp3", {"title": "그냥제목"}),
    ("2002년의 겨울.mp3", {"title": "2002년의 겨울"}),
])
def test_auto_guess(name, want):
    assert from_filename("C:/m/" + name) == want


def test_underscores_kept_when_off():
    assert from_filename("C:/m/[As_One]x.mp3", underscores=False)["artist"] == "As_One"


@pytest.mark.parametrize("pattern, stem, want", [
    ("%가수% - %제목%", "DJDOC - remember", {"artist": "DJDOC", "title": "remember"}),
    ("[%가수%]%트랙%.%제목%", "[As One]05.Day By Day", {"artist": "As One", "track": "5", "title": "Day By Day"}),
    ("%트랙%. %제목%", "07.노래", {"track": "7", "title": "노래"}),
    ("%track% %artist% - %title%", "01 A - B", {"track": "1", "artist": "A", "title": "B"}),
    ("%가수% - %제목%", "맞지않음", {}),
])
def test_patterns(pattern, stem, want):
    assert match_pattern(stem, pattern) == want


def test_bad_patterns():
    with pytest.raises(PatternError):
        compile_pattern("%모름%")
    with pytest.raises(PatternError):
        compile_pattern("그냥 글자")


def test_from_lines_auto_and_pattern():
    text = "1. Day By Day\n\n2. 그녀의 게임\n 3 너만은 모르길 \n"
    assert from_lines(text) == [{"track": "1", "title": "Day By Day"}, {"track": "2", "title": "그녀의 게임"},
                                {"track": "3", "title": "너만은 모르길"}]
    assert from_lines("A - x\nzz", "%가수% - %제목%") == [{"artist": "A", "title": "x"}, {}]
    assert from_lines("제목만", AUTO) == [{"title": "제목만"}]


def test_track_numbers_and_merge():
    assert track_numbers(3) == ["1", "2", "3"]
    assert track_numbers(2, start=5, with_total=True) == ["5/6", "6/6"]
    base = {"artist": "", "title": "옛", "album": "A"}
    assert merge(base, {"artist": "새", "title": "새제목"}) == {"artist": "새", "title": "새제목", "album": "A"}
    assert merge(base, {"artist": "새", "title": "새제목"}, only_empty=True)["title"] == "옛"


def test_guess_keeps_number_only_title():
    assert guess_auto("1999") == {"title": "1999"}
