"""Synthetic clips with known motion for analysis tests."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT, FPS, SECONDS = 640, 360, 30, 3
OBJECT = 110  # disk diameter in pixels
START = (265, 125)  # top-left of the object's box at rest
BOX = (*START, OBJECT, OBJECT)


def _texture(rng: np.random.Generator, height: int, width: int, blur: int) -> np.ndarray:
    noise = rng.integers(0, 256, (height, width), dtype=np.uint8)
    return cv2.GaussianBlur(noise, (0, 0), blur)


def make_clip(path: Path, motion: str) -> Path:
    """motion: still, move (slides right 1-2 s), spin (turns 180° in place 1-2 s),
    pan (camera pans right 1-2 s, object fixed in the scene)."""

    rng = np.random.default_rng(7)
    scene = cv2.normalize(
        _texture(rng, HEIGHT + 40, WIDTH + 200, 6), None, 60, 160, cv2.NORM_MINMAX
    )
    disk = cv2.normalize(_texture(rng, OBJECT, OBJECT, 1), None, 0, 255, cv2.NORM_MINMAX)
    cv2.line(disk, (10, OBJECT // 2), (OBJECT - 10, OBJECT // 2), 255, 6)
    cv2.circle(disk, (OBJECT // 3, OBJECT // 3), 10, 0, -1)
    mask = np.zeros((OBJECT, OBJECT), np.uint8)
    cv2.circle(mask, (OBJECT // 2, OBJECT // 2), OBJECT // 2 - 1, 255, -1)

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    for index in range(FPS * SECONDS):
        progress = min(1.0, max(0.0, index / FPS - 1.0))  # 0 before 1 s, 1 after 2 s
        canvas = scene.copy()
        x, y = START[0] + 100, START[1] + 20  # position in the larger scene
        sprite = disk
        if motion == "move":
            x += round(150 * progress)
        elif motion == "spin":
            turn = cv2.getRotationMatrix2D((OBJECT / 2, OBJECT / 2), 180 * progress, 1.0)
            sprite = cv2.warpAffine(disk, turn, (OBJECT, OBJECT), borderMode=cv2.BORDER_REFLECT)
        region = canvas[y : y + OBJECT, x : x + OBJECT]
        region[mask > 0] = sprite[mask > 0]
        offset = 100 + (round(100 * progress) if motion == "pan" else 0)
        view = canvas[20 : 20 + HEIGHT, offset : offset + WIDTH]
        writer.write(cv2.cvtColor(view, cv2.COLOR_GRAY2BGR))
    writer.release()
    return path
