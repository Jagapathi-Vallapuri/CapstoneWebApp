from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, files, extraction, medical_profile, chat
import logging
from db.base import Base
from db.session import engine
from db.migrations import ensure_medical_profiles_schema, ensure_uploaded_files_schema, ensure_prescriptions_schema, ensure_medication_schedules_schema
from core.config import settings
import os
import socket

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Capstone Project v1.0")

allow_origins = list(settings.ALLOWED_ORIGINS or [])


try:
    auto_flag = os.getenv("AUTO_ALLOW_FRONTEND_ORIGINS", "1").lower() in ("1", "true", "yes")
except Exception:
    auto_flag = True

if auto_flag:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
    except Exception:
        primary_ip = None

    frontend_port = os.getenv("FRONTEND_DEV_PORT", "5173")
    candidates = [f"http://localhost:{frontend_port}", f"http://127.0.0.1:{frontend_port}"]
    if primary_ip:
        candidates.append(f"http://{primary_ip}:{frontend_port}")

    # Add candidates if not already present
    for c in candidates:
        if c not in allow_origins:
            allow_origins.append(c)

logging.info(f"Allowed CORS origins: {allow_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(extraction.router, prefix="/extract", tags=["extraction"])
app.include_router(medical_profile.router, prefix="/profile", tags=["profile"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])

@app.on_event("startup")
def startup_event():
    logging.info("Creating database tables (if not exist)...")
    Base.metadata.create_all(bind=engine)
    ensure_medical_profiles_schema(engine)
    ensure_uploaded_files_schema(engine)
    ensure_prescriptions_schema(engine)
    ensure_medication_schedules_schema(engine)

@app.get("/")
def read_root():
    return {"text": "Hello, World!"}

@app.get('/health')
def health_check():
    return {"status": "healthy"}