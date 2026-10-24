import pytest
from funplayer.core.timefmt import format_time

@pytest.mark.parametrize("sec,text", [(0, "0:00"), (5.9, "0:05"), (72, "1:12"), (3599, "59:59"),
                                      (3723, "1:02:03"), (-1, "0:00"), (float("nan"), "0:00")])
def test_format_time(sec, text):
    assert format_time(sec) == text
