from funplayer.core.bulktag import (
    BY_KNOWN, BY_TAG, MULTI, NO_ARTIST, SURE, UNSURE, canon, clean_artist, merge_artist, split_alias, tidy_names,
)


def tidy(stems, tags=None):
    return [(t.artist, t.title, t.how) for t in tidy_names(stems, tags or [""] * len(stems))]


def test_tidy_user_shapes():
    got = tidy(["멜로망스 - 선물", "[015B] 텅빈 거리에서", "[Ami]천상천하", "사랑인가봐-멜로망스",
                "벚꽃엔딩-버스커버스커", "(홍대클럽)Benny Benassi - I Love My Sex(노래진짜좋음) - 클럽음악",
                "[As_ One]02.그녀의 게임"])
    assert got == [("멜로망스", "선물", SURE), ("015B", "텅빈 거리에서", SURE), ("Ami", "천상천하", SURE),
                   ("멜로망스", "사랑인가봐", SURE), ("버스커버스커", "벚꽃엔딩", UNSURE),
                   ("Benny Benassi", "I Love My Sex", MULTI), ("As One", "그녀의 게임", SURE)]


def test_tidy_reversed_spaced_fixed_by_known_artist():
    got = tidy(["As One - Day By Day", "02.그녀의 게임 - As One"])
    assert got[1] == ("As One", "그녀의 게임", BY_KNOWN)


def test_tidy_uses_existing_artist_tag():
    assert tidy(["As One-Day By Day"], ["As One"]) == [("As One", "Day By Day", BY_TAG)]
    assert tidy(["Day By Day-As One"], ["As One"]) == [("As One", "Day By Day", SURE)]


def test_tidy_single_name_uses_tag_or_asks():
    assert tidy(["그냥제목"], ["가수"]) == [("가수", "그냥제목", SURE)]
    assert tidy(["01. 그냥제목"]) == [("", "그냥제목", NO_ARTIST)]
    assert tidy(["2002년의 겨울"], ["가수"]) == [("가수", "2002년의 겨울", SURE)]


def test_tidy_leading_number_never_becomes_track():
    t = tidy_names(["03. 서지원 - I Miss You"], [""])[0]
    assert (t.artist, t.title) == ("서지원", "I Miss You")


# ---- 가수 이름 겹침 / 같은 가수 표기 통일 ----
def test_alias_helpers():
    assert split_alias("이승철(Lee Seung Chul)") == ("이승철", "Lee Seung Chul")
    assert split_alias("Lee Seung Chul(이승철)") == ("이승철", "Lee Seung Chul")
    assert split_alias("Song(Live)") == ("Song(Live)", "")      # 같은 글자끼리는 별칭이 아님
    assert canon("Lee Seung Chul (이승철)") == "이승철(Lee Seung Chul)"
    assert clean_artist("02.이승철 (Lee Seung Chul)") == "이승철(Lee Seung Chul)"
    assert clean_artist("(홍대클럽)Benny Benassi") == "Benny Benassi"


def test_merge_artist():
    assert merge_artist("이승철,이승철") == "이승철"
    assert merge_artist("이승철, 이승철 / 이승철") == "이승철"
    assert merge_artist("A, B, a") == "A, B"
    assert merge_artist("A, B") == "A, B"           # 겹치지 않으면 그대로
    assert merge_artist("") == ""
    assert merge_artist("Lee Seung Chul, 이승철(Lee Seung Chul)") == "이승철(Lee Seung Chul)"


def test_tidy_merges_doubled_artist_from_tag_and_name():
    t = tidy_names(["제목만"], ["이승철,이승철"])[0]
    assert (t.artist, t.title, t.merged) == ("이승철", "제목만", True) and "하나로" in t.note
    t2 = tidy_names(["이승철,이승철 - 희야"], [""])[0]
    assert (t2.artist, t2.title, t2.merged) == ("이승철", "희야", True)
    t3 = tidy_names(["이승철 - 희야"], ["이승철"])[0]
    assert not t3.merged and t3.note == ""


def test_same_artist_unified_to_best_form():
    got = tidy_names(["이승철(Lee Seung Chul) - 희야", "이승철 - 소리쳐", "Lee Seung Chul - 그사람",
                      "Lee Seung Chul(이승철) - 방황"], [""] * 4)
    assert [t.artist for t in got] == ["이승철(Lee Seung Chul)"] * 4
    assert got[0].note == "" and "통일" in got[1].note and "통일" in got[2].note


def test_hangul_beats_english_only_when_linked():
    # 한글과 영어 표기를 이어 줄 '한글(영어)'가 없으면 같은 가수인지 알 수 없어 그대로 둔다
    got = tidy_names(["이승철 - 희야", "Lee Seung Chul - 그사람"], ["", ""])
    assert [t.artist for t in got] == ["이승철", "Lee Seung Chul"]
    # 기존 태그가 이어 주면 맞춘다
    got = tidy_names(["Lee Seung Chul - 그사람"], ["이승철(Lee Seung Chul)"])
    assert got[0].artist == "이승철(Lee Seung Chul)"


def test_alias_artist_keeps_parens_but_title_drops_noise():
    t = tidy_names(["아이유(IU) - 좋은 날(Live)"], [""])[0]
    assert (t.artist, t.title) == ("아이유(IU)", "좋은 날")


def test_tag_spelling_preferred_and_mismatch_asks():
    from funplayer.core.bulktag import MISMATCH
    got = tidy_names(["[As_One]너만은모르길", "(You Drive Me) Crazy - Britney Spears", "[22]그대눈물까지도",
                      "[chuck]별땅"],
                     ["애즈원(As One)", "Britney Spears", "투투", "Chuck"],
                     ["너만은 모르길", "(You Drive Me) Crazy", "그대눈물까지도", "별땅"])
    assert (got[0].artist, got[0].title) == ("애즈원(As One)", "너만은 모르길")
    assert (got[1].artist, got[1].title) == ("Britney Spears", "(You Drive Me) Crazy")
    assert got[2].how == MISMATCH and got[2].unsure and "투투" in got[2].note
    assert got[3].artist == "Chuck" and got[3].note == ""


def test_many_hyphens_find_artist_piece_and_ask():
    names = ["김건모 - 잘못된 만남 - Remix", "Remix - 김건모 - 잘못된 만남", "김건모-잘못된 만남 - 1995",
             "잘못된 만남-김건모-1995", "김건모 - 핑계"]
    got = tidy(names)
    assert got[:4] == [("김건모", "잘못된 만남", MULTI)] * 4
    assert got[4] == ("김건모", "핑계", SURE)


def test_hyphen_inside_name_kept():
    assert tidy(["Jay-Z - Empire State"]) == [("Jay-Z", "Empire State", SURE)]
    got = tidy(["김건모 - 잘못된 만남-리믹스", "김건모 - 핑계"])
    assert got[0] == ("김건모", "잘못된 만남-리믹스", SURE)
    assert tidy(["김건모 - 잘못된 만남-리믹스"])[0][2] == MULTI      # 실마리가 없으면 확인

def test_wrong_tag_on_tail_piece_ignored():
    t = tidy_names(["(홍대클럽)Benny Benassi - I Love My Sex(노래진짜좋음) - 클럽음악"], ["클럽음악"])[0]
    assert (t.artist, t.how) == ("Benny Benassi", MULTI)
    t2 = tidy_names(["Remix - 김건모 - 잘못된 만남"], ["김건모"])[0]
    assert (t2.artist, t2.title) == ("김건모", "잘못된 만남")
