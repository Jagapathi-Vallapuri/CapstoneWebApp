from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from db.base import Base


class LLMLog(Base):
    __tablename__ = "llm_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    file_id = Column(String(36), ForeignKey("uploaded_files.id"), nullable=True)
    provider = Column(String(50), nullable=True)
    model = Column(String(100), nullable=True)
    route = Column(String(50), nullable=True)  # e.g., 'extraction', 'chat'
    url = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    file = relationship("UploadedFile")
