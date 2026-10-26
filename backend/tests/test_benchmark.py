from scripts.benchmark import estimate_detect_seconds, ten_minute_1080p_frames


def test_ten_minute_frame_count() -> None:
    assert ten_minute_1080p_frames() == 18_000


def test_cpu_nano_matches_plan_chapter() -> None:
    seconds = estimate_detect_seconds(18_000, "n", "cpu")
    assert 16 * 60 < seconds < 18 * 60


def test_sample_every_reduces_detection_frames() -> None:
    full = estimate_detect_seconds(18_000, "n", "cpu", sample_every=1)
    sampled = estimate_detect_seconds(18_000, "n", "cpu", sample_every=3)
    assert sampled * 2.5 < full
