from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, Boolean, Integer
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from db.base import Base

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        Index('ix_uploaded_files_user_id', 'user_id'),
        Index('ix_uploaded_files_status', 'status'),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"))
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    display_name = Column(String(255), nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending")
    accepted = Column(Boolean, default=False)
    extracted_data = Column(Text)
    last_retry_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)
    user = relationship("User", back_populates="files")
    prescription = relationship("Prescription", uselist=False, back_populates="file")
    
    @property
    def s3_url(self):
        from core.config import settings
        return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{self.filename}"

    # Convenience helpers for extracted_data JSON
    def get_extracted_json(self):
        import json
        raw_obj: object = self.extracted_data  # avoid static typing confusion with Column[str]
        try:
            s = raw_obj if isinstance(raw_obj, str) else ''
            return json.loads(s or '{}')
        except Exception:
            return {}

    def set_extracted_json(self, data):
        import json
        self.extracted_data = json.dumps(data or {})