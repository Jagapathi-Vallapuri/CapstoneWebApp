import os
import json
from typing import Dict, Any, Tuple, List

import torch
import torch.nn as nn
from torchvision import transforms
from torchvision.models import resnet50, ResNet50_Weights
from transformers import AutoTokenizer, AutoModel
from PIL import Image

from rdkit import Chem
from rdkit.Chem import Descriptors

from torch_geometric.data import Data, Batch
from torch_geometric.nn import GATConv, global_max_pool


# ------------------------------
# Config
# ------------------------------
BIOMED_BERT_MODEL = os.getenv("BIOMED_BERT_MODEL", "dmis-lab/biobert-v1.1")
MAX_SEQ_LEN = int(os.getenv("MAX_SEQ_LEN", "256"))
IMAGE_SIZE = int(os.getenv("IMAGE_SIZE", "224"))

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ------------------------------
# Global singletons (tokenizer, transforms)
# ------------------------------

tokenizer = AutoTokenizer.from_pretrained(BIOMED_BERT_MODEL)

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

image_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
])

# ------------------------------
# Drug metadata
# ------------------------------

def process_formula(string: str) -> str:
    return string or ""

def process_drug_info(file_path: str) -> Dict[str, Dict[str, Any]]:
    with open(file_path, 'r') as f:
        drug_dict = json.load(f)

    for drug_id, drug_info in drug_dict.items():
        desc = drug_info.get('description')
        if isinstance(desc, dict):
            parts: List[str] = []
            for v in desc.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, dict):
                    parts.extend([vv for vv in v.values() if isinstance(vv, str)])
            drug_info['description'] = ' '.join(parts)
        elif desc is None:
            drug_info['description'] = ''

        if 'formula' in drug_info:
            try:
                drug_info['formula'] = process_formula(drug_info['formula'])
            except Exception:
                pass
    return drug_dict

# ------------------------------
# Text features
# ------------------------------

def get_drug_text_and_tokenize(drug_id: str, drug_metadata: Dict[str, Any]) -> Dict[str, torch.Tensor]:
    text = drug_metadata.get(drug_id, {}).get('description', '')
    tokens = tokenizer(
        text,
        return_tensors='pt',
        padding='max_length',
        truncation=True,
        max_length=MAX_SEQ_LEN
    )
    return {k: v.squeeze(0) for k, v in tokens.items()}

# ------------------------------
# Graph features (robust one-hots with clamping)
# ------------------------------

# C, N, O, F, P, S, Cl, Br, I, H, Other
_ATOMS = [1, 6, 7, 8, 9, 15, 16, 17, 35, 53]
_ATOM_INDEX = {z: i for i, z in enumerate(_ATOMS)}
_ATOM_DIM = len(_ATOMS) + 1  # +1 other

def one_hot_bounded(val: int, size: int) -> torch.Tensor:
    idx = val
    if idx < 0:
        idx = 0
    if idx >= size:
        idx = size - 1
    return torch.eye(size)[idx]

def atom_one_hot(atomic_num: int) -> torch.Tensor:
    idx = _ATOM_INDEX.get(atomic_num, len(_ATOMS))
    return torch.eye(_ATOM_DIM)[idx]

# Define dimensions for simple, robust feature set
_DEGREE_DIM = 6      # 0..5+
_H_DIM = 5           # 0..4+
_VALENCE_DIM = 6     # 0..5+
_RADICAL_DIM = 3     # 0..2+
_HYBRID_DIM = 7      # rdchem.HybridizationType upto 6-ish; clamp
_AROM_DIM = 2
_RING_DIM = 2
_CHIRAL_DIM = 4      # rdchem.ChiralType upto 3; clamp

GRAPH_INPUT_DIM = _ATOM_DIM + _DEGREE_DIM + _H_DIM + _VALENCE_DIM + _VALENCE_DIM + _VALENCE_DIM + _RADICAL_DIM + _HYBRID_DIM + _AROM_DIM + _Ring_DIM if False else (_ATOM_DIM + _DEGREE_DIM + _H_DIM + _VALENCE_DIM + _VALENCE_DIM + _VALENCE_DIM + _RADICAL_DIM + _HYBRID_DIM + _AROM_DIM + _RING_DIM + _CHIRAL_DIM)
# Fix variable naming typo
_Ring_DIM = None  # unused guard

# Correct calculation
GRAPH_INPUT_DIM = _ATOM_DIM + _DEGREE_DIM + _H_DIM + _VALENCE_DIM + _VALENCE_DIM + _VALENCE_DIM + _RADICAL_DIM + _HYBRID_DIM + _AROM_DIM + _RING_DIM + _CHIRAL_DIM if '_RING_DIM' in globals() else (_ATOM_DIM + _DEGREE_DIM + _H_DIM + _VALENCE_DIM + _VALENCE_DIM + _VALENCE_DIM + _RADICAL_DIM + _HYBRID_DIM + _AROM_DIM + 2 + _CHIRAL_DIM)

# Define ring dim explicitly
_RING_DIM = 2
GRAPH_INPUT_DIM = _ATOM_DIM + _DEGREE_DIM + _H_DIM + _VALENCE_DIM + _VALENCE_DIM + _VALENCE_DIM + _RADICAL_DIM + _HYBRID_DIM + _AROM_DIM + _RING_DIM + _CHIRAL_DIM

DEFAULT_X = torch.zeros(1, GRAPH_INPUT_DIM)
DEFAULT_EDGE_ATTR = torch.zeros(1, 5)
DEFAULT_EDGE_INDEX = torch.LongTensor([[0], [0]])

def atom_feature(atom: Chem.rdchem.Atom) -> torch.Tensor:
    z = atom.GetAtomicNum()
    deg = atom.GetDegree()
    num_h = atom.GetNumImplicitHs()
    ev = atom.GetExplicitValence()
    iv = atom.GetImplicitValence()
    tv = atom.GetTotalValence()
    rad = atom.GetNumRadicalElectrons()
    hyb = int(atom.GetHybridization())
    arom = 1 if atom.GetIsAromatic() else 0
    in_ring = 1 if atom.IsInRing() else 0
    chiral = int(atom.GetChiralTag())

    feats = [
        atom_one_hot(z),
        one_hot_bounded(deg, _DEGREE_DIM),
        one_hot_bounded(num_h, _H_DIM),
        one_hot_bounded(ev, _VALENCE_DIM),
        one_hot_bounded(iv, _VALENCE_DIM),
        one_hot_bounded(tv, _VALENCE_DIM),
        one_hot_bounded(rad, _RADICAL_DIM),
        one_hot_bounded(hyb, _HYBRID_DIM),
        torch.tensor([arom], dtype=torch.float32),
        torch.tensor([in_ring], dtype=torch.float32),
        one_hot_bounded(chiral, _CHIRAL_DIM),
    ]
    return torch.cat(feats).float()

def load_and_featurize_graph(drug_id: str, drug_metadata: Dict[str, Any]) -> Data:
    smiles = drug_metadata.get(drug_id, {}).get('smiles', None)
    if not smiles:
        return Data(edge_index=DEFAULT_EDGE_INDEX, x=DEFAULT_X, edge_attr=DEFAULT_EDGE_ATTR)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return Data(edge_index=DEFAULT_EDGE_INDEX, x=DEFAULT_X, edge_attr=DEFAULT_EDGE_ATTR)

    x_list: List[torch.Tensor] = []
    for a in mol.GetAtoms():
        try:
            x_list.append(atom_feature(a))
        except Exception:
            x_list.append(torch.zeros(GRAPH_INPUT_DIM))

    row, col, bond_features = [], [], []
    for b in mol.GetBonds():
        i = b.GetBeginAtomIdx(); j = b.GetEndAtomIdx()
        stereo = int(b.GetStereo())
        feats = [
            float(b.GetBondTypeAsDouble()),
            float(stereo),
            float(b.GetIsConjugated()),
            float(b.GetIsAromatic()),
            float(b.IsInRing()),
        ]
        row.extend([i, j]); col.extend([j, i])
        bond_features.extend([feats, feats])

    if not row or not x_list:
        return Data(edge_index=DEFAULT_EDGE_INDEX, x=DEFAULT_X, edge_attr=DEFAULT_EDGE_ATTR)

    edge_index = torch.LongTensor([row, col])
    edge_attr = torch.FloatTensor(bond_features)
    return Data(edge_index=edge_index, x=torch.stack(x_list), edge_attr=edge_attr)

# ------------------------------
# Image features
# ------------------------------

def load_and_transform_image(drug_id: str, images_dir: str) -> torch.Tensor:
    cleaned = drug_id.split('::')[-1]
    image_path = os.path.join(images_dir, f"{cleaned}.png")
    zero = torch.zeros(3, IMAGE_SIZE, IMAGE_SIZE, dtype=torch.float32)
    if not os.path.exists(image_path):
        return zero
    try:
        img = Image.open(image_path).convert('RGB')
        return image_transform(img)
    except Exception:
        return zero

# ------------------------------
# Encoders and model
# ------------------------------
TEXT_DIM = 256
GRAPH_DIM = 256
IMAGE_DIM = 256
GAT_HEADS = 4

class TextEncoder(nn.Module):
    def __init__(self, output_dim: int = TEXT_DIM):
        super().__init__()
        self.bert = AutoModel.from_pretrained(BIOMED_BERT_MODEL)
        hidden = self.bert.config.hidden_size
        self.projection_head = nn.Sequential(
            nn.Linear(hidden, output_dim * 2),
            nn.GELU(),
            nn.Linear(output_dim * 2, output_dim)
        )
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask, return_dict=True)
        cls = out.pooler_output
        return self.projection_head(cls)

class GATEncoder(nn.Module):
    def __init__(self, input_dim: int = GRAPH_INPUT_DIM, output_dim: int = GRAPH_DIM):
        super().__init__()
        hidden = output_dim // GAT_HEADS
        self.conv1 = GATConv(input_dim, hidden, heads=GAT_HEADS, dropout=0.2)
        self.conv2 = GATConv(hidden * GAT_HEADS, hidden, heads=GAT_HEADS, dropout=0.2)
        self.conv3 = GATConv(hidden * GAT_HEADS, output_dim, heads=1, concat=False, dropout=0.2)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
    def forward(self, data: Batch) -> torch.Tensor:
        x, edge_index, batch = data.x, data.edge_index, data.batch
        # Pad/trim if mismatch
        if x.size(1) != self.conv1.in_channels:
            if x.size(1) > self.conv1.in_channels:
                x = x[:, :self.conv1.in_channels]
            else:
                pad = torch.zeros(x.size(0), self.conv1.in_channels - x.size(1), device=x.device)
                x = torch.cat([x, pad], dim=1)
        x = self.dropout(self.relu(self.conv1(x, edge_index)))
        x = self.dropout(self.relu(self.conv2(x, edge_index)))
        x = self.conv3(x, edge_index)
        x = global_max_pool(x, batch)
        return x

class ImageEncoder(nn.Module):
    def __init__(self, output_dim: int = IMAGE_DIM):
        super().__init__()
        self.resnet = resnet50(weights=ResNet50_Weights.IMAGENET1K_V1)
        for name, p in self.resnet.named_parameters():
            if 'layer4' not in name and 'fc' not in name:
                p.requires_grad = False
            else:
                p.requires_grad = True
        in_feats = self.resnet.fc.in_features
        self.resnet.fc = nn.Sequential(
            nn.Linear(in_feats, output_dim * 2),
            nn.GELU(),
            nn.Linear(output_dim * 2, output_dim)
        )
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.resnet(x)

class DDI_Predictor(nn.Module):
    def __init__(self, num_classes: int, graph_input_dim: int | None = None):
        """Fusion predictor.

        Args:
            num_classes: number of interaction classes.
            graph_input_dim: override for GATEncoder input feature dimension (useful when
                loading checkpoints trained with a different atom feature set).
        """
        super().__init__()
        self.text_encoder = TextEncoder(output_dim=TEXT_DIM)
        effective_graph_dim: int = GRAPH_INPUT_DIM if graph_input_dim is None else int(graph_input_dim)
        self.graph_encoder = GATEncoder(input_dim=effective_graph_dim, output_dim=GRAPH_DIM)
        self.image_encoder = ImageEncoder(output_dim=IMAGE_DIM)
        self.SINGLE_DRUG_DIM = TEXT_DIM + GRAPH_DIM + IMAGE_DIM
        self.shared_projection = nn.Sequential(
            nn.Linear(self.SINGLE_DRUG_DIM, self.SINGLE_DRUG_DIM),
            nn.GELU(),
            nn.Dropout(0.3)
        )
        agg = self.SINGLE_DRUG_DIM
        self.fusion_classifier = nn.Sequential(
            nn.Linear(agg, agg // 2),
            nn.LayerNorm(agg // 2),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(agg // 2, agg // 4),
            nn.LayerNorm(agg // 4),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(agg // 4, num_classes)
        )
    def forward(self, batch: Dict[str, Any]) -> torch.Tensor:
        v_t1 = self.text_encoder(batch['d1_input_ids'], batch['d1_attention_mask'])
        v_g1 = self.graph_encoder(batch['d1_graph_batch'])
        v_i1 = self.image_encoder(batch['d1_image'])
        v_d1 = torch.cat([v_t1, v_g1, v_i1], dim=1)

        v_t2 = self.text_encoder(batch['d2_input_ids'], batch['d2_attention_mask'])
        v_g2 = self.graph_encoder(batch['d2_graph_batch'])
        v_i2 = self.image_encoder(batch['d2_image'])
        v_d2 = torch.cat([v_t2, v_g2, v_i2], dim=1)

        p_d1 = self.shared_projection(v_d1)
        p_d2 = self.shared_projection(v_d2)
        fusion = p_d1 + p_d2
        logits = self.fusion_classifier(fusion)
        return logits

# ------------------------------
# Inference helpers
# ------------------------------

def get_drug_features_for_name(drug_name: str, drug_name_to_id: Dict[str, str], drug_metadata: Dict[str, Any], images_dir: str) -> Tuple[torch.Tensor, torch.Tensor, Data, torch.Tensor]:
    drug_id = drug_name_to_id.get(drug_name)
    if not drug_id:
        raise ValueError(f"Drug name '{drug_name}' not found in metadata lookup")
    text = get_drug_text_and_tokenize(drug_id, drug_metadata)
    input_ids = text['input_ids']
    attention_mask = text['attention_mask']
    graph = load_and_featurize_graph(drug_id, drug_metadata)
    img = load_and_transform_image(drug_id, images_dir)
    return input_ids, attention_mask, graph, img.unsqueeze(0)

def create_prediction_batch(drug_A: str, drug_B: str, drug_name_to_id: Dict[str, str], drug_metadata: Dict[str, Any], images_dir: str) -> Dict[str, Any]:
    id_A, mask_A, graph_A, img_A = get_drug_features_for_name(drug_A, drug_name_to_id, drug_metadata, images_dir)
    id_B, mask_B, graph_B, img_B = get_drug_features_for_name(drug_B, drug_name_to_id, drug_metadata, images_dir)
    d1_graph_batch = Batch.from_data_list([graph_A]).to(DEVICE)
    d2_graph_batch = Batch.from_data_list([graph_B]).to(DEVICE)
    batch = {
        'd1_input_ids': id_A.unsqueeze(0).to(DEVICE),
        'd1_attention_mask': mask_A.unsqueeze(0).to(DEVICE),
        'd1_graph_batch': d1_graph_batch,
        'd1_image': img_A.to(DEVICE),
        'd2_input_ids': id_B.unsqueeze(0).to(DEVICE),
        'd2_attention_mask': mask_B.unsqueeze(0).to(DEVICE),
        'd2_graph_batch': d2_graph_batch,
        'd2_image': img_B.to(DEVICE),
        'labels': torch.tensor([0], dtype=torch.long).to(DEVICE)
    }
    return batch
