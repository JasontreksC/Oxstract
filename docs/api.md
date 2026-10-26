# Oxstract API

로컬 서버의 FastAPI가 제공한다. 기준은 계획서 4장, 5.0, 5.5다. 완료 후 드라이브 링크는 5.6에 따라 작업 조회와 진행률 이벤트에 실어 보낸다.

베이스 URL 예: `http://127.0.0.1:8000`

- 요청과 응답 JSON은 UTF-8이다.
- 시각은 원본 영상 기준 초 단위다.
- 색은 `#RRGGBB`다.
- 식별자는 문자열이다.
- 기계가 읽을 계약은 [openapi.yaml](openapi.yaml)이고, 구간과 전환의 JSON Schema는 [`schemas/`](../schemas/)에 있다.

## 현재 상태

업로드 저장, 프레임 추출, 파일 제공은 동작한다(M1). 탐지, 작업 실행, 렌더는 아직 `501`을 반환한다. 결과 파일은 렌더 전에는 `404`다. 진행률 소켓은 연결 직후 `stage: "error"` 한 건을 보내고 닫는다.

## POST /videos

영상 파일을 업로드한다.

- Content-Type: `multipart/form-data`
- 필드: `file`

성공 `201`:

```json
{
  "id": "video-id",
  "filename": "clip.mp4",
  "content_type": "video/mp4",
  "duration": 120.0,
  "width": 1920,
  "height": 1080
}
```

길이와 해상도는 저장 후에만 채운다. 알기 전에는 `null`이다.

## GET /videos/{id}/frame?t=

객체 선택에 쓸 프레임 이미지를 반환한다. `t`는 0 이상의 초다.

성공 `200`: `image/png`. 없는 영상이거나 범위를 벗어난 `t`면 `404`다.

## GET /videos/{id}/file

저장된 원본 영상을 그대로 내려보낸다. 재생용이다. 계획서 4장의 주요 API에는 없지만 M1 재생에 필요해 추가했다.

성공 `200`: 업로드 때의 Content-Type(없으면 `video/mp4`). Range 요청을 받아 구간 이어받기를 지원한다. 없는 영상이면 `404`다.

## POST /videos/{id}/detect?t=

그 프레임에 탐지 모델을 돌려 박스 목록을 반환한다. 사용자가 박스를 클릭해 고른다.

성공 `200`:

```json
{
  "t": 12.4,
  "boxes": [
    {
      "bbox": { "x": 100, "y": 80, "width": 240, "height": 180 },
      "class_name": "dog",
      "confidence": 0.91
    }
  ]
}
```

`bbox`는 위 프레임 이미지의 픽셀 좌표다. `x`, `y`는 왼쪽 위다.

## POST /jobs

자동 편집을 시작한다. 5.0에서 고른 프레임과 박스가 추적의 시작점이다. 추적은 그 프레임 기준으로 앞뒤로 진행한다.

```json
{
  "video_id": "video-id",
  "frame_t": 12.4,
  "bbox": { "x": 100, "y": 80, "width": 240, "height": 180 },
  "source": "drag",
  "class": "dog",
  "target": { "text": "강아지", "class_name": null },
  "options": {
    "motion_threshold": 0.05,
    "min_segment_duration": 1.0,
    "padding": 0.3,
    "include_audio": true
  }
}
```

| 필드 | 필수 | 설명 |
|---|---|---|
| `video_id` | 예 | 업로드한 영상 |
| `frame_t` | 예 | 객체를 고른 시각(초) |
| `bbox` | 예 | 그 프레임의 선택 박스 |
| `source` | 예 | `drag` 또는 `detect` |
| `class` | 아니오 | 탐지 박스를 클릭했을 때의 클래스명 |
| `target` | 아니오 | 텍스트 또는 클래스명 지정. 어떤 지정 방식을 쓸지는 아직 미결이다 |
| `options.motion_threshold` | 아니오 | 움직임 임계값. 기본 `0.05` |
| `options.min_segment_duration` | 아니오 | 최소 컷 길이(초). 기본 `1` |
| `options.padding` | 아니오 | 컷 앞뒤 여유(초). 기본 `0.3` |
| `options.include_audio` | 아니오 | 오디오 포함. 기본 `true` |

성공 `202`는 아래 작업 객체를 `status: "queued"`로 반환한다.

## GET /jobs/{id}

상태와 탐지된 구간 목록을 반환한다.

```json
{
  "id": "job-id",
  "video_id": "video-id",
  "status": "awaiting_edit",
  "progress": 1,
  "segments": [],
  "error": null,
  "output_ready": false,
  "drive": { "web_view_link": null, "error": null }
}
```

`status`: `queued`, `running`, `awaiting_edit`, `rendering`, `uploading`, `completed`, `failed`.

구간 탐지가 끝나면 `awaiting_edit`이 되고 `segments`에 시간순 목록이 담긴다. 렌더와 드라이브 업로드가 끝나면 `completed`이고 `drive.web_view_link`에 링크가 있다. 업로드만 실패하면 결과 파일은 로컬에 남고 `drive.error`와 `GET .../output`으로 받을 수 있다.

## PATCH /jobs/{id}/segments

구간 전체를 바꾼다. 부분 수정이 아니라 목록을 통째로 교체한다. 추가, 삭제, 시각 조정, 컷별 전환이 이 요청에 들어간다.

```json
{
  "segments": [
    {
      "start": 1.2,
      "end": 4.8,
      "score": 0.86,
      "transition_after": { "type": "fade", "duration": 0.5 }
    },
    {
      "start": 12.0,
      "end": 15.5,
      "score": 0.74,
      "transition_after": {
        "type": "text_card",
        "duration": 2,
        "bg_color": "#111111",
        "text": "다음 장면",
        "font_size": 48,
        "font_color": "#FFFFFF"
      }
    },
    { "start": 20.0, "end": 22.0, "score": 0.51, "transition_after": null }
  ]
}
```

전환 `type`:

| type | 의미 | 필요한 값 |
|---|---|---|
| `fade` | 앞 컷 페이드 아웃, 다음 컷 페이드 인 | `duration` (기본 0.5초) |
| `text_card` | 단색 배경과 텍스트 장면을 사이에 삽입 | `duration`(기본 2초), `bg_color`, `text`, `font_size`, `font_color` |
| `none` | 바로 잇기. 기본값 | 없음 |

마지막 구간의 `transition_after`는 `null`이거나 빼야 한다. 넣으면 `422`다. `end`는 `start`보다 커야 한다.

일괄 적용은 클라이언트가 마지막 구간을 제외한 모든 `transition_after`를 같은 값으로 채운 뒤 이 요청을 보낸다.

성공하면 저장된 목록을 그대로 반환한다.

## POST /jobs/{id}/render

확정된 구간과 전환으로 최종 영상을 만든다. 전환이 있으면 concat 대신 필터 그래프를 쓴다.

성공 `202`:

```json
{ "job_id": "job-id", "status": "rendering" }
```

## GET /jobs/{id}/output

결과 영상을 내려받는다. 성공 `200`의 Content-Type은 `video/mp4`다. 아직 없으면 `404`다.

## WS /jobs/{id}/progress

작업 진행률 소켓이다.

```json
{
  "job_id": "job-id",
  "stage": "track",
  "progress": 0.42,
  "message": "추적 중",
  "drive": null
}
```

`stage`: `detect`, `track`, `segment`, `render`, `upload`, `done`, `error`.

`progress`는 0부터 1까지다. `done`일 때 `drive.web_view_link`를 포함할 수 있다.

## 오류

| 코드 | 상황 |
|---|---|
| 404 | 없는 영상·프레임, 없는 작업의 결과 파일 |
| 415 | 영상이 아닌 Content-Type 업로드 |
| 422 | 본문이나 쿼리가 스키마에 맞지 않음, 해석할 수 없는 영상 파일 |
| 501 | 라우트는 있으나 파이프라인이 아직 없음 |
