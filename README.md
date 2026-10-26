# Oxstract

지정한 객체가 움직이는 구간만 잘라 시간순으로 잇는 로컬 영상 편집기다. 이 저장소는 그 앱의 시작 골격이다. 범위와 순서는 [video-editor-plan.md](video-editor-plan.md)를 따른다. 탐지, 추적, 컷, 합성, 드라이브 업로드는 아직 없다.

## 구성

| 경로 | 역할 |
|---|---|
| `frontend/` | React, TypeScript, Vite |
| `backend/` | FastAPI |
| `worker/` | 대기 중인 작업 워커 |
| `config/` | 드라이브 설정 예시. 실제 값은 커밋하지 않는다 |
| `docs/` | API와 화면 문서 |
| `schemas/` | 구간과 전환 JSON Schema |
| `samples/` | 로컬 테스트 영상 자리 |
| `scripts/benchmark.py` | 계획서 10장의 탐지 시간 추정 |

## 준비

- Python 3.12
- Node.js 22
- Docker Compose (컨테이너로 띄울 때)
- 선택: NVIDIA GPU와 Container Toolkit

FFmpeg와 탐지 모델은 이후 마일스톤에서 이미지에 넣는다.

## 설정

시크릿은 커밋하지 않는다. 예시는 빈 값만 있다.

```bash
cp .env.example .env
cp config/drive.example.yaml config/drive.yaml
chmod 600 config/drive.yaml
```

`.env`의 빈 칸은 필요할 때 채운다. 드라이브 API 키, OAuth 클라이언트 ID, 클라이언트 시크릿, 폴더 ID는 `config/drive.yaml`에만 둔다. 처음 계정 승인 뒤에 생기는 `config/drive_token.json`도 서버에만 남긴다. 두 파일 모두 git에서 빠져 있다.

`folder_id`가 비어 있으면 나중에 업로드는 드라이브 루트로 간다. `enabled`를 `false`로 두면 드라이브 연동을 끈다.

## 로컬 서버

터미널을 나눠 실행한다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt -r worker/requirements.txt
uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000
```

```bash
python worker/main.py
```

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 `http://127.0.0.1:5173` 을 연다. Vite가 `/videos`, `/jobs`, `/health`를 `http://127.0.0.1:8000`으로 넘긴다. API 문서는 `http://127.0.0.1:8000/docs` 이다.

워커는 큐를 소비하지 않고 대기만 한다. 탐지·작업·렌더 라우트는 `501`을 반환한다. 업로드·프레임·파일 제공은 동작한다.

## Docker Compose

저장소 루트에서:

```bash
docker compose up --build
```

- 프론트: `http://localhost:5173`
- API: `http://localhost:8000`
- Redis: `localhost:6379`

`config/`는 백엔드와 워커에 마운트된다. 영상용 named volume은 `media`다.

GPU를 쓰려면 호스트에 NVIDIA Container Toolkit을 설치하고, `docker-compose.yml`의 `worker` 서비스 안 디바이스 예약 주석을 해제한 뒤 다시 띄운다. 주석 상태에서는 CPU로만 기동한다.

## 검사

```bash
pip install -r requirements-dev.txt
ruff check backend worker scripts
ruff format --check backend worker scripts
pytest
```

```bash
cd frontend
npm run lint
npm run typecheck
npm run format:check
```

같은 검사가 `.github/workflows/ci.yml`에 있다.

추정 스크립트:

```bash
python scripts/benchmark.py
```

## 문서

- [API](docs/api.md), [OpenAPI](docs/openapi.yaml)
- [스타일](docs/design/style-guide.md), [와이어프레임](docs/design/wireframes.md), [구성요소](docs/design/components.md)
- [샘플 영상](samples/README.md)
