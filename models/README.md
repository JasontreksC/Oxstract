# 탐지 모델

서버는 `models/yolo11n.onnx`(또는 `DETECT_MODEL` 경로)를 ONNX Runtime으로 CPU에서 돌린다. 실행에는 PyTorch가 필요 없다. 모델 파일은 커밋하지 않는다.

Docker 이미지는 빌드 중에 이 파일을 만든다. 로컬 개발에서는 한 번만 아래처럼 만든다. 내보내기에만 PyTorch가 필요하므로 따로 만든 가상환경에서 하고, 끝나면 지워도 된다.

```bash
python3.12 -m venv /tmp/yolo-export
/tmp/yolo-export/bin/pip install --extra-index-url https://download.pytorch.org/whl/cpu \
  ultralytics onnx onnxslim onnxruntime
# 화면이 없는 서버라면 libGL 오류를 피하려고 headless OpenCV로 바꾼다
/tmp/yolo-export/bin/pip uninstall -y opencv-python
/tmp/yolo-export/bin/pip install opencv-python-headless
cd models
/tmp/yolo-export/bin/yolo export model=yolo11n.pt format=onnx imgsz=640
rm yolo11n.pt
```

모델이 없으면 탐지 박스만 꺼지고(`POST /api/videos/{id}/detect`가 `503`), 화면에서 직접 드래그해 대상을 고르는 기능은 그대로 쓸 수 있다.

YOLO11은 Ultralytics의 AGPL-3.0 모델이다. 혼자 쓰는 셀프호스팅에는 문제가 없지만, 이 앱을 다른 사람에게 서비스하거나 배포할 때는 라이선스 조건을 확인한다.
