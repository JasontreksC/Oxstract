/**
 * 화면(무대) 좌표와 원본 영상 픽셀 좌표 사이의 변환.
 * 서버와 주고받는 박스는 늘 원본 픽셀(회전 적용 뒤)이고, 변환은 이 파일에서만 한다.
 */

export interface Size {
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

/** object-fit: contain 으로 무대에 그려진 영상의 자리. 남는 곳은 레터박스다. */
export function fitRect(stage: Size, media: Size): Rect {
  if (stage.width <= 0 || stage.height <= 0 || media.width <= 0 || media.height <= 0) {
    return { x: 0, y: 0, width: 0, height: 0 };
  }
  const scale = Math.min(stage.width / media.width, stage.height / media.height);
  const width = media.width * scale;
  const height = media.height * scale;
  return { x: (stage.width - width) / 2, y: (stage.height - height) / 2, width, height };
}

export function stageToSource(point: Point, frame: Rect, media: Size): Point {
  return {
    x: ((point.x - frame.x) / frame.width) * media.width,
    y: ((point.y - frame.y) / frame.height) * media.height,
  };
}

export function sourceToStage(box: Rect, frame: Rect, media: Size): Rect {
  const sx = frame.width / media.width;
  const sy = frame.height / media.height;
  return {
    x: frame.x + box.x * sx,
    y: frame.y + box.y * sy,
    width: box.width * sx,
    height: box.height * sy,
  };
}

/** 드래그 두 점(원본 좌표)으로 만든 박스. 영상 밖은 잘라 낸다. */
export function boxFromPoints(a: Point, b: Point, media: Size): Rect {
  const x1 = clamp(Math.min(a.x, b.x), 0, media.width);
  const y1 = clamp(Math.min(a.y, b.y), 0, media.height);
  const x2 = clamp(Math.max(a.x, b.x), 0, media.width);
  const y2 = clamp(Math.max(a.y, b.y), 0, media.height);
  return { x: x1, y: y1, width: x2 - x1, height: y2 - y1 };
}

export function insideRect(point: Point, rect: Rect): boolean {
  return (
    point.x >= rect.x &&
    point.y >= rect.y &&
    point.x <= rect.x + rect.width &&
    point.y <= rect.y + rect.height
  );
}

/** 미리보기 프레임 번호. backend app/media.py frame_index 와 같다. */
export function frameIndex(t: number, fps: number): number {
  return Math.max(0, Math.floor(t * fps + 1e-6));
}

/** 프레임 가운데 시각. 브라우저와 서버가 같은 프레임을 보게 한다. */
export function frameTime(index: number, fps: number): number {
  return (index + 0.5) / fps;
}
