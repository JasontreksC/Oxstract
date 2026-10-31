"""YOLO11 ONNX pre- and post-processing, without the model file."""

from __future__ import annotations

import numpy as np
import pytest

from app import detect
from app.detect import COCO_CLASSES, DetectorUnavailable, decode, letterbox

DOG = COCO_CLASSES.index("dog")
CAT = COCO_CLASSES.index("cat")


def _output(*boxes: tuple[float, float, float, float, int, float], anchors: int = 50) -> np.ndarray:
    """Fake model output (1, 84, anchors): cx, cy, w, h in model input pixels, then scores."""

    output = np.zeros((1, 4 + len(COCO_CLASSES), anchors), np.float32)
    for anchor, (cx, cy, w, h, class_id, score) in enumerate(boxes):
        output[0, :4, anchor] = (cx, cy, w, h)
        output[0, 4 + class_id, anchor] = score
    return output


def test_letterbox_keeps_aspect_and_centers() -> None:
    image = np.zeros((720, 1280, 3), np.uint8)

    blob, scale, pad_x, pad_y = letterbox(image, 640)

    assert blob.shape == (1, 3, 640, 640)
    assert blob.dtype == np.float32
    assert scale == pytest.approx(0.5)
    assert (pad_x, pad_y) == (0, 140)
    assert blob[0, 0, 0, 0] == pytest.approx(114 / 255)  # grey padding above the picture
    assert blob[0, 0, 300, 300] == 0  # the black picture itself


def test_decode_maps_back_to_image_pixels() -> None:
    # A 200x100 box centred at (640, 360) in a 1280x720 frame is (320, 320) 100x50 after
    # letterboxing at scale 0.5 with 140 px of padding on top.
    output = _output((320, 320, 100, 50, DOG, 0.9))

    [box] = decode(output, scale=0.5, pad_x=0, pad_y=140, width=1280, height=720)

    assert box.class_name == "dog"
    assert box.confidence == pytest.approx(0.9)
    assert (box.x, box.y, box.width, box.height) == pytest.approx((540, 310, 200, 100))


def test_decode_drops_low_scores_and_merges_duplicates() -> None:
    output = _output(
        (320, 320, 100, 50, DOG, 0.9),
        (322, 321, 100, 50, DOG, 0.8),  # same dog, lower score
        (321, 320, 100, 50, CAT, 0.7),  # same place, other class: kept
        (100, 100, 40, 40, DOG, 0.1),  # too unsure
    )

    boxes = decode(output, scale=1, pad_x=0, pad_y=0, width=640, height=640)

    assert [(b.class_name, round(b.confidence, 1)) for b in boxes] == [("dog", 0.9), ("cat", 0.7)]


def test_decode_clips_to_frame() -> None:
    output = _output((10, 10, 60, 60, DOG, 0.9))

    [box] = decode(output, scale=1, pad_x=0, pad_y=0, width=640, height=640)

    assert (box.x, box.y) == (0, 0)
    assert (box.width, box.height) == pytest.approx((40, 40))


def test_missing_model_is_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DETECT_MODEL", str(tmp_path / "missing.onnx"))
    monkeypatch.setattr(detect, "_detector", None)

    with pytest.raises(DetectorUnavailable):
        detect.get_detector()
