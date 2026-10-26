FROM python:3.12-slim

# GPU draft: switch this base to an NVIDIA CUDA image when detection runs on GPU.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

CMD ["python", "main.py"]
