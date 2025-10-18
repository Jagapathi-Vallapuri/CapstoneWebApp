from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from db.base import Base


class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"
    __table_args__ = (
        Index('ix_medication_schedules_user_id', 'user_id'),
        Index('ix_medication_schedules_file_id', 'file_id'),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    file_id = Column(String(36), ForeignKey("uploaded_files.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    dose = Column(String(255), nullable=True)
    frequency = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    file = relationship("UploadedFile")
