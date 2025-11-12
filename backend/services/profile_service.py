import json
import logging
from typing import Any, Dict, Optional, cast
from sqlalchemy.orm import Session
from models.prescription import Prescription
from models.medical_profile import MedicalProfile
from datetime import datetime

PROFILE_FIELD_NAMES = [
    'present_conditions','diagnosed_conditions','medications_past','allergies',
    'medical_history','family_history','surgeries','immunizations','lifestyle_factors'
]

def recompute_profile_after_delete(db: Session, user_id: str, removed_file_id: str, prev_parsed: Dict[str, Any]) -> None:
    """Recompute MedicalProfile fields and medications_current from remaining accepted prescriptions.

    - Aggregate unique medicines across remaining accepted prescriptions to set medications_current.
    - For profile fields, choose the most recent non-empty candidate from remaining accepted prescriptions.
    - If no candidate exists for a field, clear it only when the current value matches the removed file's value.
    """
    try:
        remaining = db.query(Prescription).filter(
            Prescription.user_id == user_id,
            Prescription.accepted == True
        ).all()
        meds_union: list[str] = []
        seen = set()
        profile_candidates: Dict[str, Any] = {}

        def pres_sort_key(p: Prescription):
            at = getattr(p, 'accepted_at', None)
            ed = getattr(p, 'extraction_date', None)
            return ((at or datetime.min), (ed or datetime.min))

        remaining_sorted = sorted(remaining, key=pres_sort_key, reverse=True)
        for p in remaining_sorted:
            try:
                raw = cast(Optional[str], getattr(p, 'extracted_fields', None))
                fields = json.loads(raw or '{}') if raw else {}
            except Exception:
                fields = {}
            lp = fields.get('llm_parsed') if isinstance(fields, dict) else None
            if not isinstance(lp, dict):
                continue
            # Aggregate meds
            try:
                for m in (lp.get('medicines') or []):
                    if isinstance(m, str):
                        mm = m.strip()
                        if mm and mm.lower() not in seen:
                            seen.add(mm.lower())
                            meds_union.append(mm)
            except Exception:
                pass
            # Profile candidates (first encountered from most recent)
            for fname in PROFILE_FIELD_NAMES:
                if fname in profile_candidates:
                    continue
                try:
                    val = lp.get(fname)
                    if isinstance(val, str) and val.strip():
                        profile_candidates[fname] = val.strip()
                except Exception:
                    continue

        profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == user_id).first()
        if not profile:
            return

        # medications_current from union
        if meds_union:
            setattr(profile, 'medications_current', ", ".join(meds_union))
        else:
            try:
                prev_meds = []
                for m in (prev_parsed.get('medicines') or []):
                    if isinstance(m, str) and m.strip():
                        prev_meds.append(m.strip())
                prev_summary = ", ".join(prev_meds) if prev_meds else None
                cur_val = getattr(profile, 'medications_current', None)
                if prev_summary and cur_val and cur_val.strip() == prev_summary:
                    setattr(profile, 'medications_current', None)
            except Exception:
                pass

        # Profile fields
        for fname in PROFILE_FIELD_NAMES:
            cand = profile_candidates.get(fname)
            if cand:
                try:
                    setattr(profile, fname, cand)
                except Exception:
                    pass
            else:
                try:
                    prev_val = prev_parsed.get(fname)
                    cur_val = getattr(profile, fname, None)
                    if isinstance(prev_val, str) and prev_val.strip() and isinstance(cur_val, str) and cur_val.strip() == prev_val.strip():
                        setattr(profile, fname, None)
                except Exception:
                    pass
    except Exception:
        # Non-fatal; do not block outer operation
        logging.warning("Profile recompute failed during delete workflow", exc_info=True)
