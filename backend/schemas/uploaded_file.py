from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UploadedFileBase(BaseModel):
    filename: str
    file_type: Optional[str]
    status: Optional[str]
    extracted_data: Optional[str]


class UploadedFileCreate(UploadedFileBase):
    pass


class UploadedFileOut(UploadedFileBase):
    id: str
    user_id: str
    upload_date: datetime
    s3_url: Optional[str]

    class Config:
        orm_mode = True
