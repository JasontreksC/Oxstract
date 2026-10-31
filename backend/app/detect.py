"""Object detection on a single frame with a YOLO11 ONNX model, on the CPU.

The model file is a one-time Ultralytics export (README, "탐지 모델"). Running it
needs only onnxruntime and OpenCV, so the server carries no PyTorch. The model
loads on first use and stays in memory.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

COCO_CLASSES = (
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
)  # fmt: skip

CONFIDENCE = 0.35
IOU = 0.5
MAX_DETECTIONS = 30


class DetectorUnavailable(RuntimeError):
    """The model file or onnxruntime is missing."""


@dataclass(frozen=True)
class Detection:
    """A box in the pixels of the image that was passed in."""

    x: float
    y: float
    width: float
    height: float
    class_name: str
    confidence: float


def model_path() -> Path:
    configured = os.environ.get("DETECT_MODEL")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "models" / "yolo11n.onnx"


def letterbox(image: np.ndarray, size: int) -> tuple[np.ndarray, float, int, int]:
    """Scale into a size×size grey square. Return the NCHW float blob, scale, and padding."""

    height, width = image.shape[:2]
    scale = min(size / width, size / height)
    new_width, new_height = round(width * scale), round(height * scale)
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, np.uint8)
    pad_x, pad_y = (size - new_width) // 2, (size - new_height) // 2
    canvas[pad_y : pad_y + new_height, pad_x : pad_x + new_width] = resized
    blob = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    return np.ascontiguousarray(blob), scale, pad_x, pad_y


def _nms(boxes: np.ndarray, scores: np.ndarray, iou: float) -> list[int]:
    """Greedy non-maximum suppression on x1, y1, x2, y2 boxes."""

    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        best, rest = order[0], order[1:]
        keep.append(int(best))
        x1 = np.maximum(boxes[best, 0], boxes[rest, 0])
        y1 = np.maximum(boxes[best, 1], boxes[rest, 1])
        x2 = np.minimum(boxes[best, 2], boxes[rest, 2])
        y2 = np.minimum(boxes[best, 3], boxes[rest, 3])
        inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        overlap = inter / np.maximum(areas[best] + areas[rest] - inter, 1e-9)
        order = rest[overlap <= iou]
    return keep


def decode(
    output: np.ndarray,
    *,
    scale: float,
    pad_x: int,
    pad_y: int,
    width: int,
    height: int,
    confidence: float = CONFIDENCE,
    iou: float = IOU,
    max_detections: int = MAX_DETECTIONS,
) -> list[Detection]:
    """Turn YOLO11 output (1, 4 + classes, anchors) into boxes in image pixels."""

    prediction = output[0]
    channels = 4 + len(COCO_CLASSES)
    if prediction.shape[0] != channels and prediction.shape[1] == channels:
        prediction = prediction.T
    centers = prediction[:4].T
    class_scores = prediction[4:].T
    class_ids = class_scores.argmax(axis=1)
    scores = class_scores[np.arange(len(class_ids)), class_ids]
    mask = scores >= confidence
    if not mask.any():
        return []
    centers, scores, class_ids = centers[mask], scores[mask], class_ids[mask]

    cx, cy, w, h = centers.T
    x1 = np.clip((cx - w / 2 - pad_x) / scale, 0, width)
    y1 = np.clip((cy - h / 2 - pad_y) / scale, 0, height)
    x2 = np.clip((cx + w / 2 - pad_x) / scale, 0, width)
    y2 = np.clip((cy + h / 2 - pad_y) / scale, 0, height)
    boxes = np.stack([x1, y1, x2, y2], axis=1)
    # Offset each class far apart so one NMS pass never merges different classes.
    offsets = class_ids[:, None].astype(np.float32) * (max(width, height) + 1)
    keep = _nms(boxes + offsets, scores, iou)[:max_detections]

    detections = []
    for index in keep:
        bx1, by1, bx2, by2 = boxes[index]
        if bx2 - bx1 < 2 or by2 - by1 < 2:
            continue
        class_id = int(class_ids[index])
        detections.append(
            Detection(
                x=float(bx1),
                y=float(by1),
                width=float(bx2 - bx1),
                height=float(by2 - by1),
                class_name=COCO_CLASSES[class_id]
                if class_id < len(COCO_CLASSES)
                else str(class_id),
                confidence=float(scores[index]),
            )
        )
    return detections


class Detector:
    def __init__(self, path: Path) -> None:
        try:
            import onnxruntime as ort
        except ImportError:
            raise DetectorUnavailable("onnxruntime이 설치되어 있지 않습니다.") from None
        if not path.is_file():
            raise DetectorUnavailable(
                f"탐지 모델 파일 {path}이 없습니다. README의 '탐지 모델' 절을 보세요."
            )
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, os.cpu_count() or 1)
        self.session = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        model_input = self.session.get_inputs()[0]
        self.input_name = model_input.name
        size = model_input.shape[-1]
        self.size = size if isinstance(size, int) else 640

    def __call__(self, image: np.ndarray) -> list[Detection]:
        blob, scale, pad_x, pad_y = letterbox(image, self.size)
        output = self.session.run(None, {self.input_name: blob})[0]
        height, width = image.shape[:2]
        return decode(output, scale=scale, pad_x=pad_x, pad_y=pad_y, width=width, height=height)


_lock = threading.Lock()
_detector: Detector | None = None


def get_detector() -> Detector:
    """Load the model once. Raise DetectorUnavailable until the file exists."""

    global _detector
    with _lock:
        if _detector is None:
            _detector = Detector(model_path())
        return _detector
