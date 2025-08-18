# MediDoc (Capstone)

A full‑stack medical document assistant:
- Upload prescriptions or medical documents to S3 and manage your uploads
- Maintain a personal medical profile
- Chat with an LLM assistant (Gemini or OpenAI‑compatible) enriched with your medical profile context
- Backend: FastAPI + SQLAlchemy
- Frontend: React (Vite) + Tailwind CSS


## Contents
- Overview
- Architecture
- Quick start
- Configuration (env vars)
- API summary
- Data model
- Troubleshooting


## Overview
MediDoc lets authenticated users upload documents (PNG/JPEG/PDF up to 5MB) to S3, keep a structured medical profile, and ask questions to an AI assistant. The assistant can optionally use your medical profile as context to tailor responses.


## Architecture
Repository layout:

- `backend/` FastAPI app, SQLAlchemy models, JWT auth, S3 integration, chat endpoint
  - `main.py` app entry (includes routers and CORS)
  - `core/config.py` typed settings via pydantic‑settings
  - `db/` engine, session, Base
  - `models/` SQLAlchemy entities (User, MedicalProfile, UploadedFile, Prescription)
  - `schemas/` Pydantic schemas for request/response models
  - `routes/` API routers: auth, files, extract, profile, chat
  - `utils/` security helpers, RAG utilities
- `frontend/` Vite + React SPA
  - `src/components/OnePageApp.jsx` main UI container
  - `src/components/Views.jsx` Uploads/Profile/Chat views
  - `src/services/api.js` Backend API client

On backend startup, database tables are created automatically if they don’t exist.


## Quick start
Prerequisites:
- Python 3.10+
- Node.js 18+ (recommended 20+)
- An AWS S3 bucket (for file uploads)
- An LLM provider (default Gemini) and credentials

### 1) Backend
1. Copy env template and fill values:
   - Copy `backend/.env.example` to `backend/.env`
2. Create and activate a virtualenv, then install deps:
   - Windows (PowerShell):
     ```powershell
     cd backend
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     pip install -r requirements.txt
     ```
3. Run the API:
   ```powershell
   # from backend directory
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Open API docs: http://localhost:8000/docs

Notes:
- Ensure `ALLOWED_ORIGINS` in backend `.env` includes your frontend dev URL(s) (e.g., http://localhost:5173 and your LAN IP for mobile testing).
- For local development without an external DB, use SQLite (example provided in `.env.example`).

### 2) Frontend
1. Create a frontend env file:
   - Copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE_URL` to your backend (e.g., http://localhost:8000)
2. Install deps and run dev server:
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
3. Open the app: http://localhost:5173


## Configuration (env vars)
### Backend (`backend/.env`)
Required core:
- `SECRET_KEY` – any random string used for JWT signing
- `DATABASE_URL` – SQLAlchemy URL (examples below)

CORS:
- `ALLOWED_ORIGINS` – JSON array of allowed origins (e.g., `["http://localhost:5173","http://192.168.0.10:5173"]`)

AWS S3:
- `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`

LLM (Chat):
- `LLM_PROVIDER` – `gemini` (default) | `lmstudio` | `openai-compatible`
- `LLM_API_KEY` – required for Gemini or Bearer‑based providers
- `LLM_MODEL` – e.g., `gemini-2.5-flash`
- `LLM_API_URL` – required for non‑Gemini providers (e.g., `http://localhost:1234/v1/chat/completions`)
- `LLM_MAX_TOKENS` – default 512
- `LLM_TEMPERATURE` – default 0.2
- `LLM_SYSTEM_PROMPT` – optional assistant system prompt

Database URL examples:
- SQLite (local dev): `sqlite:///./dev.db`
- MySQL (PyMySQL): `mysql+pymysql://user:password@host:3306/dbname`
- Postgres: `postgresql+psycopg2://user:password@host:5432/dbname`

### Frontend (`frontend/.env.local`)
- `VITE_API_BASE_URL` – e.g., `http://localhost:8000`
- Optional (only used as fallback when presign fails):
  - `VITE_S3_BUCKET`
  - `VITE_S3_REGION`


## API summary
All endpoints except registration and login require a Bearer token (JWT).

Auth
- POST `/auth/register` – JSON `{ name, email, password, age?, gender?, phone? }` → user
- POST `/auth/login` – form‑urlencoded `{ username: email, password }` → `{ access_token, token_type }`
- GET `/auth/me` – current user

Files
- POST `/files/upload` – multipart `file` (PNG/JPEG/PDF ≤ 5MB) → uploaded file record
- GET `/files/` – list current user’s files
- GET `/files/{file_id}/presign?download=true|false` – presigned URL to view/download

Extraction
- POST `/extract/extract/{file_id}` – placeholder extraction creates a `Prescription` entry

Medical Profile
- POST `/profile/medical-profile` – create profile (one per user)
- GET `/profile/medical-profile` – fetch profile
- PUT `/profile/medical-profile` – update profile

Chat
- POST `/chat/` – JSON `{ message, max_tokens?, temperature? }` → `{ reply, raw?, meta? }`
  - Provider selection via env (see LLM config). Gemini uses the Google endpoint (API key in query). Others use Bearer header to `LLM_API_URL`.
  - Automatically includes your medical profile as context when available.

Minimal examples (PowerShell):
```powershell
# Register
curl -Method POST -Uri http://localhost:8000/auth/register -Headers @{ 'Content-Type'='application/json' } -Body '{"name":"Alice","email":"alice@example.com","password":"password1"}'

# Login (note: form-url-encoded)
$resp = curl -Method POST -Uri http://localhost:8000/auth/login -Headers @{ 'Content-Type'='application/x-www-form-urlencoded' } -Body 'username=alice@example.com&password=password1'
$token = ($resp.Content | ConvertFrom-Json).access_token

# Me
curl -Method GET -Uri http://localhost:8000/auth/me -Headers @{ 'Authorization' = "Bearer $token" }

# Upload (adjust file path)
curl -Method POST -Uri http://localhost:8000/files/upload -Headers @{ 'Authorization' = "Bearer $token" } -Form @{ file = Get-Item .\sample.pdf }

# Chat
curl -Method POST -Uri http://localhost:8000/chat/ -Headers @{ 'Authorization' = "Bearer $token"; 'Content-Type'='application/json' } -Body '{"message":"Summarize my medical profile"}'
```


## Data model
- `User` – id, name, age, gender (enum: MALE/FEMALE/OTHER), email (unique), phone, hashed_password, timestamps
- `MedicalProfile` – 1:1 with `User`; multiple text fields (present conditions, medications, history, etc.)
- `UploadedFile` – id, user_id, filename, file_type, upload_date, status, extracted_data; S3 URL property
- `Prescription` – id, user_id, file_id, extracted_fields (placeholder), extraction_date


## Troubleshooting
- 401 Unauthorized: Ensure you pass `Authorization: Bearer <access_token>`; re‑login if expired
- CORS blocked: Add your frontend origin(s) to `ALLOWED_ORIGINS` in `backend/.env`
- Upload fails:
  - Only PNG/JPEG/PDF are allowed and max size is 5MB (magic‑number validated)
  - Confirm S3 credentials, bucket name, and region
  - Ensure the bucket exists and the IAM user has `s3:PutObject`, `s3:GetObject`, `s3:HeadObject`
- Presign 404: The object may not exist in S3; check upload logs and bucket
- Chat errors:
  - Gemini: set `LLM_API_KEY` and (optionally) `LLM_MODEL` (default `gemini-2.5-flash`)
  - Non‑Gemini: set `LLM_API_URL` and `LLM_API_KEY`; choose correct payload type (`/v1/chat/completions` or `/completions`)
- Mobile LAN testing:
  - Set `VITE_API_BASE_URL` to your backend’s LAN IP (e.g., `http://192.168.x.x:8000`)
  - Add that origin to `ALLOWED_ORIGINS`


## Deployment notes
- Set strong production values in `backend/.env` and never commit secrets.
- Configure CORS `ALLOWED_ORIGINS` with your production domain(s).
- Use a managed database (RDS/Cloud SQL/etc.) and set `DATABASE_URL` accordingly.
- Behind a reverse proxy, ensure the backend is started with a production ASGI server (e.g., `uvicorn`/`gunicorn` + `uvicorn.workers.UvicornWorker`).
- Serve the frontend static build via your platform (e.g., `npm run build` → deploy `frontend/dist`).


## Notes
- Tables are auto‑created on backend startup; no migrations are bundled
- Keep secrets out of version control; commit only `.env.example`
- Frontend confines scrolling to views and uses a dynamic `--vh` fix for mobile browsers
