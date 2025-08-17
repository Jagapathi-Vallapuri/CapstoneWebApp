from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, files, extraction, medical_profile
import logging
from db.base import Base
from db.session import engine
from core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Capstone Project v1.0")


# CORS middleware
# Configure CORS from settings; fall back to no origins if not set
allow_origins = settings.ALLOWED_ORIGINS or []
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log full exception for server-side debugging, but return a generic message to clients
    logging.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(extraction.router, prefix="/extract", tags=["extraction"])
app.include_router(medical_profile.router, prefix="/profile", tags=["profile"])

@app.on_event("startup")
def startup_event():
    logging.info("Creating database tables (if not exist)...")
    Base.metadata.create_all(bind=engine)

@app.get("/")
def read_root():
    return {"text": "Hello, World!"}

@app.get('/health')
def health_check():
    return {"status": "healthy"}