
from fastapi import FastAPI, UploadFile, File, Response
from app.craft_infer import detect_text
import cv2
import numpy as np
import torch
from craft_pytorch.craft import CRAFT
from pathlib import Path

# Optional: enable CUDA if available later
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

app = FastAPI()

# Load model at startup
net = None
@app.on_event("startup")
def load_model():
    """Load CRAFT weights handling DataParallel 'module.' prefixes gracefully."""
    global net
    net = CRAFT()
    weights_path = Path(__file__).resolve().parent.parent / "weights" / "craft_mlt_25k.pth"
    # Load raw checkpoint
    checkpoint = torch.load(str(weights_path), map_location="cpu")
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        state_dict = checkpoint
    # Strip 'module.' if present (from DataParallel training)
    cleaned = {}
    for k, v in state_dict.items():
        new_key = k[7:] if k.startswith("module.") else k
        cleaned[new_key] = v
    missing, unexpected = net.load_state_dict(cleaned, strict=False)
    if missing:
        print(f"[CRAFT] Warning: missing keys: {missing}")
    if unexpected:
        print(f"[CRAFT] Warning: unexpected keys: {unexpected}")
    net.to(DEVICE).eval()


def check_file_type(file: UploadFile):
    if not file.filename or "." not in file.filename:
        return {"error": "Invalid file type"}
    extension = file.filename.rsplit(".", 1)[-1].lower()
    if extension not in ("jpg", "jpeg", "png"):
        return {"error": "Invalid file type"}
    return None


@app.post("/detect/{mode}/")
async def detect_objects(mode: str, file: UploadFile = File(...)):
    error = check_file_type(file)
    if error:
        return error

    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        return {"error": "Could not decode image"}

    if mode == "boxes":
        boxes = detect_text(net, image, return_type="boxes")
        return {"boxes": [box.tolist() for box in boxes]}
    elif mode == "image":
        img_with_boxes = detect_text(net, image, return_type="image")
        # Ensure img_with_boxes is a NumPy ndarray
        if not isinstance(img_with_boxes, np.ndarray):
            img_with_boxes = np.array(img_with_boxes)
        _, img_encoded = cv2.imencode('.jpg', img_with_boxes)
        return Response(content=img_encoded.tobytes(), media_type="image/jpeg")
    else:
        return {"error": "Invalid mode. Use 'boxes' or 'image'"}