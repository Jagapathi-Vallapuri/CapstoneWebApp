from pydantic import BaseModel, EmailStr
from pydantic import ConfigDict
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    name: str
    age: Optional[int]
    gender: Optional[str]
    email: EmailStr
    phone: Optional[str]

class UserCreate(UserBase):
    password: str

class UserOut(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Pydantic v2: use from_attributes
    model_config = ConfigDict(from_attributes=True)