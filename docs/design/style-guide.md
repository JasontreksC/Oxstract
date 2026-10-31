# 스타일 가이드

영상 색을 해치지 않도록 어두운 테마를 쓴다. 영역은 테두리보다 면의 밝기 차이로 나눈다. 토큰의 구현은 `frontend/src/styles/tokens.css`와 `frontend/src/styles/tokens.ts`다. 값을 바꿀 때는 두 파일과 이 문서를 같이 고친다. 확정 목업: [wireframes.md](wireframes.md).

## 색

| 토큰 | 값 | 쓰임 |
|---|---|---|
| `--color-bg` | `#0e1116` | 페이지 배경, 입력 칸 |
| `--color-surface` | `#151a21` | 패널 |
| `--color-surface-card` | `#1a2028` | 패널 안 카드(클립) |
| `--color-surface-raised` | `#1d232c` | 보조 버튼, 안내 상자 |
| `--color-border` | `#2a313c` | 입력과 버튼 테두리 |
| `--color-border-strong` | `#333c49` | 점선 놓기 영역, 호버 |
| `--color-text` | `#e8edf4` | 본문 |
| `--color-text-muted` | `#9aa6b8` | 보조 글 |
| `--color-text-dim` | `#8a95a7` | 더 약한 글, 단축키 안내 |
| `--color-accent` | `#4c8dff` | 주 버튼, 선택, 재생 위치 |
| `--color-accent-strong` | `#7aa7ff` | 호버, 진행 중 표시 |
| `--color-on-accent` | `#08111f` | 강조색 위 글자 |
| `--color-success` | `#6dcea0` | 끝난 단계, 완료 |
| `--color-warning` | `#e6b35a` | 대상 필요, 텍스트 카드, 임계선 |
| `--color-danger` | `#f07178` | 삭제, 실패 |
| `--color-signal-move` | `#8fb4ff` | 움직임 그래프: 이동 |
| `--color-signal-rotate` | `#c792ea` | 움직임 그래프: 회전, 페이드 칩 |

보조 글 색은 패널 배경 위에서 4.5:1 이상이다. 상태는 색만으로 전달하지 않고 아이콘이나 문구를 같이 둔다.

## 간격과 모서리

간격은 4의 배수(`--space-1` 4px ~ `--space-8` 48px). 화면 가장자리와 패널 사이 16px, 패널 안 16px, 관련 컨트롤 사이 8px.

모서리: 입력·작은 요소 6px, 버튼 8px, 패널·카드 12px.

## 글꼴

`"Pretendard Variable"`을 npm 패키지(`pretendard`)로 번들에 넣는다. 사설망 서버가 오프라인이어도 같은 모습이 나온다. 한글 글리프는 dynamic subset이라 화면에 나온 글자 조각만 받는다.

크기: 11, 12, 13, 14(본문), 16, 18, 24px. 줄 높이 1.5. 시각과 숫자는 `font-variant-numeric: tabular-nums`로 자리가 흔들리지 않게 한다(`.num`).

텍스트 카드 장면(FFmpeg `drawtext`)은 UI 글꼴과 별도다. 이미지에 `fonts-noto-cjk`를 넣고 그 경로로 그린다.

## 구성요소 규칙

- 영역마다 주 버튼(`.btn-primary`, 높이 44px)은 하나다. 나머지는 `.btn`, `.btn-ghost`, `.btn-danger`.
- 선택지가 2~4개면 드롭다운 대신 세그먼트 버튼을 쓴다.
- 숫자 입력보다 프리셋과 슬라이더를 먼저 보여 주고, 정확한 값은 "고급"에 접는다.
- 아이콘은 `lucide-react`. 아이콘만 있는 버튼에는 `aria-label`.
- 비활성 컨트롤은 `disabled`와 함께 이유를 `title`로 알린다.
- 타임라인: 남는 구간은 강조색 반투명 채움, 버려지는 부분은 어둡게, 임계선은 호박색 점선.
