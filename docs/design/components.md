# 화면 구성요소

스타일은 [style-guide.md](style-guide.md), 배치는 [wireframes.md](wireframes.md)를 따른다. 아래 네 컴포넌트는 스텁으로 저장소에 있다. 업로드 칸, 민감도 입력, 진행 막대, 화면 전환은 `frontend/src/App.tsx`에 잠시 모여 있다.

## 객체 선택

| 이름 | 파일 | 역할 |
|---|---|---|
| VideoPlayer | `frontend/src/components/VideoPlayer.tsx` | 재생, 시각 이동, "이 장면에서 선택" |
| BoxSelectionOverlay | `frontend/src/components/BoxSelectionOverlay.tsx` | 드래그 박스와 탐지 박스 클릭 |
| 업로드, 민감도, 시작 버튼 | `App.tsx` | 파일 선택과 `POST /jobs`에 넘길 옵션 |

`BoxSelectionOverlay`의 좌표는 아직 프레임 픽셀이 아니라 오버레이 박스 기준이다. 영상을 실제로 붙일 때 프레임 크기로 환산한다.

## 진행

| 이름 | 위치 | 역할 |
|---|---|---|
| 진행 막대와 단계 문구 | `App.tsx` | `progress`와 `stage` 표시 |
| 완료 배너 | `App.tsx` | `drive.web_view_link` 또는 실패 문구 |

소켓 클라이언트는 아직 없다. 화면은 예시 수치만 보여 준다.

## 타임라인 편집

| 이름 | 파일 | 역할 |
|---|---|---|
| VideoPlayer | 위와 같음 | 고른 구간 미리보기 |
| Timeline | `frontend/src/components/Timeline.tsx` | 구간 선택, 컷 사이 전환 표시, 일괄 적용 |
| TransitionSettingsPanel | `frontend/src/components/TransitionSettingsPanel.tsx` | `fade`, `text_card`, `none` 설정 |

일괄 적용은 마지막 구간을 제외하고 같은 `transition_after`를 채운다. 마지막 구간을 고르면 패널은 비활성이다. 미리보기는 자리만 있다.

구간 타입은 `frontend/src/types`와 `schemas/`가 같다.
