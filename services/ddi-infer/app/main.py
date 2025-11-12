import os
import json
from typing import Dict, Any, Optional

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import (
    DDI_Predictor,
    DEVICE,
    process_drug_info,
    create_prediction_batch,
)

app = FastAPI()

class PredictRequest(BaseModel):
    drugA: str
    drugB: str

# Globals initialized at startup
model = None
id_to_label: Dict[int, str] = {}
drug_metadata: Dict[str, Any] = {}
drug_name_to_id: Dict[str, str] = {}
images_dir: str = ""


def load_label_mapping(labels_json_path: str, num_classes: int) -> Dict[int, str]:
    # If a labels JSON exists, it can be either {'label_to_id': {...}} or {'id_to_label': {...}}
    if labels_json_path and os.path.exists(labels_json_path):
        with open(labels_json_path, 'r') as f:
            data = json.load(f)
        if 'id_to_label' in data and isinstance(data['id_to_label'], dict):
            # keys may be strings; normalize to int keys
            return {int(k): v for k, v in data['id_to_label'].items()}
        if 'label_to_id' in data and isinstance(data['label_to_id'], dict):
            l2i = data['label_to_id']
            return {int(v): k for k, v in l2i.items()}
        # Flat list/array possible
        if isinstance(data, list):
            return {i: str(x) for i, x in enumerate(data)}
    # Fallback: generic class names
    return {i: f"class_{i}" for i in range(num_classes)}


@app.get("/healthz")
def healthz():
    return {"status": "ok", "device": str(DEVICE)}


@app.on_event("startup")
def startup():
    global model, id_to_label, drug_metadata, drug_name_to_id, images_dir

    model_path = os.getenv("MODEL_PATH")
    drug_info_path = os.getenv("DRUG_INFO_PATH")
    images_dir = os.getenv("MOLECULES_IMAGES_DIR", "/models/images")
    labels_json = os.getenv("LABELS_JSON", "")

    if not model_path or not os.path.exists(model_path):
        raise RuntimeError("MODEL_PATH is missing or not found")
    if not drug_info_path or not os.path.exists(drug_info_path):
        raise RuntimeError("DRUG_INFO_PATH is missing or not found")

    # Load metadata and name lookup
    drug_metadata = process_drug_info(drug_info_path)
    # Build name->id map ensuring key is str and non-empty
    tmp_lookup: Dict[str, str] = {}
    for did, info in drug_metadata.items():
        if isinstance(info, dict):
            name = info.get('name')
            if isinstance(name, str) and name:
                tmp_lookup[name] = did
    drug_name_to_id = tmp_lookup

    # Instantiate model with NUM_CLASSES from env or labels
    # If LABELS_JSON provided, infer num_classes from there, otherwise require NUM_CLASSES env
    num_classes_env = os.getenv("NUM_CLASSES")
    if labels_json and os.path.exists(labels_json):
        # Temporarily load generic mapping to get length
        temp_map = load_label_mapping(labels_json, 0)
        if temp_map:
            num_classes = len(temp_map)
        else:
            if not num_classes_env:
                raise RuntimeError("Cannot infer NUM_CLASSES; provide LABELS_JSON or NUM_CLASSES env")
            num_classes = int(num_classes_env)
        id_to_label = load_label_mapping(labels_json, num_classes)
    else:
        if not num_classes_env:
            raise RuntimeError("NUM_CLASSES env is required when LABELS_JSON not provided")
        num_classes = int(num_classes_env)
        id_to_label = {i: f"class_{i}" for i in range(num_classes)}

    # Load checkpoint first to infer graph input feature dimension if available
    ckpt_raw = torch.load(model_path, map_location='cpu')
    if isinstance(ckpt_raw, dict):
        state_probe = ckpt_raw.get('model_state_dict', ckpt_raw.get('state_dict', ckpt_raw))
    else:
        state_probe = ckpt_raw
    graph_in_dim = None
    for k, v in state_probe.items():
        if k.endswith('graph_encoder.conv1.lin.weight') and hasattr(v, 'shape') and len(v.shape) == 2:
            graph_in_dim = v.shape[1]
            break
    if graph_in_dim:
        os.environ['GRAPH_INPUT_DIM_OVERRIDE'] = str(graph_in_dim)
    model = DDI_Predictor(num_classes=num_classes, graph_input_dim=graph_in_dim if isinstance(graph_in_dim, int) else None).to(DEVICE)

    # Load checkpoint robustly (reuse raw object loaded to CPU, move weights to DEVICE)
    ckpt = ckpt_raw
    if isinstance(ckpt, dict):
        state = ckpt.get('model_state_dict', ckpt.get('state_dict', ckpt))
        # if label_to_id saved, prefer it
        l2i = ckpt.get('label_to_id')
        if isinstance(l2i, dict) and not labels_json:
            id_to_label = {int(v): k for k, v in l2i.items()}
    else:
        state = ckpt

    # Strip DataParallel prefix if present
    from collections import OrderedDict
    if any(k.startswith('module.') for k in state.keys()):
        new_state = OrderedDict()
        for k, v in state.items():
            new_state[k.replace('module.', '', 1)] = v
        state = new_state

    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        print("[load] missing keys:", missing)
    if unexpected:
        print("[load] unexpected keys:", unexpected)

    model.eval()
    print("Model loaded and ready.")


@app.post("/predict")
def predict(req: PredictRequest):
    if model is None:
        raise HTTPException(status_code=500, detail="Model not initialized")
    try:
        batch = create_prediction_batch(req.drugA, req.drugB, drug_name_to_id, drug_metadata, images_dir)
        with torch.no_grad():
            logits = model(batch)
            probs = torch.softmax(logits, dim=1)[0]
            pred_id = int(torch.argmax(probs).item())
            pred_label = id_to_label.get(pred_id, f"class_{pred_id}")
            return {
                "predicted_label": pred_label,
                "confidence": float(probs[pred_id].item()),
                "probabilities": {id_to_label.get(i, f"class_{i}"): float(probs[i].item()) for i in range(len(probs))}
            }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"inference error: {e}")
