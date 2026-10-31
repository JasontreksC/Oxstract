# Oxstract API

FastAPI가 제공한다. 모든 경로는 `/api` 아래에 있고, 빌드된 웹 화면은 같은 서버가 나머지 경로로 내려보낸다. 사설망에서는 포트 하나만 열면 된다.

- 요청과 응답 JSON은 UTF-8이다. 오류 응답은 `{"detail": "..."}` 이다.
- 시각은 원본 영상 기준 초 단위다. 폭과 높이는 회전을 적용한 뒤 화면에 보이는 크기다.
- 기계가 읽을 계약은 서버가 만드는 `GET /api/openapi.json`이고, 문서 화면은 `/api/docs`다. 구간과 전환의 JSON Schema는 [`schemas/`](../schemas/)에 있다.

## 현재 상태 (M5)

동작함: 프로젝트, 클립 업로드와 순서, 영상 메타데이터, 미리보기 프록시(워커), 프레임과 썸네일, 작업 목록·취소·SSE, 프레임 탐지, 클립 대상 저장, 대상 분석(워커)과 신호 조회, 구간 판정과 손 편집, 결과 순서와 전환, 렌더(워커)와 결과 파일.

아직 없음: 드라이브 업로드(M7).

## 프레임 번호

미리보기는 고정 fps(`proxy_fps`)라서 시각 `t`가 든 프레임 번호는 `floor(t × proxy_fps)`다. 서버는 시각을 받으면 이 번호로 바꿔 정확히 그 프레임을 읽고, 돌려줄 때는 프레임 가운데 시각 `(번호 + 0.5) / proxy_fps`를 쓴다. 브라우저가 이 시각으로 이동하면 같은 프레임을 보여 준다.

## 프로젝트

| 메서드와 경로 | 설명 | 성공 |
|---|---|---|
| `GET /api/projects` | 목록. 최근 수정 순 | `200` `ProjectSummary[]` |
| `POST /api/projects` | 만들기. 본문 `{"name": "주말 산책"}` (1~100자) | `201` `Project` |
| `GET /api/projects/{id}` | 클립 포함 상세 | `200` `Project` |
| `PATCH /api/projects/{id}` | 이름 바꾸기. 본문 `{"name": "..."}` | `200` `Project` |
| `DELETE /api/projects/{id}` | 지우기. 다른 프로젝트가 쓰지 않는 영상 파일도 지운다 | `204` |

```json
{
  "id": "4f0c…",
  "name": "주말 산책",
  "created_at": "2026-10-31T05:33:09.120Z",
  "updated_at": "2026-10-31T05:36:18.004Z",
  "clips": [{ "id": "…", "project_id": "4f0c…", "position": 0, "video": { "...": "Video" } }],
  "reference": { "clip_id": "…", "class_name": "dog" }
}
```

`reference`는 프로젝트가 공유하는 대상이다. 마지막으로 손으로 대상을 고른 클립이고, 아직 없으면 `null`이다(아래 "대상").

`ProjectSummary`는 `clip_count`, `total_duration`(원본 길이 합), `cover_video_id`(첫 클립 영상)를 더 준다.

## 클립

| 메서드와 경로 | 설명 | 성공 |
|---|---|---|
| `POST /api/projects/{id}/clips` | 영상 업로드 후 끝에 추가. `multipart/form-data`의 `file` | `201` `Clip` |
| `DELETE /api/projects/{id}/clips/{clip_id}` | 빼기. 쓰는 곳이 없어진 영상 파일도 지운다 | `204` |
| `PUT /api/projects/{id}/clips/order` | 순서 바꾸기. 본문 `{"clip_ids": [...]}`에 이 프로젝트 클립을 한 번씩 모두 | `200` `Project` |
| `PUT /api/projects/{id}/clips/{clip_id}/target` | 따라갈 대상 저장 (아래) | `200` `Clip` |
| `DELETE /api/projects/{id}/clips/{clip_id}/target` | 대상 지우기. 분석도 취소하고 지운다. 공유 대상을 고른 클립이면 공유도 끝난다 | `200` `Clip` |
| `GET /api/projects/{id}/clips/{clip_id}/analysis` | 분석 결과 JSON (아래). 아직이면 `409` | `200` |
| `POST /api/projects/{id}/clips/{clip_id}/analysis` | 지금 대상으로 다시 분석. 대상이 없으면 공유 대상을 다시 찾는다. 둘 다 없으면 `409` | `202` `Clip` |
| `GET /api/projects/{id}/clips/{clip_id}/segments` | 자르는 설정과 결과 (아래). 분석 전이면 `409` | `200` |
| `PUT /api/projects/{id}/clips/{clip_id}/segments` | 설정·손 편집을 바꾸고 다시 자르기 | `200` |

### 대상

```json
{
  "t": 12.4,
  "bbox": { "x": 566, "y": 229, "width": 791, "height": 502 },
  "source": "detect",
  "class_name": "bus",
  "confidence": 0.9
}
```

- `bbox`는 원본 픽셀(회전 적용 뒤, `Video.width`×`Video.height` 기준)이다.
- `source`는 `detect`(탐지 박스를 누름) 또는 `drag`(직접 그림). `drag`면 `class_name`, `confidence`는 버린다.
- 서버는 `t`를 프레임 가운데로 맞추고 `frame_index`를 붙여 `Clip.target`에 돌려준다. 박스는 화면 안으로 잘라 내고, 남는 쪽이 4px보다 작으면 `422`다. 영상 길이를 넘는 `t`도 `422`다.
- 대상을 저장하면 그 클립의 이전 분석을 취소하고 새 분석 작업(`kind: "analyze"`)을 큐에 넣는다. 진행은 `Clip.analysis`에 있다.

공유 대상:

- 손으로 저장한 대상은 프로젝트의 `reference`가 된다. 서버는 그 장면에서 대상을 잘라 겉모습(색 분포와 SIFT 특징점)을 기억한다.
- 대상이 없거나 자동으로 찾은 다른 클립은 모두 다시 분석한다. 나중에 추가하는 클립도 같다. 이런 분석 작업은 먼저 `stage: "locate"`로 영상을 0.5초 간격(최대 120장)으로 훑어 같은 대상을 찾는다. 같은 종류의 탐지 박스와 특징점이 맞는 자리 중 가장 닮은 곳을 고른다.
- 찾으면 `Clip.target`에 `source: "auto"`와 닮은 정도 `score`(0..1)를 붙여 저장하고 `stage: "track"`으로 분석을 이어 간다. 그 클립에서 손으로 대상을 고르면 그것이 우선한다.
- 닮은 정도가 0.65보다 낮으면 못 찾은 것으로 보고 작업이 실패한다(`Clip.target`은 `null`, 오류 문구는 직접 지정 안내).

### 분석

`Clip.analysis`:

```json
{ "status": "running", "progress": 0.42, "stage": "track", "job_id": "…", "error": null, "ready": false }
```

`ready`가 `true`면 결과를 읽을 수 있다. 결과는 샘플(초당 약 10개)마다 한 칸인 열 형식이다.

```json
{
  "version": 1,
  "proxy_fps": 30,
  "sample_fps": 10,
  "target_frame": 372,
  "target_class": "dog",
  "samples": {
    "t": [0.0167, 0.1167, "…"],
    "x": [566.0, 571.5, "…"], "y": ["…"], "w": ["…"], "h": ["…"],
    "visible": [true, true, "…"],
    "move": [0.012, 0.31, "…"],
    "turn": [0.4, 2.1, "…"],
    "flow": [0.003, 0.02, "…"]
  }
}
```

- 박스(`x`, `y`, `w`, `h`)는 원본 픽셀이고, 대상을 놓친 샘플은 `visible: false`, 박스는 `null`이다.
- 추적 중 박스 안이 대상과 두 번 연속 닮지 않으면(화면 밖으로 나감, 가려짐) 놓친 것으로 본다. 놓친 동안은 0.3초마다 화면 전체에서 다시 찾고, 찾으면 거기서 다시 따라간다.
- `move`: 바로 앞 샘플에서 중심 이동과 크기 변화, 박스 대각선/초. 카메라 움직임을 뺀 값.
- `turn`: 화면 평면 안 회전, 도/초. 카메라 회전을 뺀 값.
- `flow`: 박스 자체의 이동을 뺀 안쪽 움직임(제자리 회전, 몸 돌리기, 자세 변화), 박스 대각선/초.
- 구간 판정은 이 값을 임계값과 비교한다(아래 "구간"). 화면 그래프는 이동 0.25, 회전 20°/s, 내부 0.1을 가운데 높이로 그린다.

### 구간

분석이 끝나면 워커가 그 클립의 설정(없으면 기본값)으로 한 번 잘라 `Clip.cuts`에 둔다. 그래서 ③ 단계를 열지 않은 클립도 렌더할 수 있다.

```json
{
  "params": {
    "sensitivity": 1.0,
    "use_move": true,
    "use_turn": true,
    "merge_gap": 0.5,
    "padding": 0.3,
    "min_length": 1.0
  },
  "edits": [
    { "op": "drop", "start": 3.0, "end": 4.0 },
    { "op": "keep", "start": 15.0, "end": 17.0 }
  ],
  "cuts": [{ "start": 0.67, "end": 2.47, "score": 0.83, "edited": false }],
  "duration": 6.0,
  "kept": 1.8
}
```

- 판정(`backend/app/segments.py`): 켜진 신호마다 값 ÷ 임계값(이동 0.25, 회전 20°/s, 내부 0.1; `sensitivity`로 나눔) 중 큰 것을 0.3초 이동평균하고, 1을 넘으면 시작해 0.7 아래로 내려가면 끝낸다. 대상을 놓친 샘플은 0. 이어서 `merge_gap` 이하 멈춤 합치기, `min_length` 미만 버리기, 앞뒤 `padding`.
- `use_turn`은 평면 회전(`turn`)과 안쪽 움직임(`flow`)을 함께 켜고 끈다.
- `edits`는 그 위에 차례로 덧씌운다. `keep`은 범위를 더하고 `drop`은 뺀다. 시간 범위라서 민감도를 바꿔도 뜻이 그대로다. 뒤의 편집이 앞의 것을 이긴다. 최대 500개.
- `edited`는 손 편집이 닿은 구간이다. 0.1초보다 짧은 조각은 남기지 않는다.
- PUT은 몇 ms 걸려서 화면이 슬라이더를 끄는 동안 바로 부른다(0.12초 디바운스).

업로드는 `ffprobe`로 바로 읽어 메타데이터를 채우고, 미리보기 작업을 큐에 넣는다.

- 영상이 아닌 Content-Type: `415`
- 읽을 수 없는 파일: `422`
- 서버 디스크 여유 1GB 미만: `507`
- 서버에 FFmpeg가 없음: `503`
- 순서 목록이 클립과 맞지 않음: `422`

## 영상

```json
{
  "id": "2d3c…",
  "filename": "IMG_0412.MOV",
  "content_type": "video/quicktime",
  "duration": 48.2,
  "width": 1080,
  "height": 1920,
  "fps": 29.97,
  "rotation": 90,
  "video_codec": "hevc",
  "has_audio": true,
  "variable_fps": true,
  "proxy": { "status": "running", "progress": 0.42, "job_id": "c4ea…", "error": null },
  "created_at": "2026-10-31T05:33:09.120Z"
}
```

| 메서드와 경로 | 설명 |
|---|---|
| `GET /api/videos/{id}` | 위 모델 |
| `GET /api/videos/{id}/file` | 원본 파일. Range 지원 |
| `GET /api/videos/{id}/proxy` | 미리보기 mp4. 아직이면 `409` |
| `POST /api/videos/{id}/proxy` | 미리보기 다시 만들기. `202` `Job` |
| `GET /api/videos/{id}/frame?t=` | 그 시각 프레임 PNG. 프록시가 있으면 프록시에서 뽑는다. 범위 밖이면 `404` |
| `GET /api/videos/{id}/thumb` | 320px JPEG 썸네일. 한 번 만들어 둔다 |
| `POST /api/videos/{id}/detect?t=` | 그 프레임의 물체 박스 (아래) |

미리보기(프록시): H.264 + AAC, 짧은 변 최대 720px, 원본 fps를 30 이하 정수(`proxy_fps`)로 고정, 1초마다 키프레임, 회전 적용. 브라우저 재생과 이후 CPU 분석에 쓴다.

### 탐지

`POST /api/videos/{id}/detect?t=12.4`는 미리보기 프레임에 YOLO11n(ONNX Runtime, CPU)을 돌린다. COCO 80종, 신뢰도 0.35 이상, 최대 30개.

```json
{
  "t": 12.416,
  "frame_index": 372,
  "boxes": [
    { "bbox": { "x": 566, "y": 229, "width": 791, "height": 502 }, "class_name": "bus", "confidence": 0.9 }
  ]
}
```

박스는 원본 픽셀이다. 미리보기가 아직이면 `409`, 모델 파일이 없으면 `503`(직접 그리기는 계속 쓸 수 있다). 이 서버 CPU에서 한 프레임에 약 0.2초 걸린다.

## 결과 순서와 전환

| 메서드와 경로 | 설명 |
|---|---|
| `GET /api/projects/{id}/sequence` | 결과 순서(클립 순서 → 클립 안 컷 시간순)와 컷마다 다음 전환 |
| `PUT /api/projects/{id}/sequence` | 전환과 시작·끝 제목 저장 |

```json
{
  "default": { "type": "fade", "duration": 0.5 },
  "overrides": {
    "6cf1…:2.7": {
      "type": "text_card", "duration": 2, "text": "2부",
      "bg_color": "#111111", "font_color": "#FFFFFF", "font_size": 48
    }
  },
  "intro": { "type": "text_card", "duration": 2, "text": "주말 산책", "bg_color": "#111111", "font_color": "#FFFFFF", "font_size": 64 },
  "outro": null,
  "items": [{ "key": "6cf1…:0.7", "clip_id": "6cf1…", "video_id": "…", "clip_position": 0, "index": 0, "start": 0.67, "end": 2.47, "transition_after": { "type": "fade", "duration": 0.5 } }],
  "total": 11.2
}
```

- 전환은 앞 컷의 `key`(클립 id + 컷 시작 0.1초 단위)로 저장한다. 한 클립을 다시 잘라도 다른 클립의 전환은 그대로다. 없는 key는 `default`를 쓴다.
- `fade`: 앞 컷 끝을 검게, 다음 컷 처음을 밝게(영상·소리 모두). 컷 안에서 일어나 길이가 늘지 않는다. 컷 길이의 절반을 넘지 않는다.
- `text_card`: 단색 배경에 가운데 글자 장면을 그 시간만큼 넣는다. `font_size`는 1080줄 기준 픽셀.
- `total`은 컷 길이 합 + 텍스트 카드 길이 합.

## 렌더

| 메서드와 경로 | 설명 |
|---|---|
| `POST /api/projects/{id}/renders` | 렌더 큐에 넣기. 본문 `{"resolution": "1080", "quality": "mid", "audio": true}`. 남는 구간이 없으면 `409` |
| `GET /api/projects/{id}/renders` | 최근 결과 50개 (진행 중 포함) |
| `GET /api/renders/{id}/file` | 결과 mp4. `?download=true`면 첨부로, 파일 이름은 프로젝트 이름 |
| `DELETE /api/renders/{id}` | 지우기. 진행 중이면 취소 |

- `resolution`: `source`는 첫 클립 크기(긴 변 최대 3840), `1080`·`720`은 첫 클립 방향(가로/세로)에 맞춘 16:9 또는 9:16.
- 출력: 30fps, H.264(libx264, CPU) yuv420p, AAC 48kHz 스테레오, `faststart`. 품질 `small`/`mid`/`high`는 preset veryfast/medium/slow, CRF 26/22/19.
- 조각마다 같은 규격으로 인코딩한 뒤 concat demuxer로 재인코딩 없이 잇는다(`backend/app/render.py`).

## 작업

워커(`python -m app.worker`)가 SQLite `jobs` 표에서 하나씩 꺼내 처리한다. 종류는 `proxy`, `analyze`, `render`.

```json
{
  "id": "c4ea…",
  "kind": "proxy",
  "ref_id": "2d3c…",
  "status": "running",
  "stage": "transcode",
  "progress": 0.42,
  "message": "미리보기 만드는 중",
  "error": null,
  "created_at": "…",
  "started_at": "…",
  "finished_at": null
}
```

`status`: `queued` → `running` → `done` | `failed` | `canceled`.

| 메서드와 경로 | 설명 |
|---|---|
| `GET /api/jobs?active=true` | 대기·실행 중인 작업. `active`를 빼면 최근 200개 |
| `GET /api/jobs/{id}` | 하나 |
| `POST /api/jobs/{id}/cancel` | 대기 중이면 바로 취소, 실행 중이면 워커가 다음 진행 보고 때 멈춘다 |
| `GET /api/jobs/{id}/events` | `text/event-stream`. 바뀔 때마다 `event: job` + 위 JSON. 끝나면 스트림을 닫는다 |

워커가 비정상 종료해 `running`으로 남은 작업은 다음 워커가 켜질 때 `failed`로 바뀐다.

## 상태 확인

`GET /api/health` → `{"status": "ok"}`
