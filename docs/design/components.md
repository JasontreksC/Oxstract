# 화면 구성요소

스타일은 [style-guide.md](style-guide.md), 배치는 [ui-redesign.md](ui-redesign.md)와 [wireframes.md](wireframes.md)를 따른다. 표의 "상태"는 2026-10-31 기준이다.

## 경로

| 경로 | 컴포넌트 | 상태 |
|---|---|---|
| `/` | `routes/HomePage.tsx` | 동작. 프로젝트 카드, 새 프로젝트, 화면 어디든 영상을 놓으면 새 프로젝트 |
| `/p/:projectId/:step` | `routes/ProjectEditor.tsx` | ①~⑤ 모두 동작 |

## 편집기 틀

| 이름 | 파일 | 역할 |
|---|---|---|
| Stepper | `editor/Stepper.tsx`, `editor/steps.ts` | 다섯 단계, 끝난 단계 체크, 잠긴 단계와 이유 |
| ProjectTitle | `editor/ProjectTitle.tsx` | 이름 누르면 바로 고치기 |
| ActivityButton | `editor/ActivityButton.tsx` | 뒤에서 도는 작업 수, 목록과 취소 |
| Inspector 스타일 | `editor/Inspector.module.css` | 오른쪽 패널 공통 제목, 사실 목록 |

## 클립과 업로드

| 이름 | 파일 | 역할 |
|---|---|---|
| ClipList | `features/clips/ClipList.tsx` | 썸네일 카드, 상태 배지, dnd-kit 끌어서 순서(키보드 가능), 올리는 중 카드 |
| useUploads | `features/clips/uploads.ts` | XHR 업로드 큐(진행률), 홈에서 넘어온 파일 이어받기 |
| UploadDropzone | `features/clips/UploadDropzone.tsx` | 클립이 없을 때 뷰어 자리의 큰 놓기 영역 |
| MediaInspector | `features/clips/MediaInspector.tsx` | 길이·해상도·fps·코덱·오디오·미리보기 상태, 다시 만들기, 빼기 |
| ResultOrder | `features/clips/ResultOrder.tsx` | 클립을 길이 비율로 늘어놓은 결과 순서 |

## 플레이어

| 이름 | 파일 | 역할 |
|---|---|---|
| Viewer | `player/Viewer.tsx` | 프록시 재생, 재생 바 하나, 프레임 가운데로 이동, 단축키, 미리보기 준비·실패 상태, `overlay` 렌더 함수, `seek`·`play` 핸들, `playRanges`로 컷만 재생 |
| geometry | `player/geometry.ts` | 무대↔원본 픽셀 변환(레터박스 보정), 드래그 박스, 프레임 번호. `geometry.test.ts`로 검사 |

## 대상 지정

| 이름 | 파일 | 역할 |
|---|---|---|
| TargetOverlay | `features/target/TargetOverlay.tsx` | 멈추면 탐지(0.25초 디바운스), 박스 표시, 제자리 클릭은 커서 아래 가장 작은 박스 선택, 끌면 직접 그리기 |
| TargetInspector | `features/target/TargetInspector.tsx` | 고른 영역 잘라 보기, 저장·취소·그 장면 보기, 저장된 대상 지우기, 지정 진행(n/m) |
| classLabel | `lib/coco.ts` | COCO 이름의 한국어 표기 |

## ③ 구간

| 이름 | 파일 | 역할 |
|---|---|---|
| TrackOverlay | `features/analysis/TrackOverlay.tsx` | 재생 중 추적 박스와 그 순간의 신호 값. 클릭은 영상으로 통과 |
| AnalysisInspector | `features/analysis/AnalysisInspector.tsx` | 분석이 아직이거나 실패한 클립의 상태와 다시 분석 |
| SegmentTimeline | `features/segments/SegmentTimeline.tsx` | 신호 그래프, 끌 수 있는 민감도 기준선, 남는 구간 음영, 놓친 구간 빗금, 구간 띠(끝 끌기, 빈 곳 끌어 새 구간, 눌러 고르기), Delete·I·O·Ctrl+Z |
| SegmentInspector | `features/segments/SegmentInspector.tsx` | 민감도 프리셋, 이동·회전 켜기, 멈춤 합치기·여유 슬라이더, 고급(민감도 숫자, 최소 길이), 요약, 고른 컷(재생, 빼기), 되돌리기, 자동 구간으로 |
| useCutEditor | `features/segments/useCutEditor.ts` | 설정을 바로 화면에 반영하고 0.12초 뒤 저장, 되돌리기 기록(0.7초 안 변경은 하나로), 고른 컷을 시각으로 기억 |
| edits | `lib/edits.ts` | 끝 끌기를 keep/drop 편집으로 바꾸기, 덮이는 옛 편집 정리. `edits.test.ts`로 검사 |
| playhead | `player/playhead.ts` | 뷰어 밖 타임라인이 재생 위치를 읽는 작은 저장소(편집기 전체를 매 프레임 다시 그리지 않음) |
| SIGNALS | `lib/signals.ts` | 신호 이름, 단위, 그래프 기준값, 샘플 찾기. `signals.test.ts`로 검사 |

## ④ 전환·텍스트

| 이름 | 파일 | 역할 |
|---|---|---|
| Storyboard | `features/sequence/Storyboard.tsx` | 결과 순서의 컷 카드(썸네일, 길이), 컷 사이 전환 칩, 클립 경계, 시작·끝 제목 칸 |
| TransitionInspector | `features/sequence/TransitionInspector.tsx` | 없음·페이드·텍스트 카드, 페이드 길이, 문구·색·크기·시간, 모든 컷 사이에 적용 |
| TransitionPreview | 같은 파일 | 텍스트 카드 모양, 또는 앞 컷 끝과 다음 컷 처음 프레임 |
| useSequenceEditor | `features/sequence/useSequenceEditor.ts` | 바로 화면에 반영하고 0.3초 뒤 저장 |

## ⑤ 내보내기

| 이름 | 파일 | 역할 |
|---|---|---|
| ExportInspector | `features/export/ExportInspector.tsx` | 해상도·품질·오디오, 예상 길이와 크기, 렌더 시작과 진행·취소, 결과 목록(보기, 다운로드, 지우기) |
| RenderPlayer | 같은 파일 | 고른(없으면 최근) 결과 재생 |

## 서버 상태

| 이름 | 파일 | 역할 |
|---|---|---|
| api, uploadClip | `api/client.ts` | `/api` 호출, 오류 문구 추출 |
| 쿼리 훅 | `api/queries.ts` | TanStack Query. 미리보기를 만드는 동안 프로젝트를 1초마다 다시 읽음, 순서 변경은 낙관적 갱신 |
| 타입 | `api/types.ts` | `backend/app/schemas.py`와 같다 |

## 다음에 만들 것

드라이브 업로드 표시(⑤, M7), 필름스트립 썸네일 줄(③).

전환 타입(`types/transition.ts`)은 `schemas/`와 같다.
