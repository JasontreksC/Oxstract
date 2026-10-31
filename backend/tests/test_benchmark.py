from pathlib import Path

import pytest

from app import media
from scripts.benchmark import SCENE_BOX, make_test_video, scene_state


def test_scene_rests_moves_leaves_and_comes_back() -> None:
    assert scene_state(1)[0] == SCENE_BOX[0]
    assert scene_state(6)[0] > SCENE_BOX[0]  # moving
    assert scene_state(10)[1] > 0  # spinning
    assert scene_state(16)[0] > 1920  # out of the frame
    assert scene_state(21)[0] == SCENE_BOX[0]  # back
    assert scene_state(31) == scene_state(1)  # loops


def test_test_video_has_the_asked_length_and_sound(tmp_path: Path) -> None:
    path = tmp_path / "bench.mp4"

    make_test_video(path, 2.0, media.ffmpeg_bin(), size=(320, 180))

    info = media.probe(path)
    assert info.duration == pytest.approx(2.0, abs=0.1)
    assert (info.width, info.height) == (320, 180)
    assert info.has_audio
