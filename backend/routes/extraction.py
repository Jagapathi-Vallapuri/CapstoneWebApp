from fastapi import APIRouter, Depends, HTTPException
from utils.security import get_current_user
from sqlalchemy.orm import Session
from db.session import get_db
from models.uploaded_file import UploadedFile
from models.prescription import Prescription
from schemas.prescription import PrescriptionOut
import logging
import re

router = APIRouter()

@router.post("/{file_id}", response_model=PrescriptionOut)
def extract_information(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    try:
        file_id = re.sub(r'[^a-zA-Z0-9-]', '', file_id)
        db_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not db_file:
            raise HTTPException(status_code=404, detail={"error": "File not found"})
        if db_file.user_id != current_user.id:
            raise HTTPException(status_code=403, detail={"error": "Not authorized to extract this file."})
        prescription = Prescription(
            user_id=db_file.user_id,
            file_id=db_file.id,
            extracted_fields="{}"
        )
        db.add(prescription)
        db.commit()
        db.refresh(prescription)
        return prescription
    except HTTPException as he:
        logging.error(f"Extraction error: {he.detail}")
        raise
    except Exception as e:
        logging.error(f"Extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": f"Extraction failed: {str(e)}"})