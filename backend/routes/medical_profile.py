from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from db.session import get_db
from models.user import User
from models.medical_profile import MedicalProfile
from schemas.medical_profile import MedicalProfileCreate, MedicalProfileOut
from utils.security import get_current_user
from typing import Dict, Any

router = APIRouter()



@router.post("/medical-profile", response_model=MedicalProfileOut)
def create_medical_profile(
    medical_profile: MedicalProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_medical_profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == current_user.id).first()
    if db_medical_profile:
        raise HTTPException(status_code=400, detail="Medical profile already exists for this user")
    
    new_medical_profile = MedicalProfile(
        user_id=current_user.id,
        **medical_profile.model_dump()
    )
    db.add(new_medical_profile)
    db.commit()
    db.refresh(new_medical_profile)
    return new_medical_profile

@router.get("/medical-profile", response_model=MedicalProfileOut)
def get_medical_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    medical_profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == current_user.id).first()
    if not medical_profile:
        raise HTTPException(status_code=404, detail="Medical profile not found")
    return medical_profile

@router.put("/medical-profile", response_model=MedicalProfileOut)
def update_medical_profile(
    medical_profile: MedicalProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_medical_profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == current_user.id).first()
    if not db_medical_profile:
        raise HTTPException(status_code=404, detail="Medical profile not found")
    
    for field, value in medical_profile.model_dump().items():
        setattr(db_medical_profile, field, value)
    
    db.commit()
    db.refresh(db_medical_profile)
    return db_medical_profile

@router.patch("/medical-profile", response_model=MedicalProfileOut)
def patch_medical_profile(
    medical_profile: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_medical_profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == current_user.id).first()
    if not db_medical_profile:
        raise HTTPException(status_code=404, detail="Medical profile not found")

    # Only allow updates to known fields
    allowed_fields = {
        "present_conditions",
        "diagnosed_conditions",
        "medications_past",
        "medications_current",
        "allergies",
        "medical_history",
        "family_history",
        "surgeries",
        "immunizations",
        "lifestyle_factors",
    }
    update_data = {k: v for k, v in (medical_profile or {}).items() if k in allowed_fields}
    if not update_data:
        return db_medical_profile

    for field, value in update_data.items():
        setattr(db_medical_profile, field, value)

    db.commit()
    db.refresh(db_medical_profile)
    return db_medical_profile
