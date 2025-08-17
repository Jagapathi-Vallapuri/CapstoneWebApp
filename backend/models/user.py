from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from db.base import Base
import enum

class Gender(enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)  
    age = Column(Integer)
    gender = Column(Enum(Gender), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=False)  
    phone = Column(String(20), nullable=True)  
    hashed_password = Column(String(255), nullable=False) 
    is_active = Column(Boolean(), default=True)
    created_at = Column(DateTime(), default=datetime.utcnow)
    updated_at = Column(DateTime(), default=datetime.utcnow, onupdate=datetime.utcnow)
    medical_profile = relationship("MedicalProfile", uselist=False, back_populates="user")
    files = relationship("UploadedFile", back_populates="user")