from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional


class MedicationDetail(BaseModel):
    name: str = Field(..., description="Medicine name")
    dose: Optional[str] = Field(None, description="Dosage, e.g., '500 mg'")
    frequency: Optional[str] = Field(None, description="Frequency, e.g., '2 times a day'")


class ExtractionPayload(BaseModel):
    medicines: List[str] = Field(default_factory=list, description="List of medicine names mentioned")
    medications_details: List[MedicationDetail] = Field(default_factory=list, description="Structured details for each medicine")
    additional_info: Optional[str] = Field(None, description="Any other notable details from the prescription")
    # Optional medical profile fields that the LLM can fill if present in the doc
    present_conditions: Optional[str] = Field(None, description="Current/present conditions")
    diagnosed_conditions: Optional[str] = Field(None, description="Diagnosed conditions")
    medications_past: Optional[str] = Field(None, description="Past medications")
    allergies: Optional[str] = Field(None, description="Known allergies")
    medical_history: Optional[str] = Field(None, description="Medical history summary")
    family_history: Optional[str] = Field(None, description="Family medical history")
    surgeries: Optional[str] = Field(None, description="Surgeries/procedures")
    immunizations: Optional[str] = Field(None, description="Immunizations/vaccines")
    lifestyle_factors: Optional[str] = Field(None, description="Lifestyle factors like smoking, alcohol, exercise")
