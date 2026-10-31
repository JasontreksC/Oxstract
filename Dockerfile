# One image for the web app and the worker. CPU only: no CUDA base, no NVENC.

# Export YOLO11n to ONNX once. PyTorch lives only in this throwaway stage.
FROM python:3.12-slim AS model
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    ultralytics onnx onnxslim onnxruntime \
  && pip uninstall -y opencv-python \
  && pip install --no-cache-dir opencv-python-headless
WORKDIR /model
RUN YOLO_CONFIG_DIR=/tmp/yolo yolo export model=yolo11n.pt format=onnx imgsz=640

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
# ffmpeg: probing, proxies, cuts and concat. fonts-noto-cjk: Korean text cards (drawtext).
RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=model /model/yolo11n.onnx ./models/yolo11n.onnx
COPY --from=web /web/dist ./static

ENV MEDIA_ROOT=/data \
  FRONTEND_DIST=/app/static \
  DETECT_MODEL=/app/models/yolo11n.onnx \
  PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
