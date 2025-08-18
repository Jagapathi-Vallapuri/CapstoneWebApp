from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class PrescriptionBase(BaseModel):
    extracted_fields: Optional[str]

class PrescriptionCreate(PrescriptionBase):
    pass

class PrescriptionOut(PrescriptionBase):
    id: str
    user_id: str
    file_id: str
    extraction_date: datetime

    model_config = ConfigDict(from_attributes=True)
