from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
import uuid
from db.base import Base
from datetime import datetime

class MedicalProfile(Base):
    __tablename__ = "medical_profiles"
    __table_args__ = (
        Index('ix_medical_profiles_user_id', 'user_id'),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    present_conditions = Column(Text)
    diagnosed_conditions = Column(Text)
    medications_past = Column(Text)
    medications_current = Column(Text)
    allergies = Column(Text)
    medical_history = Column(Text)
    family_history = Column(Text)
    surgeries = Column(Text)
    immunizations = Column(Text)
    lifestyle_factors = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="medical_profile")