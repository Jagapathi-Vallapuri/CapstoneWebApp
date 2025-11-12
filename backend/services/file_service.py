import json
import logging
from typing import Any, Dict, Optional, cast
from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.uploaded_file import UploadedFile
from models.prescription import Prescription
from models.medication_schedule import MedicationSchedule
from .profile_service import recompute_profile_after_delete


def delete_file_and_related(db: Session, file: UploadedFile) -> None:
    """Delete DB rows (schedules, prescriptions, file) and recompute profile.

    Steps:
    - Gather previous parsed payload for the file (for undo logic)
    - Delete medication schedules referencing the file
    - Delete prescriptions referencing the file
    - Recompute profile fields and medications_current from remaining accepted prescriptions
    - Delete the file record and commit
    """
    try:
        prev_parsed: Dict[str, Any] = {}
        try:
            cur_pres = db.query(Prescription).filter(Prescription.file_id == file.id).first()
            if cur_pres:
                try:
                    cur_raw = cast(Optional[str], getattr(cur_pres, 'extracted_fields', None))
                    cur_fields = json.loads(cur_raw or '{}') if cur_raw else {}
                except Exception:
                    cur_fields = {}
                p = (cur_fields.get('llm_parsed') or {}) if isinstance(cur_fields, dict) else {}
                prev_parsed = p if isinstance(p, dict) else {}
        except Exception:
            prev_parsed = {}

        # Delete schedules
        try:
            db.query(MedicationSchedule).filter(MedicationSchedule.file_id == file.id).delete(synchronize_session=False)
        except Exception:
            pass
        # Delete prescriptions
        db.query(Prescription).filter(Prescription.file_id == file.id).delete(synchronize_session=False)

        # Recompute profile
        recompute_profile_after_delete(db, str(file.user_id), str(file.id), prev_parsed)

        # Delete file row
        db.delete(file)
        db.commit()
    except Exception as e:
        logging.error(f"DB delete failed: {str(e)}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to delete from database")
