from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from models.user import User
from models.medical_profile import MedicalProfile
from schemas.medical_profile import MedicalProfileCreate, MedicalProfileOut
from utils.security import get_current_user

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
        **medical_profile.dict()
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
    
    # Update the medical profile fields
    for field, value in medical_profile.dict().items():
        setattr(db_medical_profile, field, value)
    
    db.commit()
    db.refresh(db_medical_profile)
    return db_medical_profile
