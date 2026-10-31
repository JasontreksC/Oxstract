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


def make_scene(
    path: Path,
    position,
    *,
    seconds: float,
    background_seed: int = 7,
    turn=lambda t: 0.0,
) -> Path:
    """The textured disk at `position(t)` (top-left, may be off screen) on a still scene.

    The disk is always the same one (seed 7), so clips with another
    `background_seed` show the same object somewhere else.
    """

    disk_rng = np.random.default_rng(7)
    _texture(disk_rng, HEIGHT + 40, WIDTH + 200, 6)  # keep the disk identical to make_clip's
    disk = cv2.normalize(_texture(disk_rng, OBJECT, OBJECT, 1), None, 0, 255, cv2.NORM_MINMAX)
    cv2.line(disk, (10, OBJECT // 2), (OBJECT - 10, OBJECT // 2), 255, 6)
    cv2.circle(disk, (OBJECT // 3, OBJECT // 3), 10, 0, -1)
    mask = np.zeros((OBJECT, OBJECT), np.uint8)
    cv2.circle(mask, (OBJECT // 2, OBJECT // 2), OBJECT // 2 - 1, 255, -1)
    scene_rng = np.random.default_rng(background_seed)
    scene = cv2.normalize(_texture(scene_rng, HEIGHT, WIDTH, 6), None, 60, 160, cv2.NORM_MINMAX)

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    for index in range(round(FPS * seconds)):
        t = index / FPS
        canvas = scene.copy()
        rotation = cv2.getRotationMatrix2D((OBJECT / 2, OBJECT / 2), turn(t), 1.0)
        sprite = cv2.warpAffine(disk, rotation, (OBJECT, OBJECT), borderMode=cv2.BORDER_REFLECT)
        x, y = (round(v) for v in position(t))
        # Paste the visible part of the disk only.
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(WIDTH, x + OBJECT), min(HEIGHT, y + OBJECT)
        if x2 > x1 and y2 > y1:
            region = canvas[y1:y2, x1:x2]
            part = mask[y1 - y : y2 - y, x1 - x : x2 - x] > 0
            region[part] = sprite[y1 - y : y2 - y, x1 - x : x2 - x][part]
        writer.write(cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR))
    writer.release()
    return path


def exit_and_return(t: float) -> tuple[float, float]:
    """Rests, slides off the right edge (1-1.6 s), stays away, slides back (3-3.6 s)."""

    away = WIDTH + 40
    if t < 1:
        x = START[0]
    elif t < 1.6:
        x = START[0] + (away - START[0]) * (t - 1) / 0.6
    elif t < 3:
        x = away
    elif t < 3.6:
        x = away + (START[0] - away) * (t - 3) / 0.6
    else:
        x = START[0]
    return (x, START[1])
