FROM pytorch/pytorch:2.6.0-cuda12.6-cudnn9-runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip

RUN grep -v -E "pyg-lib|torch-geometric|torch-scatter|torch-sparse|torch-cluster|torch-spline-conv|^torch==" /app/requirements.txt > /app/requirements_filtered.txt && \
    pip install -r /app/requirements_filtered.txt


RUN pip install pyg-lib torch-scatter torch-sparse torch-cluster torch-spline-conv \
    -f https://data.pyg.org/whl/torch-2.6.0+cu126.html || echo "[WARN] Some PyG wheels missing for torch 2.6 CUDA 12.6; consider building from source."
RUN pip install torch-geometric

COPY app/ /app/app/

COPY assets/model/ /models/
COPY assets/data/ /models/
COPY assets/images/ /models/images/

ENV MODEL_PATH=/models/best_ddi_predictor.pth \
    DRUG_INFO_PATH=/models/drug_info.json \
    MOLECULES_IMAGES_DIR=/models/images \
    LABELS_JSON=/models/labels.json \
    BIOMED_BERT_MODEL=dmis-lab/biobert-v1.1 \
    MAX_SEQ_LEN=256 \
    IMAGE_SIZE=224 \
    HF_HUB_DISABLE_TELEMETRY=1

EXPOSE 8000

RUN python -c "from torchvision.models import resnet50, ResNet50_Weights; resnet50(weights=ResNet50_Weights.IMAGENET1K_V1)" || echo "[WARN] ResNet50 weights prefetch failed"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]