from pydantic import BaseModel, ConfigDict
from typing import Optional

class MedicalProfileBase(BaseModel):
    present_conditions: Optional[str]
    diagnosed_conditions: Optional[str]
    medications_past: Optional[str]
    medications_current: Optional[str]
    allergies: Optional[str]
    medical_history: Optional[str]
    family_history: Optional[str]
    surgeries: Optional[str]
    immunizations: Optional[str]
    lifestyle_factors: Optional[str]

class MedicalProfileCreate(MedicalProfileBase):
    pass

class MedicalProfileOut(MedicalProfileBase):
    id: str
    user_id: str

    model_config = ConfigDict(from_attributes=True)
