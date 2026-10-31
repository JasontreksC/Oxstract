"""Cutting signals into parts to keep, and manual edits on top."""

from __future__ import annotations

import numpy as np
import pytest

from app.segments import THRESHOLDS, Edit, Params, activity, compute

FPS = 10


def _analysis(move: list[float], turn: list[float] | None = None, visible=None) -> dict:
    count = len(move)
    return {
        "sample_fps": FPS,
        "samples": {
            "t": [(i + 0.5) / FPS for i in range(count)],
            "visible": visible if visible is not None else [True] * count,
            "move": move,
            "turn": turn if turn is not None else [0.0] * count,
            "flow": [0.0] * count,
        },
    }


def _motion(seconds: float, *spans: tuple[float, float], level: float = 0.6) -> list[float]:
    """Move signal of `level` diagonals/s inside the spans, 0.02 elsewhere."""

    t = (np.arange(int(seconds * FPS)) + 0.5) / FPS
    values = np.full(len(t), 0.02)
    for start, end in spans:
        values[(t >= start) & (t < end)] = level
    return values.tolist()


NO_PADDING = Params(padding=0.0)


def _ranges(cuts) -> list[tuple[float, float]]:
    return [(c.start, c.end) for c in cuts]


def test_one_motion_becomes_one_part() -> None:
    cuts = compute(_analysis(_motion(10, (2, 4))), 10, NO_PADDING)

    assert len(cuts) == 1
    assert cuts[0].start == pytest.approx(2, abs=0.15)
    assert cuts[0].end == pytest.approx(4, abs=0.15)
    assert 0 < cuts[0].score <= 1
    assert not cuts[0].edited


def test_padding_and_clip_edges() -> None:
    cuts = compute(_analysis(_motion(10, (0, 2))), 10, Params(padding=0.5))

    assert cuts[0].start == 0
    assert cuts[0].end == pytest.approx(2.5, abs=0.15)


def test_short_blips_are_dropped_and_short_pauses_merged() -> None:
    signal = _motion(10, (1, 1.4), (3, 4), (4.3, 5.5))

    cuts = compute(_analysis(signal), 10, Params(padding=0.0, merge_gap=0.5, min_length=1.0))

    assert _ranges(cuts) == [pytest.approx((3, 5.5), abs=0.15)]


def test_hysteresis_keeps_a_dip_just_under_the_threshold() -> None:
    signal = _motion(10, (2, 6))
    dip = THRESHOLDS["move"] * 0.8  # below the threshold, above the exit level
    for i in range(35, 40):
        signal[i] = dip

    assert len(compute(_analysis(signal), 10, Params(padding=0.0, merge_gap=0))) == 1


def test_sensitivity_lowers_the_bar() -> None:
    gentle = _motion(10, (2, 4), level=THRESHOLDS["move"] * 0.7)

    assert compute(_analysis(gentle), 10, NO_PADDING) == []
    assert len(compute(_analysis(gentle), 10, Params(padding=0.0, sensitivity=2))) == 1


def test_rotation_counts_unless_switched_off() -> None:
    turn = [0.0] * 100
    for i in range(30, 60):
        turn[i] = 90.0
    data = _analysis([0.0] * 100, turn)

    assert len(compute(data, 10, NO_PADDING)) == 1
    assert compute(data, 10, Params(padding=0.0, use_turn=False)) == []


def test_lost_target_is_not_motion() -> None:
    signal = _motion(10, (2, 6))
    visible = [not (20 <= i < 60) for i in range(100)]

    assert compute(_analysis(signal, visible=visible), 10, NO_PADDING) == []


def test_activity_is_relative_to_threshold() -> None:
    data = _analysis([THRESHOLDS["move"]] * 5)

    level = activity(data["samples"], FPS, Params())

    assert level == pytest.approx([1.0] * 5)


def test_edits_drop_keep_and_trim() -> None:
    data = _analysis(_motion(20, (2, 6), (10, 12)))
    edits = [
        Edit("drop", 3, 4),  # split the first part
        Edit("keep", 15, 17),  # add one that was not detected
        Edit("drop", 11.5, 20),  # trim the end of the second part
    ]

    cuts = compute(data, 20, NO_PADDING, edits)

    assert _ranges(cuts) == [
        pytest.approx((2, 3), abs=0.15),
        pytest.approx((4, 6), abs=0.15),
        pytest.approx((10, 11.5), abs=0.15),
    ]
    assert all(cut.edited for cut in cuts)


def test_edits_survive_a_new_sensitivity() -> None:
    data = _analysis(_motion(20, (2, 6)))
    edits = [Edit("keep", 10, 12)]

    for sensitivity in (0.5, 1.0, 3.0):
        cuts = compute(data, 20, Params(padding=0.0, sensitivity=sensitivity), edits)
        assert (10, 12) in _ranges(cuts)


def test_later_edit_wins() -> None:
    data = _analysis([0.0] * 100)

    cuts = compute(data, 10, NO_PADDING, [Edit("keep", 2, 5), Edit("drop", 2, 5)])
    assert cuts == []
    cuts = compute(data, 10, NO_PADDING, [Edit("drop", 2, 5), Edit("keep", 2, 5)])
    assert _ranges(cuts) == [(2, 5)]
