import os, shutil
import numpy as np
import pytest
from funplayer.engine.decoder import SAMPLE_RATE, DecodeError, open_decoder

def drain(dec):
    total = 0
    while (b := dec.read()) is not None:
        assert b.dtype == np.float32 and b.ndim == 2 and b.shape[1] == 2
        total += len(b)
    return total

def test_duration(tone_wav):
    assert abs(open_decoder(tone_wav).duration - 3.0) < 0.05

def test_blocks_total_and_end(tone_wav):
    dec = open_decoder(tone_wav)
    assert abs(drain(dec) - 3 * SAMPLE_RATE) < 0.01 * 3 * SAMPLE_RATE
    assert dec.read() is None and dec.read() is None

def test_mono48k_resampled_to_stereo_44k(mono48k_wav):
    dec = open_decoder(mono48k_wav)
    first = dec.read()
    assert np.allclose(first[:, 0], first[:, 1])
    assert abs(len(first) + drain(dec) - 3 * SAMPLE_RATE) < 0.01 * 3 * SAMPLE_RATE

def test_seek_accuracy(tone_wav):
    dec = open_decoder(tone_wav); dec.seek(1.5)
    assert abs(dec.read()[0, 1] / 0.3 - 1.5) < 0.05

def test_seek_back_after_end(tone_wav):
    dec = open_decoder(tone_wav); drain(dec); dec.seek(0)
    assert dec.read()[0, 1] / 0.3 < 0.05

def test_mp3_seek_accuracy(tone_mp3):
    full = drain(open_decoder(tone_mp3))
    dec = open_decoder(tone_mp3); dec.seek(1.5)
    assert abs((full - drain(dec)) / SAMPLE_RATE - 1.5) < 0.05

@pytest.mark.parametrize("name", ["broken_mp3", "empty_wav"])
def test_bad_files_raise(name, request):
    with pytest.raises(DecodeError):
        open_decoder(request.getfixturevalue(name))

def test_missing_file_raises(tmp_path):
    with pytest.raises(DecodeError):
        open_decoder(str(tmp_path / "none.mp3"))

def test_short_file(short_wav):
    assert abs(drain(open_decoder(short_wav)) - 882) <= 2

def test_korean_path(tone_wav, tmp_path):
    dst = tmp_path / "한글 폴더" / "봄 노래 01.wav"; dst.parent.mkdir()
    shutil.copy(tone_wav, dst)
    assert abs(open_decoder(str(dst)).duration - 3.0) < 0.05

def test_close_releases_file(tone_wav, tmp_path):
    dst = tmp_path / "x.wav"; shutil.copy(tone_wav, dst)
    dec = open_decoder(str(dst)); dec.read(); dec.close()
    os.remove(dst)
