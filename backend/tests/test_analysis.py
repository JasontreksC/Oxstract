"""Analysis on synthetic clips with known motion (OpenCV only, no FFmpeg)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from synthetic import BOX, FPS, HEIGHT, SECONDS, START, WIDTH, make_clip

from app.analysis import analyze
from app.media import Canceled


def _run(path: Path, target_index: int = 15, on_progress=lambda fraction: True) -> dict:
    return analyze(
        str(path),
        fps=FPS,
        frame_count=FPS * SECONDS,
        target_index=target_index,
        target_box=BOX,
        source_size=(WIDTH, HEIGHT),
        class_name=None,
        detector=None,
        on_progress=on_progress,
    )


def _windows(result: dict, key: str) -> tuple[np.ndarray, np.ndarray]:
    """(at rest, in motion) values. Motion runs from 1 s to 2 s in every clip."""

    samples = result["samples"]
    t = np.array(samples["t"])
    values = np.array(samples[key], dtype=float)
    rest = (t < 0.95) | (t > 2.05)
    active = (t > 1.05) & (t < 1.95)
    return values[rest], values[active]


@pytest.fixture(scope="module")
def clips(tmp_path_factory) -> dict[str, dict]:
    folder = tmp_path_factory.mktemp("synthetic")
    return {
        motion: _run(make_clip(folder / f"{motion}.mp4", motion))
        for motion in ("still", "move", "spin", "pan")
    }


def test_samples_cover_the_clip_at_ten_per_second(clips) -> None:
    samples = clips["still"]["samples"]
    assert len(samples["t"]) == FPS * SECONDS // 3
    assert samples["t"] == sorted(samples["t"])
    assert all(samples["visible"])
    assert clips["still"]["sample_fps"] == 10


def test_still_object_has_no_motion(clips) -> None:
    for key, limit in (("move", 0.1), ("turn", 5), ("flow", 0.05)):
        rest, active = _windows(clips["still"], key)
        assert max(rest.max(), active.max()) < limit, key


def test_sliding_object_moves_but_does_not_turn(clips) -> None:
    rest, active = _windows(clips["move"], "move")
    assert np.median(rest) < 0.1
    assert np.median(active) == pytest.approx(150 / np.hypot(110, 110), rel=0.15)
    assert np.median(_windows(clips["move"], "turn")[1]) < 5
    assert clips["move"]["samples"]["x"][-1] == pytest.approx(START[0] + 150, abs=10)


def test_spinning_object_turns_in_place(clips) -> None:
    rest, active = _windows(clips["spin"], "turn")
    assert np.median(rest) < 5
    assert np.median(active) == pytest.approx(180, rel=0.25)
    assert np.median(_windows(clips["spin"], "flow")[1]) > 0.2
    assert np.median(_windows(clips["spin"], "move")[1]) < 0.3


def test_camera_pan_is_not_object_motion(clips) -> None:
    for key, limit in (("move", 0.15), ("turn", 5), ("flow", 0.05)):
        assert np.median(_windows(clips["pan"], key)[1]) < limit, key


def test_tracks_backward_from_a_target_mid_motion(tmp_path: Path) -> None:
    path = make_clip(tmp_path / "move.mp4", "move")
    # At 1.5 s the object has slid 75 px; start the box there.
    result = analyze(
        str(path),
        fps=FPS,
        frame_count=FPS * SECONDS,
        target_index=45,
        target_box=(START[0] + 75, START[1], 110, 110),
        source_size=(WIDTH, HEIGHT),
        class_name=None,
        detector=None,
        on_progress=lambda fraction: True,
    )
    samples = result["samples"]
    assert samples["x"][0] == pytest.approx(START[0], abs=10)
    assert samples["x"][-1] == pytest.approx(START[0] + 150, abs=10)


def test_progress_reaches_one_and_cancel_stops(tmp_path: Path) -> None:
    path = make_clip(tmp_path / "still.mp4", "still")
    seen: list[float] = []
    _run(path, on_progress=lambda fraction: seen.append(fraction) or True)
    assert seen[-1] == 1.0

    with pytest.raises(Canceled):
        _run(path, on_progress=lambda fraction: fraction < 0.5)


class _FakeDetector:
    """Always reports the same boxes, counting how often it is asked."""

    def __init__(self, *boxes: tuple[str, float, float]) -> None:
        self.boxes = boxes
        self.calls = 0

    def __call__(self, image):
        from app.detect import Detection

        self.calls += 1
        return [
            Detection(x=x, y=y, width=110, height=110, class_name=name, confidence=0.9)
            for name, x, y in self.boxes
        ]


def _run_with(path: Path, detector: _FakeDetector) -> dict:
    return analyze(
        str(path),
        fps=FPS,
        frame_count=FPS * SECONDS,
        target_index=15,
        target_box=BOX,
        source_size=(WIDTH, HEIGHT),
        class_name="dog",
        detector=detector,  # type: ignore[arg-type]
        on_progress=lambda fraction: True,
    )


def test_class_target_snaps_to_an_overlapping_detection(tmp_path: Path) -> None:
    path = make_clip(tmp_path / "move.mp4", "move")
    # A dog where the disk stops, 4 px off; the tracker reaches it after 2 s.
    detector = _FakeDetector(("dog", START[0] + 154, START[1] + 4))

    samples = _run_with(path, detector)["samples"]

    assert 1 <= detector.calls <= 3  # about every two seconds in each direction
    assert samples["x"][-1] == pytest.approx(START[0] + 154, abs=2)
    assert samples["x"][0] == pytest.approx(START[0], abs=10)  # never pulled across early


def test_class_target_ignores_other_classes(tmp_path: Path) -> None:
    path = make_clip(tmp_path / "move.mp4", "move")

    samples = _run_with(path, _FakeDetector(("cat", START[0] + 150, START[1])))["samples"]

    assert samples["x"][-1] == pytest.approx(START[0] + 150, abs=10)


def test_target_leaving_and_returning_is_lost_then_found(tmp_path: Path) -> None:
    from synthetic import exit_and_return, make_scene

    path = make_scene(tmp_path / "exit.mp4", exit_and_return, seconds=5)

    result = analyze(
        str(path),
        fps=FPS,
        frame_count=FPS * 5,
        target_index=15,
        target_box=BOX,
        source_size=(WIDTH, HEIGHT),
        class_name=None,
        detector=None,
        on_progress=lambda fraction: True,
    )

    samples = result["samples"]
    t = np.array(samples["t"])
    visible = np.array(samples["visible"])
    assert visible[t < 1.0].all()
    assert not visible[(t > 2.0) & (t < 3.0)].any()  # gone: no box stuck at the edge
    assert visible[t > 3.7].all()  # back: found again
    assert samples["x"][-1] == pytest.approx(START[0], abs=10)


def test_target_found_again_whole_after_leaving_slowly(tmp_path: Path) -> None:
    from synthetic import WIDTH as W
    from synthetic import make_scene

    def slow_exit(t: float) -> tuple[float, float]:
        # Creeps out over 3 s (half cut at the edge for a while), comes back fast.
        away = W + 40
        if t < 1:
            x = START[0]
        elif t < 4:
            x = START[0] + (away - START[0]) * (t - 1) / 3
        elif t < 5:
            x = away
        elif t < 5.6:
            x = away + (START[0] - away) * (t - 5) / 0.6
        else:
            x = START[0]
        return (x, START[1])

    path = make_scene(tmp_path / "slow.mp4", slow_exit, seconds=7)
    result = analyze(
        str(path),
        fps=FPS,
        frame_count=FPS * 7,
        target_index=15,
        target_box=BOX,
        source_size=(WIDTH, HEIGHT),
        class_name=None,
        detector=None,
        on_progress=lambda fraction: True,
    )

    samples = result["samples"]
    assert samples["x"][-1] == pytest.approx(START[0], abs=10)
    # Whole again, not the narrow part that was seen at the edge on the way out.
    assert samples["w"][-1] == pytest.approx(BOX[2], abs=10)


def test_finds_the_same_object_in_another_clip(tmp_path: Path) -> None:
    import cv2
    from synthetic import make_scene

    from app.appearance import Appearance
    from app.locate import find_in_clip

    first = make_scene(tmp_path / "a.mp4", lambda t: START, seconds=1)
    ok, frame = cv2.VideoCapture(str(first)).read()
    assert ok
    reference = Appearance.of(frame, BOX)
    assert reference is not None
    # Same disk, other background, other place, turning; it enters at 1 s.
    other = make_scene(
        tmp_path / "b.mp4",
        lambda t: (60 + 40 * t, 200) if t > 1 else (-200, 200),
        seconds=3,
        background_seed=11,
        turn=lambda t: 60 * t,
    )

    found = find_in_clip(
        str(other),
        fps=FPS,
        frame_count=FPS * 3,
        source_size=(WIDTH, HEIGHT),
        reference=reference,
        class_name=None,
        detector=None,
        on_progress=lambda fraction: True,
    )

    assert found is not None
    assert found.t > 1
    x, y, w, h = found.box
    assert x == pytest.approx(60 + 40 * found.t, abs=12)
    assert y == pytest.approx(200, abs=12)
    assert w == pytest.approx(110, abs=15)
    assert found.score > 0.65


def test_another_object_is_not_taken_for_the_target(tmp_path: Path) -> None:
    import cv2
    from synthetic import make_scene

    from app.appearance import Appearance
    from app.locate import find_in_clip

    first = make_scene(tmp_path / "a.mp4", lambda t: START, seconds=1)
    ok, frame = cv2.VideoCapture(str(first)).read()
    reference = Appearance.of(frame, BOX)
    empty = make_scene(tmp_path / "empty.mp4", lambda t: (-500, -500), seconds=2, background_seed=3)

    found = find_in_clip(
        str(empty),
        fps=FPS,
        frame_count=FPS * 2,
        source_size=(WIDTH, HEIGHT),
        reference=reference,
        class_name=None,
        detector=None,
        on_progress=lambda fraction: True,
    )

    assert found is None
