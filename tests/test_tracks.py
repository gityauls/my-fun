from funplayer.core.tracks import SUPPORTED_EXTS, expand_paths, natural_key

def touch(p):
    p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"")

def test_supported_exts():
    assert SUPPORTED_EXTS == {".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wma"}

def test_natural_key():
    names = ["10.mp3", "2.mp3", "track 20.mp3", "1.mp3", "Track 3.mp3"]
    assert sorted(names, key=natural_key) == ["1.mp3", "2.mp3", "10.mp3", "Track 3.mp3", "track 20.mp3"]

def test_folder_recursive_filtered_sorted(tmp_path):
    a = tmp_path / "a"
    for rel in ["10.mp3", "2.MP3", "notes.txt", "cover.jpg", "sub/1.flac", "b/3.ogg"]:
        touch(a / rel)
    assert expand_paths([str(a)]) == [str(a / "2.MP3"), str(a / "10.mp3"),
                                      str(a / "b" / "3.ogg"), str(a / "sub" / "1.flac")]

def test_files_and_folders_share_one_order(tmp_path):
    touch(tmp_path / "z" / "1.mp3"); touch(tmp_path / "a" / "9.mp3")
    got = expand_paths([str(tmp_path / "z"), str(tmp_path / "a" / "9.mp3")])
    assert got == [str(tmp_path / "a" / "9.mp3"), str(tmp_path / "z" / "1.mp3")]

def test_duplicates_kept(tmp_path):
    f = tmp_path / "x.wav"; touch(f)
    assert expand_paths([str(f), str(f)]) == [str(f), str(f)]

def test_missing_and_unsupported_skipped(tmp_path):
    touch(tmp_path / "readme.txt")
    assert expand_paths([str(tmp_path / "nope.mp3"), str(tmp_path / "readme.txt")]) == []
