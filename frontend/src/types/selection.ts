/** 프레임 픽셀 좌표의 선택 박스. 스텁 오버레이는 아직 스테이지 좌표를 쓴다. */

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectionBox {
  bbox: BBox;
  class_name?: string | null;
  confidence?: number | null;
}

export type SelectionSource = "drag" | "detect";
