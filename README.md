# Oxstract

지정한 객체가 움직이거나 도는 구간만 잘라, 여러 영상을 순서대로 하나로 이어 붙이는 셀프호스팅 영상 편집기다. 사설망의 서버 한 대에서 돌리고 같은 네트워크의 브라우저로 쓴다. 서버는 CPU만으로 동작하도록 만든다(오래 걸려도 결과가 나오는 쪽을 택한다).

남은 일과 순서는 [docs/roadmap.md](docs/roadmap.md), 화면 설계는 [docs/design/ui-redesign.md](docs/design/ui-redesign.md)에 있다. 처음 계획서는 [video-editor-plan.md](video-editor-plan.md)다.

## 지금 되는 것 (M5)

- 프로젝트 만들기, 이름 바꾸기, 지우기
- 여러 영상 올리기(진행률 표시), 끌어서 순서 바꾸기, 빼기
- 업로드 직후 `ffprobe`로 길이, 해상도, 회전, fps, 오디오 유무 읽기
- 워커가 브라우저용 미리보기(H.264, 짧은 변 720px, 회전 적용) 만들기. 휴대폰 HEVC·세로 영상도 재생된다
- 단일 재생 바 플레이어, 프레임 단위 이동(←/→, Shift 1초, Space 재생)
- 대상 지정: 영상을 멈추면 YOLO11n(CPU)이 그 프레임의 물체를 찾아 박스로 띄운다. 박스를 누르거나 직접 끌어 그려 따라갈 대상을 저장한다. 한 클립에서 고르면 프로젝트 전체가 그 대상을 공유해, 다른 클립(나중에 추가하는 것 포함)에서는 서버가 같은 대상을 찾아 정한다. 못 찾거나 틀리면 그 클립에서 직접 고르면 된다
- 분석: 대상을 저장하면 워커가 뒤에서 그 대상을 영상 전체에 걸쳐 따라가며(CSRT + 특징점, 탐지 대상은 1초마다 YOLO로 보정) 초당 10번 이동·회전·내부 움직임을 잰다. 카메라 움직임은 뺀다. 대상이 화면 밖으로 나가면 놓친 것으로 표시하고, 다시 들어오면 겉모습으로 찾아 다시 따라간다
- 구간 자르기: 분석이 끝나면 움직이거나 도는 부분만 자동으로 골라 둔다. ③ 구간 단계에서 민감도(프리셋 또는 그래프의 기준선 끌기), 이동·회전 켜고 끄기, 짧은 멈춤 합치기, 앞뒤 여유를 바꾸면 바로 다시 자른다
- 구간 편집: 구간 끝을 끌어 늘이거나 줄이고, 빈 곳을 끌어 새 구간을 만들고, 골라서 Delete로 뺀다(I/O로 시작·끝을 재생 위치에). 손으로 고친 것은 민감도를 바꿔도 남는다. Ctrl+Z로 되돌린다
- 미리보기: "컷만"을 켜면 남는 부분만 이어서 재생한다. 재생 중 추적 박스와 그 순간의 신호도 보인다

- 전환·텍스트: ④ 단계에서 결과 순서대로 늘어선 컷 사이마다 없음·페이드·텍스트 카드를 고르고(한꺼번에 적용 가능), 시작·끝 제목 카드를 넣는다
- 내보내기: ⑤ 단계에서 해상도(원본 최대/1080p/720p), 품질, 오디오를 골라 렌더한다. 워커가 모든 클립의 남는 구간을 순서대로 이어 하나의 mp4로 만든다. 다른 모양의 클립은 레터박스, 소리 없는 클립은 무음으로 맞춘다. 끝나면 화면에서 보고 내려받는다

구글 드라이브 업로드는 아직 없다(M7).

## 구성

| 경로 | 역할 |
|---|---|
| `backend/app` | FastAPI(`/api`)와 워커(`python -m app.worker`). SQLite DB와 영상은 `MEDIA_ROOT` 아래 |
| `frontend/` | React, TypeScript, Vite. 빌드 결과는 백엔드가 같은 포트로 서빙 |
| `Dockerfile`, `docker-compose.yml` | 이미지 하나로 `app`과 `worker` 두 서비스 |
| `models/` | 탐지 모델(`yolo11n.onnx`) 자리. 파일은 커밋하지 않는다 |
| `config/` | 드라이브 설정 예시. 실제 값은 커밋하지 않는다 |
| `docs/` | 로드맵, API, 화면 문서 |
| `schemas/` | 구간과 전환 JSON Schema |
| `samples/` | 로컬 테스트 영상 자리 |

## 준비

- Python 3.12 이상
- Node.js 22 이상
- FFmpeg (`ffmpeg`, `ffprobe`). Ubuntu는 `sudo apt install ffmpeg`. PATH에 없으면 `.env`의 `FFMPEG_BIN`, `FFPROBE_BIN`
- 컨테이너로 띄울 때 Docker Compose

```bash
cp .env.example .env
cp config/drive.example.yaml config/drive.yaml
chmod 600 config/drive.yaml
```

### 텍스트 카드 글꼴

텍스트 카드는 FFmpeg `drawtext`로 그리며 한글 글꼴이 필요하다. Docker 이미지에는 `fonts-noto-cjk`가 들어 있다. 로컬에서는 `sudo apt install fonts-noto-cjk`로 설치하거나 `.env`의 `FONT_FILE`에 글꼴 파일 경로를 적는다. 글꼴이 없으면 텍스트 카드가 든 렌더만 실패한다.

### 탐지 모델

대상 지정 화면의 탐지 박스는 `models/yolo11n.onnx`를 쓴다. Docker 이미지는 빌드할 때 알아서 만든다. 로컬에서는 [models/README.md](models/README.md)대로 한 번 만든다. 모델이 없어도 직접 끌어 그려 대상을 고르는 기능은 동작한다.

## 개발 실행

터미널 세 개를 쓴다. 영상과 DB는 기본으로 `./data`에 쌓인다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
```

```bash
source .venv/bin/activate
PYTHONPATH=backend python -m app.worker
```

```bash
cd frontend
npm install
npm run dev
```

`http://127.0.0.1:5173`을 연다. Vite가 `/api`를 8000번으로 넘긴다. 같은 네트워크의 다른 기기에서는 `http://<서버 IP>:5173`으로 연다. `oxstract.lan` 같은 이름으로 열려면 `.env`의 `VITE_ALLOWED_HOSTS`에 그 이름을 적는다.

API 문서는 `http://127.0.0.1:8000/api/docs`다.

## 서버에서 운영 (사설망)

저장소 루트에서:

```bash
docker compose up -d --build
```

`http://<서버 IP>:8000`에서 화면과 API가 함께 열린다. 포트는 `.env`의 `APP_PORT`로 바꾼다. 영상과 DB는 named volume `media`에, 설정은 `./config`에 있다. 열리는 포트는 앱 하나뿐이다.

Docker 없이 한 포트로 띄우려면 `cd frontend && npm run build`로 `frontend/dist`를 만든 뒤 uvicorn을 `--host 0.0.0.0`으로 실행하고 워커를 같이 띄운다. 백엔드가 `frontend/dist`를 찾아 화면도 서빙한다.

## 검사

```bash
ruff check backend scripts
ruff format --check backend scripts
pytest
```

FFmpeg가 없으면 영상이 필요한 테스트를, 탐지 모델이 없으면 실제 모델 테스트를 건너뛴다.

```bash
cd frontend
npm run lint
npm run typecheck
npm run format:check
npm test
npm run build
```

같은 검사가 `.github/workflows/ci.yml`에 있다.

## 문서

- [로드맵과 수정 계획](docs/roadmap.md)
- [API](docs/api.md)
- [UI 개편 계획](docs/design/ui-redesign.md), [스타일](docs/design/style-guide.md), [구성요소](docs/design/components.md), [와이어프레임](docs/design/wireframes.md)
- [샘플 영상](samples/README.md)
