# CRAFT Text Detection API

FastAPI service exposing a CRAFT text detection endpoint.

## Build & Run (Docker)

```powershell
# Build image
docker build -t detection:gpu .

# Run (GPU with CUDA if host has nvidia-container-toolkit installed)
docker run --gpus all -p 8100:8000 detection:gpu

## Endpoints

POST /detect/boxes/  -> JSON list of bounding boxes
POST /detect/image/  -> JPEG with boxes drawn

```powershell
curl.exe -X POST -F "file=@test_images/image1.jpg" http://localhost:8100/detect/boxes/

curl.exe -X POST -F "file=@test_images/image1.jpg" http://localhost:8100/detect/image/ --output result.jpg
```

## Weights
Place `craft_mlt_25k.pth` in `weights/` (already included). If replacing, ensure filename matches or adjust path in `app/main.py`.

## Notes
- Base image: PyTorch CUDA 12.1 runtime (compatible with many GPUs & driver 12.9).
- Requirements pinned for reproducibility.
- Adjust `DEVICE` logic in `app/main.py` if you want to force CPU.
