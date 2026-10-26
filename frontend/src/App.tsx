import { useState } from "react";
import { BoxSelectionOverlay, Timeline, TransitionSettingsPanel, VideoPlayer } from "./components";
import type { BBox, DetectionBox, Segment, SelectionSource, TransitionAfter } from "./types";
import { fadeTransition } from "./types";

type Screen = "select" | "progress" | "edit";

const DURATION = 30;

const SAMPLE_DETECTIONS: DetectionBox[] = [
  {
    bbox: { x: 48, y: 70, width: 140, height: 110 },
    class_name: "dog",
    confidence: 0.91,
  },
];

const INITIAL_SEGMENTS: Segment[] = [
  {
    start: 1.2,
    end: 4.8,
    score: 0.86,
    transition_after: fadeTransition(),
  },
  {
    start: 12,
    end: 15.5,
    score: 0.74,
    transition_after: null,
  },
];

export function App() {
  const [screen, setScreen] = useState<Screen>("select");
  const [currentTime, setCurrentTime] = useState(12.4);
  const [mode, setMode] = useState<SelectionSource>("drag");
  const [selectedBox, setSelectedBox] = useState<BBox | null>(null);
  const [segments, setSegments] = useState<Segment[]>(INITIAL_SEGMENTS);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(0);

  const lastIndex = segments.length - 1;
  const panelTransition =
    selectedIndex != null && selectedIndex < lastIndex
      ? (segments[selectedIndex]?.transition_after ?? null)
      : null;

  function updateTransition(next: TransitionAfter) {
    if (selectedIndex == null || selectedIndex >= lastIndex) {
      return;
    }
    setSegments((current) =>
      current.map((segment, index) =>
        index === selectedIndex ? { ...segment, transition_after: next } : segment,
      ),
    );
  }

  function applyToAll(transition: TransitionAfter) {
    setSegments((current) =>
      current.map((segment, index) =>
        index === current.length - 1
          ? { ...segment, transition_after: null }
          : { ...segment, transition_after: transition },
      ),
    );
  }

  return (
    <main className="app">
      <header className="topbar">
        <div>
          <h1>Oxstract</h1>
          <p className="muted">객체가 움직이는 구간만 이어 붙입니다. 화면은 스텁입니다.</p>
        </div>
        <nav className="tabs" aria-label="화면">
          <button
            type="button"
            aria-selected={screen === "select"}
            onClick={() => setScreen("select")}
          >
            객체 선택
          </button>
          <button
            type="button"
            aria-selected={screen === "progress"}
            onClick={() => setScreen("progress")}
          >
            진행
          </button>
          <button type="button" aria-selected={screen === "edit"} onClick={() => setScreen("edit")}>
            타임라인
          </button>
        </nav>
      </header>

      {screen === "select" ? (
        <>
          <div className="row">
            <label className="field">
              영상 파일
              <input type="file" accept="video/*" disabled />
            </label>
            <span className="muted">업로드 API는 아직 501입니다.</span>
          </div>
          <VideoPlayer
            currentTime={currentTime}
            duration={DURATION}
            onTimeChange={setCurrentTime}
            onSelectFrame={setCurrentTime}
          >
            <BoxSelectionOverlay
              mode={mode}
              detections={SAMPLE_DETECTIONS}
              selected={selectedBox}
              onDragSelect={setSelectedBox}
              onDetectionClick={(box) => setSelectedBox(box.bbox)}
            />
          </VideoPlayer>
          <div className="panel row">
            <span>선택 방식</span>
            <button type="button" aria-pressed={mode === "drag"} onClick={() => setMode("drag")}>
              드래그
            </button>
            <button
              type="button"
              aria-pressed={mode === "detect"}
              onClick={() => setMode("detect")}
            >
              탐지 박스
            </button>
            <label className="field">
              움직임 임계값
              <input type="number" defaultValue={0.05} step={0.01} />
            </label>
            <label className="field">
              최소 컷(초)
              <input type="number" defaultValue={1} step={0.1} />
            </label>
            <label className="field">
              앞뒤 여유(초)
              <input type="number" defaultValue={0.3} step={0.1} />
            </label>
            <button type="button" className="primary" onClick={() => setScreen("progress")}>
              편집 시작
            </button>
          </div>
        </>
      ) : null}

      {screen === "progress" ? (
        <section className="panel stack" aria-label="진행률">
          <strong>추적 중</strong>
          <div
            className="progress"
            aria-valuenow={42}
            aria-valuemin={0}
            aria-valuemax={100}
            role="progressbar"
          >
            <span style={{ width: "42%" }} />
          </div>
          <p className="muted">예시 42%입니다. WebSocket은 아직 연결되어 있지 않습니다.</p>
          <p className="muted">끝나면 드라이브 링크 또는 로컬 다운로드를 여기에 표시합니다.</p>
        </section>
      ) : null}

      {screen === "edit" ? (
        <div className="stack">
          <VideoPlayer
            currentTime={currentTime}
            duration={DURATION}
            onTimeChange={setCurrentTime}
          />
          <Timeline
            segments={segments}
            duration={DURATION}
            selectedIndex={selectedIndex}
            onSelectSegment={setSelectedIndex}
            onApplyTransitionToAll={applyToAll}
          />
          <div className="editor-grid">
            <TransitionSettingsPanel
              transition={panelTransition}
              disabled={panelTransition == null}
              onChange={updateTransition}
            />
            <section className="panel stack">
              <p className="muted">구간 수정은 화면에만 남습니다. 저장 API는 아직 501입니다.</p>
              <button type="button" className="primary" onClick={() => setScreen("progress")}>
                렌더
              </button>
            </section>
          </div>
        </div>
      ) : null}
    </main>
  );
}
