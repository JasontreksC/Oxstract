# 스타일 가이드

긴 영상을 보는 화면이라 어두운 테마를 기본으로 한다. 토큰의 구현은 `frontend/src/styles/tokens.css`와 `frontend/src/styles/tokens.ts`다. 값을 바꿀 때는 두 파일과 이 문서를 같이 고친다.

## 색

| 토큰 | 값 | 쓰임 |
|---|---|---|
| `--color-bg` | `#0f1218` | 페이지 배경 |
| `--color-surface` | `#171c24` | 패널 |
| `--color-surface-raised` | `#212833` | 띄운 카드, 입력 |
| `--color-border` | `#313a49` | 테두리 |
| `--color-text` | `#e7edf6` | 본문 |
| `--color-text-muted` | `#93a0b5` | 보조 글 |
| `--color-accent` | `#4c8dff` | 선택, 재생 머리, 주요 버튼 |
| `--color-accent-strong` | `#80b0ff` | 호버 |
| `--color-danger` | `#f07178` | 삭제, 실패 |
| `--color-success` | `#6dcea0` | 완료, 드라이브 링크 |
| `--color-warning` | `#e6b35a` | 주의, 텍스트 카드 전환 |
| `--color-segment` | `#4c8dff` | 타임라인 컷 |
| `--color-transition-fade` | `#c792ea` | 페이드 마커 |
| `--color-transition-text` | `#e6b35a` | 텍스트 카드 마커 |
| `--color-overlay` | `rgba(76, 141, 255, 0.28)` | 선택 박스 채움 |
| `--color-overlay-stroke` | `#4c8dff` | 선택 박스 테두리 |

대비는 본문 `#e7edf6` 대 배경 `#0f1218`을 기준으로 한다. 상태 의미는 색만으로 전달하지 않고 문구를 같이 둔다.

## 간격

4의 배수다. `--space-1` 4px, `--space-2` 8px, `--space-3` 12px, `--space-4` 16px, `--space-5` 24px, `--space-6` 32px, `--space-8` 48px.

패널 안쪽 여백은 16px, 화면 가장자리는 24px, 관련 컨트롤 사이는 8px이다.

## 모서리와 그림자

`--radius-sm` 4px, `--radius-md` 8px, `--radius-lg` 12px. 패널은 8px. 그림자는 `--shadow-panel`: `0 8px 24px rgba(0, 0, 0, 0.35)`.

## 글꼴

UI 글꼴:

`Pretendard, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif`

한글과 라틴을 한 가족으로 쓰기 위해 Pretendard를 우선한다. 설치되어 있지 않으면 Noto Sans KR, 그다음 운영체제 고딕으로 내려간다. 로컬 서버가 오프라인일 수 있어 CDN으로 글을 불러오지 않는다. 개발 기계에 Pretendard 또는 Noto Sans KR을 설치하면 의도한 모습에 가깝다.

크기: `--font-size-sm` 12px, `--font-size-md` 14px, `--font-size-lg` 16px, `--font-size-xl` 20px, `--font-size-2xl` 28px. 본문은 14px, 화면 제목은 20px이다. 줄 높이는 1.5.

고정폭은 시각과 작업 ID에만 쓴다.

`ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace`

텍스트 카드 장면(FFmpeg `drawtext`)은 UI 글꼴과 별도다. 워커 이미지에 Noto Sans CJK KR 파일을 넣고 그 경로로 그린다. 글꼴 파일은 저장소에 넣지 않는다. 크기와 색은 컷의 `font_size`, `font_color`를 따른다.

## 구성요소 규칙

- 주요 동작은 강조색 버튼 하나다. 나머지 동작은 테두리 버튼이다.
- 타임라인 컷은 `--color-segment`, 페이드는 보라, 텍스트 카드는 호박색으로 구분한다.
- 선택 박스는 채움과 2px 테두리를 같이 그린다. 탐지 박스에는 클래스명과 신뢰도를 붙인다.
- 비활성 컨트롤은 투명도만 낮추지 않고 `disabled`를 준다.
