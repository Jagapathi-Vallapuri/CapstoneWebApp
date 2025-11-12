FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
	CUDNN_BENCHMARK=0

ARG PYTHON_VERSION=3.11

WORKDIR /app

# Minimal system packages for Python + OpenCV runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
	python${PYTHON_VERSION} python3-distutils python3-venv python3-pip \
	libglib2.0-0 libsm6 libxext6 libxrender1 libgl1 curl ca-certificates && \
	ln -s /usr/bin/python${PYTHON_VERSION} /usr/bin/python && \
	python -m pip install --upgrade pip && \
	rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8000/docs >/dev/null || exit 1

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

