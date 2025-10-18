from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from db.base import Base

class Prescription(Base):
    __tablename__ = "prescriptions"
    __table_args__ = (
        Index('ix_prescriptions_user_id', 'user_id'),
        Index('ix_prescriptions_file_id', 'file_id'),
        Index('ix_prescriptions_accepted', 'accepted'),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    file_id = Column(String(36), ForeignKey("uploaded_files.id"))
    extracted_fields = Column(Text)
    extraction_date = Column(DateTime, default=datetime.utcnow)
    accepted = Column(Boolean, default=False)
    accepted_at = Column(DateTime, nullable=True)
    file = relationship("UploadedFile", back_populates="prescription")