from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class UploadedFileBase(BaseModel):
    filename: str
    file_type: Optional[str]
    status: Optional[str]
    extracted_data: Optional[str]
    display_name: Optional[str]


class UploadedFileCreate(UploadedFileBase):
    pass


class UploadedFileOut(UploadedFileBase):
    id: str
    user_id: str
    upload_date: datetime
    s3_url: Optional[str]
    last_retry_at: Optional[datetime] = None
    retry_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)
