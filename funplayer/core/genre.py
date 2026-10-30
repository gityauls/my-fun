from __future__ import annotations

# 위에서부터 보며 낱말이 들어 있으면 그 프리셋이다(먼저 맞는 것)
_GENRE_TABLE: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("알앤비", ("r&b", "rnb", "r & b", "rhythm and blues", "알앤비", "soul", "소울",
              "urban", "어반", "funk")),
    ("힙합", ("hip", "rap", "랩", "힙합", "trap")),
    ("일렉트로닉", ("electro", "edm", "house", "techno", "trance", "일렉", "하우스")),
    ("댄스", ("dance", "댄스", "disco", "디스코", "라틴", "latin")),
    ("발라드", ("ballad", "발라드")),
    ("록", ("rock", "락", "록", "metal", "메탈", "punk", "grunge")),
    ("재즈", ("jazz", "재즈", "swing")),
    ("블루스", ("blues", "블루스")),
    ("클래식", ("classic", "클래식", "orchestra", "symphony", "opera", "영화음악",
              "soundtrack")),
    ("트로트", ("trot", "트로트", "성인가요")),
    ("어쿠스틱", ("acoustic", "어쿠스틱", "folk", "포크", "country", "컨트리", "피아노",
               "piano")),
    ("라운지", ("lounge", "라운지", "chill", "칠아웃", "lo-fi", "lofi", "ambient", "앰비언트",
              "new age", "뉴에이지", "bossa", "보사노바")),
    ("라이브", ("live", "라이브")),
    ("보컬", ("vocal", "보컬")),
    ("팝", ("pop", "팝", "가요", "80년대")),
)

# ID3v1 번호 중 쓰는 것만
_ID3V1 = {
    0: "Blues", 1: "Classic Rock", 2: "Country", 3: "Dance", 7: "Hip-Hop", 8: "Jazz",
    9: "Metal", 13: "Pop", 14: "R&B", 15: "Rap", 17: "Rock", 18: "Techno", 26: "Ambient",
    32: "Classical", 52: "Electronic",
}


def preset_for_genre(text: str) -> str | None:
    if not isinstance(text, str):
        return None
    s = text.strip().lower()
    if not s:
        return None
    digits = s[1:-1].strip() if s.startswith("(") and s.endswith(")") else s
    if digits.isascii() and digits.isdigit():
        name = _ID3V1.get(int(digits))
        if name is None:
            return None
        s = name.lower()
    for preset, words in _GENRE_TABLE:
        if any(w in s for w in words):
            return preset
    return None
