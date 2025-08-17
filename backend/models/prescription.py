from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from db.base import Base

class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    file_id = Column(String(36), ForeignKey("uploaded_files.id"))
    extracted_fields = Column(Text)
    extraction_date = Column(DateTime, default=datetime.utcnow)
    file = relationship("UploadedFile", back_populates="prescription")