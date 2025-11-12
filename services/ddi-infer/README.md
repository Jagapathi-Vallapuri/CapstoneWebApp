# DDI Inference Service (GPU)

A FastAPI microservice that loads your trained DDI model (.pth) and exposes a simple REST API to predict drug-drug interactions by drug names. This image is CUDA-enabled for GPU inference.

## Requirements

- Docker with NVIDIA runtime, NVIDIA drivers on host
- Trained model file (e.g., `best_ddi_predictor.pth`)
- `drug_info.json` and optional molecule images directory (PNG files named `{DrugID}.png`)
- Label mapping either via `LABELS_JSON` or `NUM_CLASSES` env var

## Build (GPU)

```powershell
# Run from services/ddi-infer
docker build -t ddi-infer:gpu .
```

## Run (GPU)

```powershell
# Replace host paths accordingly
$MODEL="C:\\path\\to\\best_ddi_predictor.pth"
$INFO ="C:\\path\\to\\drug_info.json"
$IMGS ="C:\\path\\to\\images"   # optional
$LABS ="C:\\path\\to\\labels.json" # optional; else set NUM_CLASSES

# Either provide LABELS_JSON or NUM_CLASSES
# $env:NUM_CLASSES=3

docker run --rm -p 8000:8000 --gpus all `
  -e MODEL_PATH="/mnt/model/best_ddi_predictor.pth" `
  -e DRUG_INFO_PATH="/mnt/model/drug_info.json" `
  -e MOLECULES_IMAGES_DIR="/mnt/images" `
  -e LABELS_JSON="/mnt/model/labels.json" `
  -e NUM_CLASSES="3" `
  -v "$MODEL:/mnt/model/best_ddi_predictor.pth:ro" `
  -v "$INFO:/mnt/model/drug_info.json:ro" `
  -v "$IMGS:/mnt/images:ro" `
  -v "$LABS:/mnt/model/labels.json:ro" `
  ddi-infer:gpu
```

## Test

```powershell
# Health
curl http://localhost:8000/healthz

# Predict
curl -X POST http://localhost:8000/predict `
  -H "Content-Type: application/json" `
  -d '{"drugA": "Lisinopril", "drugB": "Ibuprofen"}'
```

## Environment Variables

- `MODEL_PATH` (required): Path inside container to the .pth file
- `DRUG_INFO_PATH` (required): Path inside container to drug_info.json
- `MOLECULES_IMAGES_DIR` (optional): Folder with molecule PNGs
- `LABELS_JSON` (optional): JSON mapping for labels. Supported shapes:
  - `{ "id_to_label": {"0": "Synergism", "1": "Antagonism", ... } }`
  - `{ "label_to_id": {"Synergism": 0, "Antagonism": 1, ... } }`
  - `["Synergism", "Antagonism", ...]`
- `NUM_CLASSES` (required if `LABELS_JSON` not provided): integer
- `BIOMED_BERT_MODEL` (optional): HF model id for tokenizer/encoder (default `dmis-lab/biobert-v1.1`)
- `MAX_SEQ_LEN` (optional): tokenizer max length (default 256)
- `IMAGE_SIZE` (optional): image size (default 224)

## Notes

- Torch Geometric wheels are installed to match torch==2.3.0 with CUDA 11.8.
- RDKit is installed via `rdkit-pypi`.
- If ResNet weights download is blocked, consider pre-downloading or set `weights=None` in `ImageEncoder`.
- If your checkpoint contains `label_to_id`, the service will prefer it when `LABELS_JSON` isn't provided.
