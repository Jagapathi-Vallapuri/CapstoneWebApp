from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from db.base import Base

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending")  
    extracted_data = Column(Text)
    user = relationship("User", back_populates="files")
    prescription = relationship("Prescription", uselist=False, back_populates="file")
    
    @property
    def s3_url(self):
        from core.config import settings
        return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{self.filename}"