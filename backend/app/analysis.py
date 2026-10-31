"""Clip analysis: follow the target through the proxy and measure how it moves.

Runs on the CPU in the worker. Starting at the target frame it tracks forward to
the end and backward to the start at about SAMPLE_FPS, and for every sample keeps
the box plus three motion signals measured against the sample before it:

- move: centre travel plus size change relative to the background, in box
  diagonals per second (moving across the screen, coming closer, going away)
- turn: in-plane rotation relative to the background, in degrees per second
- flow: motion inside the box once the box's own travel is taken out, in box
  diagonals per second (spinning in place, turning around, changing pose)

Two motions come from feature points tracked between samples: the camera's
(points outside the box) and the object's (points in the middle of the box).
The object's points move the box when there are enough of them (they follow
spinning objects that CSRT slides off); CSRT takes over on smooth or blurred
objects with too few points. A target picked
from a detection box is also checked against the detector about once a second,
and a hand-drawn one is searched for by template matching after it is lost.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import batched

import cv2
import numpy as np

from app.detect import Detector
from app.media import Canceled, MediaError, frame_time

VERSION = 1
SAMPLE_FPS = 10
ANALYSIS_LONG_SIDE = 640
DETECT_EVERY_SECONDS = 1.0
BACKWARD_CHUNK = 120
FLOW_SIDE = 96
#: Re-seat CSRT on the points' box when they disagree by this many box diagonals.
DRIFT_LIMIT = 0.1
#: Per-sample size changes below this (log scale) are jitter; the box keeps its size.
SCALE_DEADBAND = 0.01

Box = tuple[float, float, float, float]
IDENTITY = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])


@dataclass
class Sample:
    index: int
    box: Box | None = None
    move: float = 0.0
    turn: float = 0.0
    flow: float = 0.0


@dataclass
class _Progress:
    total: int
    callback: Callable[[float], bool]
    done: int = 0

    def tick(self) -> None:
        self.done += 1
        if not self.callback(min(1.0, self.done / max(1, self.total))):
            raise Canceled


def _clip_box(box: Box, width: int, height: int) -> Box | None:
    x, y, w, h = box
    x1, y1 = max(0.0, x), max(0.0, y)
    x2, y2 = min(float(width), x + w), min(float(height), y + h)
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return (x1, y1, x2 - x1, y2 - y1)


def _int_box(box: Box) -> tuple[int, int, int, int]:
    x, y, w, h = box
    return (round(x), round(y), max(1, round(w)), max(1, round(h)))


def _centre(box: Box) -> tuple[float, float]:
    return (box[0] + box[2] / 2, box[1] + box[3] / 2)


def _diag(box: Box) -> float:
    return math.hypot(box[2], box[3])


def _iou(a: Box, b: Box) -> float:
    iw = max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def _affine(
    prev: np.ndarray, cur: np.ndarray, mask: np.ndarray, min_points: int
) -> np.ndarray | None:
    """Similarity transform of the features under `mask`, with a forward-backward check."""

    points = cv2.goodFeaturesToTrack(prev, 150, 0.01, 5, mask=mask)
    if points is None or len(points) < min_points:
        return None
    criteria = {"winSize": (21, 21), "maxLevel": 3}
    moved, status, _ = cv2.calcOpticalFlowPyrLK(prev, cur, points, None, **criteria)
    back, status_back, _ = cv2.calcOpticalFlowPyrLK(cur, prev, moved, None, **criteria)
    error = np.linalg.norm((points - back).reshape(-1, 2), axis=1)
    good = (status.ravel() == 1) & (status_back.ravel() == 1) & (error < 1.0)
    if good.sum() < min_points:
        return None
    matrix, _ = cv2.estimateAffinePartial2D(
        points[good], moved[good], method=cv2.RANSAC, ransacReprojThreshold=2.0
    )
    return matrix


def _angle(matrix: np.ndarray) -> float:
    return math.degrees(math.atan2(matrix[1, 0], matrix[0, 0]))


def _scale(matrix: np.ndarray) -> float:
    return math.sqrt(abs(float(np.linalg.det(matrix[:, :2])))) or 1.0


@dataclass(frozen=True)
class Motion:
    """How the camera and the object moved from one sample to the next."""

    camera: np.ndarray
    obj: np.ndarray | None


def estimate_motion(prev: np.ndarray, cur: np.ndarray, box: Box) -> Motion:
    height, width = prev.shape
    x, y, w, h = box
    outside = np.full((height, width), 255, np.uint8)
    x1, y1 = max(0, int(x - w * 0.25)), max(0, int(y - h * 0.25))
    x2, y2 = min(width, int(x + w * 1.25)), min(height, int(y + h * 1.25))
    outside[y1:y2, x1:x2] = 0
    camera = _affine(prev, cur, outside, min_points=12)

    # The middle of the box, where the object is more likely than the background.
    inside = np.zeros((height, width), np.uint8)
    ix1, iy1 = max(0, int(x + w * 0.15)), max(0, int(y + h * 0.15))
    ix2, iy2 = min(width, int(x + w * 0.85)), min(height, int(y + h * 0.85))
    inside[iy1:iy2, ix1:ix2] = 255
    obj = _affine(prev, cur, inside, min_points=6)
    return Motion(camera=camera if camera is not None else IDENTITY, obj=obj)


def predict_box(box: Box, obj: np.ndarray) -> Box:
    """Where the object's points say the box went: centre moved, size scaled, no rotation."""

    cx, cy = _centre(box)
    nx, ny = obj @ np.array([cx, cy, 1.0])
    scale = _scale(obj)
    if abs(math.log(scale)) < SCALE_DEADBAND:
        scale = 1.0
    w, h = box[2] * scale, box[3] * scale
    return (float(nx - w / 2), float(ny - h / 2), w, h)


def measure(
    prev: np.ndarray, prev_box: Box, cur: np.ndarray, box: Box, motion: Motion, dt: float
) -> tuple[float, float, float]:
    """(move, turn, flow) for an object whose box went from prev_box to box."""

    diag = _diag(prev_box)
    camera = motion.camera
    cx, cy = _centre(prev_box)
    expected = camera @ np.array([cx, cy, 1.0])
    nx, ny = _centre(box)
    shift = math.hypot(nx - expected[0], ny - expected[1]) / diag
    grow = 0.0
    turn = 0.0
    if motion.obj is not None:
        grow = abs(math.log(_scale(motion.obj) / _scale(camera)))
        turn = abs((_angle(motion.obj) - _angle(camera) + 180.0) % 360.0 - 180.0) / dt
    move = (shift + grow) / dt

    # Compare the object with itself: same-size crops centred on the old and new box.
    height, width = prev.shape
    w, h = int(round(prev_box[2])), int(round(prev_box[3]))
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    x1, y1 = int(round(nx - w / 2)), int(round(ny - h / 2))
    flow = 0.0
    inside = (
        w >= 8
        and h >= 8
        and min(x0, y0, x1, y1) >= 0
        and max(x0, x1) + w <= width
        and max(y0, y1) + h <= height
    )
    if inside:
        crop_prev = prev[y0 : y0 + h, x0 : x0 + w]
        crop_cur = cur[y1 : y1 + h, x1 : x1 + w]
        factor = min(1.0, FLOW_SIDE / max(w, h))
        if factor < 1.0:
            size = (max(8, round(w * factor)), max(8, round(h * factor)))
            crop_prev = cv2.resize(crop_prev, size, interpolation=cv2.INTER_AREA)
            crop_cur = cv2.resize(crop_cur, size, interpolation=cv2.INTER_AREA)
        vectors = cv2.calcOpticalFlowFarneback(crop_prev, crop_cur, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        vectors = vectors.reshape(-1, 2)
        residual = np.linalg.norm(vectors - np.median(vectors, axis=0), axis=1)
        flow = float(np.percentile(residual, 75)) / factor / diag / dt
    return move, turn, flow


class _FrameSource:
    """Decode proxy frames by index, scaled for analysis."""

    def __init__(self, path: str, scale: float) -> None:
        self.path = path
        self.scale = scale

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        if self.scale >= 1.0:
            return frame
        size = (round(frame.shape[1] * self.scale), round(frame.shape[0] * self.scale))
        return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)

    def forward(self, indices: list[int]) -> Iterator[tuple[int, np.ndarray]]:
        if not indices:
            return
        capture = cv2.VideoCapture(self.path)
        if not capture.isOpened():
            raise MediaError("미리보기 파일을 열 수 없습니다.")
        try:
            wanted = set(indices)
            capture.set(cv2.CAP_PROP_POS_FRAMES, indices[0])
            for current in range(indices[0], indices[-1] + 1):
                if not capture.grab():
                    return
                if current in wanted:
                    ok, frame = capture.retrieve()
                    if not ok:
                        return
                    yield current, self._resize(frame)
        finally:
            capture.release()

    def backward(self, indices: list[int]) -> Iterator[tuple[int, np.ndarray]]:
        """Descending indices, decoded forward in chunks to bound memory."""

        for chunk in batched(indices, BACKWARD_CHUNK):
            frames = list(self.forward(sorted(chunk)))
            yield from reversed(frames)


class _Tracker:
    """CSRT checked by the object's feature points, plus re-detection or template search."""

    def __init__(self, detector: Detector | None, class_name: str | None, detect_every: int):
        self.detector = detector if class_name else None
        self.class_name = class_name
        self.detect_every = detect_every
        self.csrt = None
        self.template: np.ndarray | None = None
        self.last_box: Box | None = None
        self.since_detect = 0
        self.size = (0, 0)

    def start(self, frame: np.ndarray, box: Box) -> None:
        self.size = (frame.shape[1], frame.shape[0])
        self._reset(frame, box)

    def _reset(self, frame: np.ndarray, box: Box) -> None:
        self.csrt = cv2.TrackerCSRT.create()
        self.csrt.init(frame, _int_box(box))
        x, y, w, h = _int_box(box)
        self.template = cv2.cvtColor(frame[y : y + h, x : x + w], cv2.COLOR_BGR2GRAY)
        self.last_box = box
        self.since_detect = 0

    def _clip(self, box: Box | None) -> Box | None:
        return _clip_box(box, *self.size) if box is not None else None

    def _detect(self, frame: np.ndarray, near: Box, lost: bool) -> Box | None:
        """The same-class detection overlapping `near`. Once lost, also the closest one."""

        assert self.detector is not None
        boxes = [
            (d.x, d.y, d.width, d.height)
            for d in self.detector(frame)
            if d.class_name == self.class_name
        ]
        if not boxes:
            return None
        best = max(boxes, key=lambda b: _iou(b, near))
        if _iou(best, near) >= 0.2:
            return best
        if not lost:
            return None  # a different object of the same kind; keep the tracked one
        cx, cy = _centre(near)

        def distance(b: Box) -> float:
            bx, by = _centre(b)
            return math.hypot(bx - cx, by - cy)

        closest = min(boxes, key=distance)
        return closest if distance(closest) <= 2 * _diag(near) else None

    def _search(self, grey: np.ndarray, near: Box) -> Box | None:
        if self.template is None or self.template.size == 0:
            return None
        th, tw = self.template.shape
        x, y, w, h = near
        x1, y1 = max(0, int(x - w)), max(0, int(y - h))
        x2, y2 = min(grey.shape[1], int(x + 2 * w)), min(grey.shape[0], int(y + 2 * h))
        window = grey[y1:y2, x1:x2]
        if window.shape[0] < th or window.shape[1] < tw:
            return None
        scores = cv2.matchTemplate(window, self.template, cv2.TM_CCOEFF_NORMED)
        _, best, _, (bx, by) = cv2.minMaxLoc(scores)
        return (float(x1 + bx), float(y1 + by), float(tw), float(th)) if best >= 0.6 else None

    def update(
        self, frame: np.ndarray, grey: np.ndarray, prev_grey: np.ndarray, prev_box: Box | None
    ) -> tuple[Box | None, Motion | None]:
        assert self.csrt is not None
        ok, raw = self.csrt.update(frame)
        box = self._clip(tuple(float(v) for v in raw)) if ok else None
        motion = estimate_motion(prev_grey, grey, prev_box) if prev_box is not None else None

        if motion is not None and motion.obj is not None:
            predicted = self._clip(predict_box(prev_box, motion.obj))
            if predicted is not None:
                drifted = box is None or math.dist(_centre(box), _centre(predicted)) > (
                    DRIFT_LIMIT * _diag(predicted)
                )
                box = predicted
                if drifted:
                    self._reset(frame, box)

        self.since_detect += 1
        recheck = self.detect_every if box is not None else max(1, self.detect_every // 2)
        if self.detector is not None and self.since_detect >= recheck:
            self.since_detect = 0
            near = box or self.last_box
            found = self._clip(self._detect(frame, near, box is None)) if near is not None else None
            if found is not None:
                box = found
                self._reset(frame, box)
        elif box is None and self.class_name is None and self.last_box is not None:
            found = self._clip(self._search(grey, self.last_box))
            if found is not None:
                box = found
                self._reset(frame, box)

        if box is not None:
            self.last_box = box
        return box, motion


def _track(
    frames: Iterator[tuple[int, np.ndarray]],
    start_box: Box,
    samples: dict[int, Sample],
    tracker: _Tracker,
    dt: float,
    progress: _Progress,
    forward: bool,
) -> None:
    previous: tuple[int, np.ndarray, Box | None] | None = None
    for index, frame in frames:
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sample = samples.setdefault(index, Sample(index))
        if previous is None:
            tracker.start(frame, start_box)
            sample.box = start_box
            previous = (index, grey, start_box)
            continue
        prev_index, prev_grey, prev_box = previous
        box, motion = tracker.update(frame, grey, prev_grey, prev_box)
        sample.box = box
        if box is not None and prev_box is not None and motion is not None:
            # Motion between two samples belongs to the later one in time.
            owner = samples[index if forward else prev_index]
            owner.move, owner.turn, owner.flow = measure(prev_grey, prev_box, grey, box, motion, dt)
        previous = (index, grey, box)
        progress.tick()


def analyze(
    path: str,
    *,
    fps: int,
    frame_count: int,
    target_index: int,
    target_box: Box,
    source_size: tuple[int, int],
    class_name: str | None,
    detector: Detector | None,
    on_progress: Callable[[float], bool],
) -> dict:
    """Track the target through the whole proxy and return the signals as plain JSON data.

    `target_box` and the returned boxes are in source pixels; `source_size` is the
    (width, height) those pixels refer to.
    """

    capture = cv2.VideoCapture(path)
    ok, first = capture.read()
    capture.release()
    if not ok or first is None:
        raise MediaError("미리보기 파일을 읽을 수 없습니다.")
    proxy_height, proxy_width = first.shape[:2]
    scale = min(1.0, ANALYSIS_LONG_SIDE / max(proxy_width, proxy_height))
    width, height = round(proxy_width * scale), round(proxy_height * scale)
    sx, sy = width / source_size[0], height / source_size[1]
    box = _clip_box(
        (target_box[0] * sx, target_box[1] * sy, target_box[2] * sx, target_box[3] * sy),
        width,
        height,
    )
    if box is None:
        raise MediaError("대상 영역이 너무 작습니다.")

    step = max(1, round(fps / SAMPLE_FPS))
    target_index = min(max(0, target_index), max(0, frame_count - 1))
    indices = sorted({*range(target_index % step, frame_count, step), target_index})
    position = indices.index(target_index)
    dt = step / fps
    progress = _Progress(total=max(1, len(indices) - 1), callback=on_progress)
    source = _FrameSource(path, scale)
    detect_every = max(1, round(DETECT_EVERY_SECONDS / dt))
    samples: dict[int, Sample] = {}

    def tracker() -> _Tracker:
        return _Tracker(detector, class_name, detect_every)

    _track(source.forward(indices[position:]), box, samples, tracker(), dt, progress, True)
    backward = indices[: position + 1][::-1]
    _track(source.backward(backward), box, samples, tracker(), dt, progress, False)

    columns: dict[str, list] = {
        key: [] for key in ("t", "x", "y", "w", "h", "visible", "move", "turn", "flow")
    }
    for index in sorted(samples):
        sample = samples[index]
        columns["t"].append(round(frame_time(index, fps), 4))
        columns["visible"].append(sample.box is not None)
        if sample.box is None:
            for key in ("x", "y", "w", "h"):
                columns[key].append(None)
        else:
            x, y, w, h = sample.box
            columns["x"].append(round(x / sx, 1))
            columns["y"].append(round(y / sy, 1))
            columns["w"].append(round(w / sx, 1))
            columns["h"].append(round(h / sy, 1))
        columns["move"].append(round(sample.move, 4))
        columns["turn"].append(round(sample.turn, 2))
        columns["flow"].append(round(sample.flow, 4))
    return {
        "version": VERSION,
        "proxy_fps": fps,
        "sample_fps": fps / step,
        "target_frame": target_index,
        "target_class": class_name,
        "samples": columns,
    }
