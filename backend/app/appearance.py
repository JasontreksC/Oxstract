"""What the target looks like, to tell it apart from everything else.

Used to notice that the tracker has lost the object (the box no longer looks
like it), to find it again anywhere in the frame after it comes back, and to
find the same object in other clips of the project.

Two cues, both unaffected by rotation:
- colour: a hue-saturation histogram plus a brightness histogram of the crop
- texture: SIFT keypoints, matched with Lowe's ratio test; matching them against
  a whole frame also gives the object's position there
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

Box = tuple[float, float, float, float]

#: Below this the box is taken to show something else.
SAME_OBJECT = 0.6
_RATIO = 0.75
_MIN_MATCHES = 8


def _crop(frame: np.ndarray, box: Box) -> np.ndarray | None:
    x, y, w, h = (round(v) for v in box)
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(frame.shape[1], x + w), min(frame.shape[0], y + h)
    if x2 - x1 < 6 or y2 - y1 < 6:
        return None
    return frame[y1:y2, x1:x2]


def _histogram(crop: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hue_sat = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256]).ravel()
    value = cv2.calcHist([hsv], [2], None, [16], [0, 256]).ravel()
    hue_sat /= max(1.0, hue_sat.sum())
    value /= max(1.0, value.sum())
    return np.concatenate([hue_sat, value]).astype(np.float32)


_sift: cv2.SIFT | None = None


def _features(image: np.ndarray, mask: np.ndarray | None = None):
    global _sift
    if _sift is None:
        _sift = cv2.SIFT_create(nfeatures=400)
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return _sift.detectAndCompute(grey, mask)


def _good_matches(ours: np.ndarray | None, theirs: np.ndarray | None) -> list:
    if ours is None or theirs is None or len(ours) < 2 or len(theirs) < 2:
        return []
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(ours, theirs, k=2)
    return [p[0] for p in pairs if len(p) == 2 and p[0].distance < _RATIO * p[1].distance]


@dataclass
class Appearance:
    histogram: np.ndarray
    keypoints: tuple
    descriptors: np.ndarray | None
    size: tuple[int, int]  # crop width, height

    @classmethod
    def of(cls, frame: np.ndarray, box: Box) -> Appearance | None:
        crop = _crop(frame, box)
        if crop is None:
            return None
        keypoints, descriptors = _features(crop)
        return cls(_histogram(crop), keypoints, descriptors, (crop.shape[1], crop.shape[0]))

    def colour(self, crop: np.ndarray) -> float:
        score = cv2.compareHist(self.histogram, _histogram(crop), cv2.HISTCMP_CORREL)
        return float(max(0.0, score))

    def texture(self, crop: np.ndarray) -> float:
        """Share of our keypoints that find a match in the crop (0..1)."""

        if self.descriptors is None or len(self.keypoints) < _MIN_MATCHES:
            return 0.0
        _, theirs = _features(crop)
        matches = _good_matches(self.descriptors, theirs)
        return min(1.0, len(matches) / (0.4 * len(self.keypoints)))

    def similarity(self, frame: np.ndarray, box: Box) -> float:
        """How much the box looks like the target, 0..1."""

        crop = _crop(frame, box)
        if crop is None:
            return 0.0
        colour = self.colour(crop)
        if self.descriptors is None or len(self.keypoints) < _MIN_MATCHES:
            return colour  # a smooth object: colour is all there is
        return 0.5 * colour + 0.5 * self.texture(crop)

    def locate(self, frame: np.ndarray) -> tuple[Box, float] | None:
        """Find the target anywhere in the frame by its keypoints. (box, similarity)."""

        if self.descriptors is None or len(self.keypoints) < _MIN_MATCHES:
            return None
        keypoints, descriptors = _features(frame)
        matches = _good_matches(self.descriptors, descriptors)
        if len(matches) < _MIN_MATCHES:
            return None
        ours = np.float32([self.keypoints[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        theirs = np.float32([keypoints[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        matrix, inliers = cv2.estimateAffinePartial2D(
            ours, theirs, method=cv2.RANSAC, ransacReprojThreshold=4.0
        )
        if matrix is None or inliers is None or int(inliers.sum()) < _MIN_MATCHES:
            return None
        scale = math.sqrt(abs(float(np.linalg.det(matrix[:, :2]))))
        if not 0.25 < scale < 4:
            return None
        w, h = self.size
        cx, cy = matrix @ np.array([w / 2, h / 2, 1.0])
        box = (float(cx - w * scale / 2), float(cy - h * scale / 2), w * scale, h * scale)
        return box, self.similarity(frame, box)

    def best(self, frame: np.ndarray, boxes: list[Box]) -> tuple[Box, float] | None:
        """The candidate box that looks most like the target."""

        scored = [(box, self.similarity(frame, box)) for box in boxes]
        return max(scored, key=lambda item: item[1]) if scored else None
