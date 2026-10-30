import pytest

from funplayer.core.genre import preset_for_genre


@pytest.mark.parametrize("text, expected", [
    ("Ballad", "발라드"), ("ROCK", "록"), ("Classic Rock", "록"), ("Classical", "클래식"),
    ("Rhythm and Blues", "알앤비"), ("Blues", "블루스"), ("알앤비/어반", "알앤비"),
    ("R&B", "알앤비"), ("Hip-Hop", "힙합"), ("K-Pop", "팝"), ("Lo-fi", "라운지"),
    ("재즈", "재즈"), ("(17)", "록"), ("17", "록"), ("32", "클래식"),
    ("레게", None), ("", None), ("  ", None),
])
def test_genre_table_cases(text, expected):
    assert preset_for_genre(text) == expected
