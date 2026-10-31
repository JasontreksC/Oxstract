"""What the target looks like, to tell it apart from everything else.

Used to notice that the tracker has lost the object (the box no longer looks
like it), to find it again anywhere in the frame after it comes back, and to
find the same object in other clips of the project.

Two cues, both unaffected by rotation:
- colour: a hue-saturation histogram plus a brightness histogram of the crop
- texture: SIFT keypoints, matched with Lowe's ratio test; matching them against
  a whole frame also gives the object's position there

A whole frame is searched two ways: by keypoints (`locate`), which needs a
textured object big enough to show many of them, and by colour (`scan`), which
also finds small or turned objects whose keypoints mostly do not match.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

Box = tuple[float, float, float, float]

#: A smooth target (too few keypoints to match) is still there while the box's
#: colour correlates at least this much.
SAME_OBJECT = 0.6
#: A textured target is still there while the box shows keypoints of its own and
#: its colour correlates at least this much. Keypoint matches are not asked for:
#: a target seen small, turned or under other light matches few of them.
STILL_COLOUR = 0.5
_RATIO = 0.75
_MIN_MATCHES = 8
#: Texture is the share of the smaller side's keypoints that match; with fewer
#: keypoints than this a few chance matches would count for too much.
_TEXTURE_FLOOR = 20
#: Colour scan: candidate places tried per frame.
_SCAN_CANDIDATES = 4
#: A found box must be at least this much inside the frame. An object still coming
#: in is left for a later frame, so its box is not cut at the edge for good.
MOSTLY_INSIDE = 0.85


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


def _inside_share(box: Box, width: int, height: int) -> float:
    x, y, w, h = box
    iw = max(0.0, min(float(width), x + w) - max(0.0, x))
    ih = max(0.0, min(float(height), y + h) - max(0.0, y))
    return iw * ih / (w * h) if w > 0 and h > 0 else 0.0


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


@dataclass(frozen=True)
class Look:
    """Colour and keypoints of one box, worked out once and compared with any appearance."""

    histogram: np.ndarray
    keypoints: tuple
    descriptors: np.ndarray | None
    size: tuple[int, int]  # crop width, height

    @classmethod
    def of(cls, frame: np.ndarray, box: Box) -> Look | None:
        crop = _crop(frame, box)
        if crop is None:
            return None
        keypoints, descriptors = _features(crop)
        return cls(_histogram(crop), keypoints, descriptors, (crop.shape[1], crop.shape[0]))


@dataclass(frozen=True)
class Features:
    """Keypoints of a whole frame, to search it for several appearances."""

    keypoints: tuple
    descriptors: np.ndarray | None

    @classmethod
    def of(cls, frame: np.ndarray) -> Features:
        return cls(*_features(frame))


@dataclass
class Appearance:
    histogram: np.ndarray
    keypoints: tuple
    descriptors: np.ndarray | None
    size: tuple[int, int]  # crop width, height

    @classmethod
    def of(cls, frame: np.ndarray, box: Box) -> Appearance | None:
        look = Look.of(frame, box)
        return cls.from_look(look) if look is not None else None

    @classmethod
    def from_look(cls, look: Look) -> Appearance:
        return cls(look.histogram, look.keypoints, look.descriptors, look.size)

    def _textured(self) -> bool:
        return self.descriptors is not None and len(self.keypoints) >= _MIN_MATCHES

    def compare(self, look: Look | None) -> float:
        """How much the box seen in `look` looks like the target, 0..1."""

        if look is None:
            return 0.0
        colour = cv2.compareHist(self.histogram, look.histogram, cv2.HISTCMP_CORREL)
        colour = float(max(0.0, colour))
        if not self._textured():
            return colour  # a smooth object: colour is all there is
        theirs = len(look.keypoints)
        if theirs < _MIN_MATCHES:
            # Plain floor or wall where a textured target should be: colour alone
            # cannot tell, since the picked box holds some background too.
            return 0.5 * colour
        # Share of keypoints that find a match, counted on the side with fewer of
        # them: a target seen smaller than when it was picked shows fewer keypoints.
        # Each of their keypoints counts once, however many of ours pick it.
        matched = {m.trainIdx for m in _good_matches(self.descriptors, look.descriptors)}
        fewer = max(_TEXTURE_FLOOR, min(len(self.keypoints), theirs))
        texture = min(1.0, len(matched) / (0.4 * fewer))
        return 0.5 * colour + 0.5 * texture

    def still_there(self, look: Look | None) -> bool:
        """Whether a box being tracked can still show the target.

        Looser than `compare`: it only has to tell the target from what a box is
        left on when the target has gone, which is plain floor, wall or sky (no
        keypoints) or something of another colour.
        """

        if look is None:
            return False
        colour = cv2.compareHist(self.histogram, look.histogram, cv2.HISTCMP_CORREL)
        if not self._textured():
            return colour >= SAME_OBJECT
        return len(look.keypoints) >= _MIN_MATCHES and colour >= STILL_COLOUR

    def similarity(self, frame: np.ndarray, box: Box) -> float:
        """How much the box looks like the target, 0..1."""

        return self.compare(Look.of(frame, box))

    def locate(
        self, frame: np.ndarray, features: Features | None = None
    ) -> tuple[Box, float] | None:
        """Find the target anywhere in the frame by its keypoints. (box, similarity).

        Only an object at least MOSTLY_INSIDE the frame counts as found. Pass the
        frame's `features` when searching it for more than one appearance.
        """

        if not self._textured():
            return None
        if features is None:
            features = Features.of(frame)
        keypoints, descriptors = features.keypoints, features.descriptors
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
        if _inside_share(box, frame.shape[1], frame.shape[0]) < MOSTLY_INSIDE:
            return None
        return box, self.similarity(frame, box)

    def scan(self, frame: np.ndarray, size: tuple[float, float]) -> tuple[Box, float] | None:
        """Find the target by colour: the box of `size` (w, h) that looks most like it.

        The target's hue-saturation histogram is projected on the frame; the few
        places where a box of that size holds most of it are compared in full.
        """

        width, height = frame.shape[1], frame.shape[0]
        w = max(8, min(round(size[0]), width))
        h = max(8, min(round(size[1]), height))
        hue_sat = self.histogram[:128].reshape(16, 8)
        model = (hue_sat / max(float(hue_sat.max()), 1e-6) * 255).astype(np.float32)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        projected = cv2.calcBackProject([hsv], [0, 1], model, [0, 180, 0, 256], 1)
        density = cv2.boxFilter(projected.astype(np.float32), -1, (w, h))
        candidates: list[Box] = []
        for _ in range(_SCAN_CANDIDATES):
            _, peak, _, (cx, cy) = cv2.minMaxLoc(density)
            if peak <= 0:
                break
            x, y = cx - w // 2, cy - h // 2
            # Near the frame edge the object may still be coming in, and the colour
            # of the part already in pulls the box off centre: left for a later frame.
            mx, my = w // 4, h // 4
            if mx <= x <= width - w - mx and my <= y <= height - h - my:
                candidates.append((float(x), float(y), float(w), float(h)))
            # Rule this place out before looking for the next one.
            cv2.rectangle(density, (x, y), (x + w, y + h), 0, -1)
        return self.best(frame, candidates)

    def best(self, frame: np.ndarray, boxes: list[Box]) -> tuple[Box, float] | None:
        """The candidate box that looks most like the target."""

        scored = [(box, self.similarity(frame, box)) for box in boxes]
        return max(scored, key=lambda item: item[1]) if scored else None
