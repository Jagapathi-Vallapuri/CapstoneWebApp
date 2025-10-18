from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Form
from utils.security import get_current_user
from sqlalchemy.orm import Session
from db.session import get_db
from models.uploaded_file import UploadedFile
from schemas.uploaded_file import UploadedFileOut
from typing import List, Dict, Any, Optional, cast
from core.config import settings

import os
import requests
import io
import json
from models.prescription import Prescription
from schemas.extraction import ExtractionPayload
from sqlalchemy.orm import Session as OrmSession
from urllib.parse import urlparse, parse_qsl, urlunparse, urlencode
import boto3
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse
import re
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.prompts import render_prompt
import time
from utils.llm_logger import log_llm_event
from models.medication_schedule import MedicationSchedule
from models.medical_profile import MedicalProfile
from datetime import datetime, timedelta

router = APIRouter()

def _recompute_profile_after_delete(db: Session, user_id: str, removed_file_id: str, prev_parsed: Dict[str, Any]) -> None:
    """Recompute MedicalProfile fields and medications_current from remaining accepted prescriptions.

    - Aggregate unique medicines across remaining accepted prescriptions to set medications_current.
    - For profile fields, choose the most recent non-empty candidate from remaining accepted prescriptions.
    - If no candidate exists for a field, clear it only when the current value matches the removed file's value.
    """
    try:
        remaining = db.query(Prescription).filter(
            Prescription.user_id == user_id,
            Prescription.accepted == True
        ).all()
        meds_union: list[str] = []
        seen = set()
        profile_candidates: Dict[str, Any] = {}

        def pres_sort_key(p: Prescription):
            at = getattr(p, 'accepted_at', None)
            ed = getattr(p, 'extraction_date', None)
            return ((at or datetime.min), (ed or datetime.min))

        remaining_sorted = sorted(remaining, key=pres_sort_key, reverse=True)
        for p in remaining_sorted:
            try:
                raw = cast(Optional[str], getattr(p, 'extracted_fields', None))
                fields = json.loads(raw or '{}') if raw else {}
            except Exception:
                fields = {}
            lp = fields.get('llm_parsed') if isinstance(fields, dict) else None
            if not isinstance(lp, dict):
                continue
            # Aggregate meds
            try:
                for m in (lp.get('medicines') or []):
                    if isinstance(m, str):
                        mm = m.strip()
                        if mm and mm.lower() not in seen:
                            seen.add(mm.lower())
                            meds_union.append(mm)
            except Exception:
                pass
            # Profile candidates (first encountered from most recent)
            for fname in ['present_conditions','diagnosed_conditions','medications_past','allergies','medical_history','family_history','surgeries','immunizations','lifestyle_factors']:
                if fname in profile_candidates:
                    continue
                try:
                    val = lp.get(fname)
                    if isinstance(val, str) and val.strip():
                        profile_candidates[fname] = val.strip()
                except Exception:
                    continue

        profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == user_id).first()
        if not profile:
            return

        # medications_current from union
        if meds_union:
            setattr(profile, 'medications_current', ", ".join(meds_union))
        else:
            try:
                prev_meds = []
                for m in (prev_parsed.get('medicines') or []):
                    if isinstance(m, str) and m.strip():
                        prev_meds.append(m.strip())
                prev_summary = ", ".join(prev_meds) if prev_meds else None
                cur_val = getattr(profile, 'medications_current', None)
                if prev_summary and cur_val and cur_val.strip() == prev_summary:
                    setattr(profile, 'medications_current', None)
            except Exception:
                pass

        # Profile fields
        for fname in ['present_conditions','diagnosed_conditions','medications_past','allergies','medical_history','family_history','surgeries','immunizations','lifestyle_factors']:
            cand = profile_candidates.get(fname)
            if cand:
                try:
                    setattr(profile, fname, cand)
                except Exception:
                    pass
            else:
                try:
                    prev_val = prev_parsed.get(fname)
                    cur_val = getattr(profile, fname, None)
                    if isinstance(prev_val, str) and prev_val.strip() and isinstance(cur_val, str) and cur_val.strip() == prev_val.strip():
                        setattr(profile, fname, None)
                except Exception:
                    pass
    except Exception:
        # Non-fatal; do not block delete
        pass

@router.post("/upload", response_model=UploadedFileOut)
def upload_file(
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    try:
        contents = file.file.read()
        size = len(contents)
        if size > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail={"error": "File too large (max 5MB)."})

        magic = contents[:4]
        is_jpeg = magic[:3] == b'\xff\xd8\xff'
        is_png = magic == b'\x89PNG'
        is_pdf = magic == b'%PDF'
        if not (is_jpeg or is_png or is_pdf):
            raise HTTPException(status_code=400, detail={"error": "Invalid file type (magic number check failed)."})

        # Sanitize filename and set per-user prefix
        safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', file.filename or "uploaded_file")
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        user_prefix = f"users/{current_user.id}/"
        s3_key_original = f"{user_prefix}{unique_filename}"

        # Upload original bytes to S3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION
        )
        try:
            s3.upload_fileobj(
                io.BytesIO(contents),
                settings.S3_BUCKET,
                s3_key_original,
                ExtraArgs={"ContentType": file.content_type}
            )
        except Exception as e:
            logging.error(f"S3 upload failed: {str(e)}")
            raise HTTPException(status_code=500, detail={"error": f"S3 upload failed: {str(e)}"})

        s3_url = f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{s3_key_original}"
        presigned_url = None
        try:
            presigned_url = s3.generate_presigned_url('get_object', Params={"Bucket": settings.S3_BUCKET, "Key": s3_key_original}, ExpiresIn=900)
        except Exception:
            presigned_url = None

        # Determine a friendly display name for UI
        friendly_name = None
        try:
            if display_name and display_name.strip():
                friendly_name = display_name.strip()
            else:
                # Compute an index per user: count existing files + 1
                total = db.query(UploadedFile).filter(UploadedFile.user_id == current_user.id).count()
                # Derive extension from original filename
                root, ext = os.path.splitext(file.filename or '')
                ext = (ext or '').lower()
                friendly_name = f"Document {total + 1}{ext}"
        except Exception:
            # Fallback to original filename base or 'Document'
            root, ext = os.path.splitext(file.filename or '')
            friendly_name = (root or 'Document') + (ext or '')

        db_file = UploadedFile(
            user_id=current_user.id,
            filename=s3_key_original,
            file_type=file.content_type,
            status="uploaded",
            display_name=friendly_name
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        detection_url = settings.detection_url or 'http://localhost:8001'
        boxes: Optional[list] = None
        llm_result = None
        llm_parsed = None

        def call_detection():
            try:
                ct = file.content_type or "application/octet-stream"
                resp = requests.post(
                    f"{detection_url}/detect/boxes/",
                    files={"file": ("file", io.BytesIO(contents), ct)},
                    timeout=20,
                )
                if resp.ok:
                    data = resp.json()
                    return data.get('boxes')
            except Exception as e:
                logging.warning(f"Detection call failed: {str(e)}")
            return None

        def call_llm():
            result: Dict[str, Any] = {"llm_result": None, "llm_parsed": None}
            try:
                model = settings.LLM_MODEL or 'gemini-2.5-flash'
                api_key = settings.LLM_API_KEY
                llm_url = settings.LLM_API_URL
                provider = settings.LLM_PROVIDER or 'gemini'
                system_prompt = settings.LLM_SYSTEM_PROMPT or (
                    "You are a medical prescription extraction assistant. Extract: "
                    "- medicine names and structured medication details (name, dose, frequency), "
                    "- any additional noteworthy info, and "
                    "- any medical profile data present (present_conditions, diagnosed_conditions, medications_past, allergies, medical_history, family_history, surgeries, immunizations, lifestyle_factors). "
                    "Respond ONLY with valid JSON."
                )

                image_url_for_model = presigned_url or s3_url
                schema = ExtractionPayload.model_json_schema()
                # Prefer externalized prompt template if available
                rendered = None
                try:
                    rendered = render_prompt(
                        'extraction_system.txt',
                        {
                            'IMAGE_URL': image_url_for_model,
                            'JSON_SCHEMA': json.dumps(schema, ensure_ascii=False),
                        }
                    )
                except Exception:
                    rendered = None

                combined = rendered or (
                    f"{system_prompt}\n\n"
                    f"A prescription image has been uploaded. Access it here (short-lived): {image_url_for_model}.\n"
                    f"Return STRICTLY a JSON object that conforms to this JSON Schema (no explanations, no markdown):\n"
                    f"{json.dumps(schema, ensure_ascii=False)}\n\n"
                    f"Rules:\n"
                    f"- Only output valid JSON (UTF-8), no code fences.\n"
                    f"- If a field is unknown, use an empty list for arrays or omit the optional field.\n"
                )

                if provider.lower() == 'gemini':
                    if not llm_url:
                        llm_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    if not api_key:
                        logging.warning('Gemini API key missing; skipping LLM extraction')
                        return result
                    parsed = urlparse(llm_url)
                    q = dict(parse_qsl(parsed.query))
                    q['key'] = api_key
                    llm_url = urlunparse(parsed._replace(query=urlencode(q)))
                    payload = {
                        "contents": [{"role": "user", "parts": [{"text": combined}]}],
                        "generationConfig": {"temperature": 0.0, "maxOutputTokens": settings.LLM_MAX_TOKENS or 512}
                    }
                    t0 = time.time()
                    r = requests.post(llm_url, json=payload, timeout=30)
                    duration_ms = int((time.time() - t0) * 1000)
                    if r.ok:
                        resp_data = r.json()
                        # Log raw provider response to file
                        try:
                            log_llm_event('extraction.gemini.response', {
                                "status": r.status_code,
                                "duration_ms": duration_ms,
                                "data": resp_data,
                            })
                        except Exception:
                            pass
                        cands = resp_data.get('candidates')
                        if isinstance(cands, list) and cands:
                            content = cands[0].get('content') or {}
                            parts = content.get('parts') or []
                            texts = [p.get('text', '') for p in parts if isinstance(p, dict) and 'text' in p]
                            llm_reply = "".join(texts).strip()
                            result['llm_result'] = llm_reply
                            try:
                                content = llm_reply
                                # Remove markdown code fences if present
                                if content.startswith('```'):
                                    content = content.strip()
                                    if content.startswith('```') and content.endswith('```'):
                                        content = content[3:-3].strip()
                                    if content.lower().startswith('json'):
                                        content = content[4:].lstrip('\n').lstrip()
                                # Extract the first JSON object substring
                                start = content.find('{')
                                end = content.rfind('}')
                                if start != -1 and end != -1 and end > start:
                                    content = content[start:end+1]
                                parsed_obj = json.loads(content)
                                # Validate/normalize against Pydantic schema
                                payload = ExtractionPayload.model_validate(parsed_obj)
                                result['llm_parsed'] = json.loads(payload.model_dump_json())
                            except Exception:
                                pass
                    else:
                        try:
                            log_llm_event('extraction.gemini.error', {
                                "status": r.status_code,
                                "body": getattr(r, 'text', None),
                            })
                        except Exception:
                            pass
                else:
                    if not llm_url or not api_key:
                        try:
                            log_llm_event('extraction.llm.skip', {"reason": "missing url/key"})
                        except Exception:
                            pass
                        return result
                    headers = {'Authorization': f'Bearer {api_key}'}
                    payload = {"input": combined}
                    r = requests.post(llm_url, json=payload, headers=headers, timeout=30)
                    if r.ok:
                        result['llm_result'] = r.text
                        try:
                            log_llm_event('extraction.llm.response', {
                                "status": r.status_code,
                                "body": r.text,
                            })
                        except Exception:
                            pass
                        try:
                            content = r.text
                            if content.startswith('```'):
                                content = content.strip()
                                if content.startswith('```') and content.endswith('```'):
                                    content = content[3:-3].strip()
                                if content.lower().startswith('json'):
                                    content = content[4:].lstrip('\n').lstrip()
                            start = content.find('{')
                            end = content.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                content = content[start:end+1]
                            parsed_obj = json.loads(content)
                            payload = ExtractionPayload.model_validate(parsed_obj)
                            result['llm_parsed'] = json.loads(payload.model_dump_json())
                        except Exception:
                            pass
                    else:
                        try:
                            log_llm_event('extraction.llm.error', {
                                "status": r.status_code,
                                "body": getattr(r, 'text', None),
                            })
                        except Exception:
                            pass
            except Exception as e:
                try:
                    log_llm_event('extraction.llm.error', {"error": str(e)})
                except Exception:
                    pass
            return result

        # Run detection and LLM concurrently
        try:
            with ThreadPoolExecutor(max_workers=2) as ex:
                futs = {
                    ex.submit(call_detection): 'detection',
                    ex.submit(call_llm): 'llm',
                }
                for fut in as_completed(futs):
                    name = futs.get(fut)
                    try:
                        res = fut.result()
                        if name == 'detection':
                            boxes = res
                        elif name == 'llm' and isinstance(res, dict):
                            llm_result = res.get('llm_result')
                            llm_parsed = res.get('llm_parsed')
                    except Exception as e:
                        logging.warning(f"Concurrent task {name} failed: {str(e)}")

            # Ensure llm_parsed aligns with our schema if present
            normalized_llm = None
            if isinstance(llm_parsed, dict):
                try:
                    payload = ExtractionPayload.model_validate(llm_parsed)
                    normalized_llm = json.loads(payload.model_dump_json())
                except Exception:
                    normalized_llm = llm_parsed

            extracted_payload = {
                "boxes": boxes,
                "original_s3": s3_url,
                "llm_result": llm_result,
                "llm_parsed": normalized_llm,
            }

            prescription = Prescription(
                user_id=db_file.user_id,
                file_id=db_file.id,
                extracted_fields=json.dumps(extracted_payload)
            )
            db.add(prescription)
            db.commit()
            db.refresh(prescription)
        except Exception as e:
            logging.error(f"Failed to run concurrent tasks or create prescription record: {str(e)}")
            try:
                db.rollback()
            except Exception:
                pass

        try:
            # Set to awaiting_review so frontend can prompt user to accept
            setattr(db_file, 'status', 'awaiting_review')
            setattr(db_file, 'extracted_data', json.dumps(extracted_payload))
            db.commit()
            db.refresh(db_file)
        except Exception:
            # If previous transaction failed, ensure we can proceed
            try:
                db.rollback()
            except Exception:
                pass

        return db_file
    except HTTPException as he:
        logging.error(f"File upload error: {he.detail}")
        raise
    except Exception as e:
        logging.error(f"File upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail={"error": f"File upload failed: {str(e)}"})

@router.get("/", response_model=List[UploadedFileOut])
def get_files(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    files = db.query(UploadedFile).filter(UploadedFile.user_id == current_user.id).all()
    return files


@router.get("/{file_id}/presign")
def presign_file(
    file_id: str,
    download: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ensure file exists and belongs to current user
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file or file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION
    )

    params = {"Bucket": settings.S3_BUCKET, "Key": file.filename}
    try:
        # ensure the object actually exists in S3 before generating a presigned URL
        try:
            s3.head_object(Bucket=settings.S3_BUCKET, Key=file.filename)
        except ClientError as ce:
            err_code = getattr(ce, 'response', {}).get('Error', {}).get('Code')
            logging.warning(f"S3 head_object failed for key={file.filename}: {err_code}")
            # NoSuchKey or 404-like responses
            raise HTTPException(status_code=404, detail="Object not found in S3")

        original = None
        if '_' in file.filename:
            original = '_'.join(file.filename.split('_')[1:])

        previewable = False
        try:
            ct = (file.file_type or '').lower()
            if ct.startswith('image/') or ct == 'application/pdf':
                previewable = True
        except Exception:
            previewable = False

        if original:
            if download:
                params["ResponseContentDisposition"] = f'attachment; filename="{original}"'
            else:
                if previewable:
                    params["ResponseContentDisposition"] = f'inline; filename="{original}"'
                else:
                    params["ResponseContentDisposition"] = f'attachment; filename="{original}"'

        url = s3.generate_presigned_url('get_object', Params=params, ExpiresIn=900)
        return JSONResponse({"presigned_url": url, "expires_in": 900})
    except ClientError as e:
        logging.error(f"Failed to generate presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate presigned URL")


@router.get("/{file_id}/extraction")
def get_extraction(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ensure file exists and belongs to current user
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file or file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        raw = cast(Optional[str], getattr(file, 'extracted_data', None))
        data = json.loads(raw or '{}')
    except Exception:
        data = {}
    return {
        "status": file.status,
        "extracted": data,
        "accepted": bool(getattr(file, 'accepted', (file.status or '').lower() == 'accepted'))
    }


@router.get("/schedule")
def get_medication_schedule(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    entries = db.query(MedicationSchedule).filter(MedicationSchedule.user_id == current_user.id).order_by(MedicationSchedule.created_at.desc()).all()
    # Return a lightweight DTO
    return [
        {
            "id": e.id,
            "name": e.name,
            "dose": e.dose,
            "frequency": e.frequency,
            "file_id": e.file_id,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.post("/{file_id}/extraction/accept")
def accept_extraction(
    file_id: str,
    body: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ensure file exists and belongs to current user
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file or file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    # Load current extracted_data
    try:
        raw = cast(Optional[str], getattr(file, 'extracted_data', None))
        extracted = json.loads(raw or '{}')
    except Exception:
        extracted = {}

    # If user provided a corrected payload, validate against schema and store it
    if body and isinstance(body, dict):
        incoming = body.get('payload')
        if incoming is not None:
            try:
                payload = ExtractionPayload.model_validate(incoming)
                normalized = json.loads(payload.model_dump_json())
                extracted["llm_parsed"] = normalized
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    # Persist back to UploadedFile and linked Prescription
    try:
        setattr(file, 'status', 'accepted')
        if hasattr(file, 'accepted'):
            setattr(file, 'accepted', True)
        setattr(file, 'extracted_data', json.dumps(extracted))

        # Update linked prescription if exists
        pres = db.query(Prescription).filter(Prescription.file_id == file.id).first()
        if pres:
            try:
                pres_raw = cast(Optional[str], getattr(pres, 'extracted_fields', None))
                pres_fields = json.loads(pres_raw or '{}')
            except Exception:
                pres_fields = {}
            pres_fields.update(extracted or {})
            setattr(pres, 'extracted_fields', json.dumps(pres_fields))
            if hasattr(pres, 'accepted'):
                setattr(pres, 'accepted', True)
            if hasattr(pres, 'accepted_at'):
                from datetime import datetime
                setattr(pres, 'accepted_at', datetime.utcnow())

        # Also update medical profile and medication schedule if llm_parsed present
        try:
            parsed = extracted.get('llm_parsed') if isinstance(extracted, dict) else None
            if isinstance(parsed, dict):
                # normalize via schema (defensive)
                payload = ExtractionPayload.model_validate(parsed)
                meds = payload.medicines or []
                details = payload.medications_details or []
                # Create or update medical profile fields
                profile = db.query(MedicalProfile).filter(MedicalProfile.user_id == file.user_id).first()
                if not profile:
                    profile = MedicalProfile(user_id=file.user_id)
                    db.add(profile)
                # Apply non-empty fields from payload
                field_map = [
                    'present_conditions', 'diagnosed_conditions', 'medications_past', 'allergies',
                    'medical_history', 'family_history', 'surgeries', 'immunizations', 'lifestyle_factors'
                ]
                for fname in field_map:
                    try:
                        val = getattr(payload, fname, None)
                        if val is not None and str(val).strip() != '':
                            setattr(profile, fname, str(val).strip())
                    except Exception:
                        pass
                # Update medications_current summary text on profile
                summary = ", ".join(meds) if meds else None
                if summary:
                    setattr(profile, 'medications_current', summary)
                # Replace schedule entries for this file
                try:
                    db.query(MedicationSchedule).filter(MedicationSchedule.user_id == file.user_id, MedicationSchedule.file_id == file.id).delete(synchronize_session=False)
                except Exception:
                    pass
                for d in details:
                    try:
                        entry = MedicationSchedule(
                            user_id=file.user_id,
                            file_id=file.id,
                            name=d.name,
                            dose=d.dose,
                            frequency=d.frequency,
                        )
                        db.add(entry)
                    except Exception:
                        continue
        except Exception:
            # non-fatal
            pass

        db.commit()
        db.refresh(file)
    except Exception as e:
        logging.error(f"Failed to accept extraction: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to accept extraction")

    return {"ok": True, "status": file.status}


@router.delete("/{file_id}")
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """Delete a user's uploaded document from S3 and related SQL rows.

    Steps:
    - Ensure file exists and belongs to current user
    - Delete object from S3 (ignore if already missing)
    - Delete related Prescription row(s) then UploadedFile
    - Commit and return ok
    """
    # ensure file exists and belongs to current user
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file or file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    # Attempt S3 delete first so we don't orphan DB if S3 deletion fails
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
        try:
            s3.delete_object(Bucket=settings.S3_BUCKET, Key=file.filename)
        except ClientError as ce:
            code = getattr(ce, 'response', {}).get('Error', {}).get('Code')
            # Treat NoSuchKey as non-fatal
            if str(code) not in ("NoSuchKey", "404"):
                logging.error(f"S3 delete_object failed for key={file.filename}: {code}")
                raise HTTPException(status_code=500, detail="Failed to delete from S3")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected S3 error during delete: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete from S3")

    # Delete related DB rows
    try:
        # Capture the existing prescription payload for this file (for potential undo logic)
        prev_parsed = {}
        try:
            cur_pres = db.query(Prescription).filter(Prescription.file_id == file.id).first()
            if cur_pres:
                try:
                    cur_raw = cast(Optional[str], getattr(cur_pres, 'extracted_fields', None))
                    cur_fields = json.loads(cur_raw or '{}') if cur_raw else {}
                except Exception:
                    cur_fields = {}
                prev_parsed = (cur_fields.get('llm_parsed') or {}) if isinstance(cur_fields, dict) else {}
                if not isinstance(prev_parsed, dict):
                    prev_parsed = {}
        except Exception:
            prev_parsed = {}

        # Remove medication schedule entries linked to this file
        try:
            db.query(MedicationSchedule).filter(MedicationSchedule.file_id == file.id).delete(synchronize_session=False)
        except Exception:
            pass
        # Remove prescriptions linked to this file
        db.query(Prescription).filter(Prescription.file_id == file.id).delete(synchronize_session=False)

        # Recompute user profile derived data from remaining accepted prescriptions
        _recompute_profile_after_delete(db, str(file.user_id), str(file.id), prev_parsed)

        # Finally remove the file record itself and commit
        db.delete(file)
        db.commit()
    except Exception as e:
        logging.error(f"DB delete failed: {str(e)}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to delete from database")

    return {"ok": True}


@router.post("/{file_id}/retry")
def retry_extraction(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # ensure file exists and belongs to current user
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file or file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    if (file.status or '').lower() == 'accepted':
        raise HTTPException(status_code=400, detail="Already accepted; cannot retry")

    # cooldown 2 minutes
    now = datetime.utcnow()
    last = getattr(file, 'last_retry_at', None)
    if last and (now - last) < timedelta(minutes=2):
        remain = timedelta(minutes=2) - (now - last)
        secs = int(remain.total_seconds())
        raise HTTPException(status_code=429, detail=f"Retry too soon. Try again in {secs} seconds")

    # Re-run detection + LLM using the original S3 object
    s3_url = file.s3_url
    presigned_url = None
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
        # validate presence
        try:
            s3.head_object(Bucket=settings.S3_BUCKET, Key=file.filename)
            presigned_url = s3.generate_presigned_url('get_object', Params={"Bucket": settings.S3_BUCKET, "Key": file.filename}, ExpiresIn=900)
        except ClientError:
            presigned_url = None
    except Exception:
        presigned_url = None
    boxes: Optional[list] = None
    llm_result = None
    llm_parsed = None

    def call_llm_again():
        result: Dict[str, Any] = {"llm_result": None, "llm_parsed": None}
        try:
            model = settings.LLM_MODEL or 'gemini-2.5-flash'
            api_key = settings.LLM_API_KEY
            llm_url = settings.LLM_API_URL
            provider = settings.LLM_PROVIDER or 'gemini'
            system_prompt = settings.LLM_SYSTEM_PROMPT or (
                "You are a medical prescription extraction assistant. Extract: "
                "- medicine names and structured medication details (name, dose, frequency), "
                "- any additional noteworthy info, and "
                "- any medical profile data present (present_conditions, diagnosed_conditions, medications_past, allergies, medical_history, family_history, surgeries, immunizations, lifestyle_factors). "
                "Respond ONLY with valid JSON."
            )

            image_url_for_model = presigned_url or s3_url
            schema = ExtractionPayload.model_json_schema()
            rendered = None
            try:
                rendered = render_prompt(
                    'extraction_system.txt',
                    {
                        'IMAGE_URL': image_url_for_model,
                        'JSON_SCHEMA': json.dumps(schema, ensure_ascii=False),
                    }
                )
            except Exception:
                rendered = None

            combined = rendered or (
                f"{system_prompt}\n\n"
                f"A prescription image has been uploaded. Access it here: {image_url_for_model}.\n"
                f"Return STRICTLY a JSON object that conforms to this JSON Schema (no explanations, no markdown):\n"
                f"{json.dumps(schema, ensure_ascii=False)}\n\n"
                f"Rules:\n"
                f"- Only output valid JSON (UTF-8), no code fences.\n"
                f"- If a field is unknown, use an empty list for arrays or omit the optional field.\n"
            )

            if (provider or '').lower() == 'gemini':
                if not llm_url:
                    llm_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                if not api_key:
                    raise HTTPException(status_code=400, detail="Missing LLM API key")
                parsed = urlparse(llm_url)
                q = dict(parse_qsl(parsed.query))
                q['key'] = api_key
                llm_url = urlunparse(parsed._replace(query=urlencode(q)))
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": combined}]}],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": settings.LLM_MAX_TOKENS or 512}
                }
                t0 = time.time()
                r = requests.post(llm_url, json=payload, timeout=30)
                duration_ms = int((time.time() - t0) * 1000)
                if r.ok:
                    resp_data = r.json()
                    try:
                        log_llm_event('retry.gemini.response', {"status": r.status_code, "duration_ms": duration_ms, "data": resp_data})
                    except Exception:
                        pass
                    cands = resp_data.get('candidates')
                    if isinstance(cands, list) and cands:
                        content = cands[0].get('content') or {}
                        parts = content.get('parts') or []
                        texts = [p.get('text', '') for p in parts if isinstance(p, dict) and 'text' in p]
                        llm_reply = "".join(texts).strip()
                        result['llm_result'] = llm_reply
                        try:
                            content = llm_reply
                            if content.startswith('```'):
                                content = content.strip()
                                if content.startswith('```') and content.endswith('```'):
                                    content = content[3:-3].strip()
                                if content.lower().startswith('json'):
                                    content = content[4:].lstrip('\n').lstrip()
                            start = content.find('{')
                            end = content.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                content = content[start:end+1]
                            parsed_obj = json.loads(content)
                            payload_obj = ExtractionPayload.model_validate(parsed_obj)
                            result['llm_parsed'] = json.loads(payload_obj.model_dump_json())
                        except Exception:
                            pass
                else:
                    try:
                        log_llm_event('retry.gemini.error', {"status": r.status_code, "body": getattr(r, 'text', None)})
                    except Exception:
                        pass
            else:
                if not llm_url or not api_key:
                    raise HTTPException(status_code=400, detail="Missing LLM URL or key")
                headers = {'Authorization': f'Bearer {api_key}'}
                payload = {"input": combined}
                r = requests.post(llm_url, json=payload, headers=headers, timeout=30)
                if r.ok:
                    result['llm_result'] = r.text
                    try:
                        log_llm_event('retry.llm.response', {"status": r.status_code, "body": r.text})
                    except Exception:
                        pass
                    try:
                        content = r.text
                        if content.startswith('```'):
                            content = content.strip()
                            if content.startswith('```') and content.endswith('```'):
                                content = content[3:-3].strip()
                            if content.lower().startswith('json'):
                                content = content[4:].lstrip('\n').lstrip()
                        start = content.find('{')
                        end = content.rfind('}')
                        if start != -1 and end != -1 and end > start:
                            content = content[start:end+1]
                        parsed_obj = json.loads(content)
                        payload_obj = ExtractionPayload.model_validate(parsed_obj)
                        result['llm_parsed'] = json.loads(payload_obj.model_dump_json())
                    except Exception:
                        pass
                else:
                    try:
                        log_llm_event('retry.llm.error', {"status": r.status_code, "body": getattr(r, 'text', None)})
                    except Exception:
                        pass
        except HTTPException:
            raise
        except Exception as e:
            try:
                log_llm_event('retry.llm.error', {"error": str(e)})
            except Exception:
                pass
        return result

    try:
        res = call_llm_again()
        llm_result = res.get('llm_result') if isinstance(res, dict) else None
        llm_parsed = res.get('llm_parsed') if isinstance(res, dict) else None

        # Update extracted_data and set status to awaiting_review if parsed
        payload = {
            "boxes": None,
            "original_s3": s3_url,
            "llm_result": llm_result,
            "llm_parsed": llm_parsed,
        }
        setattr(file, 'extracted_data', json.dumps(payload))
        if (file.status or '').lower() != 'accepted':
            setattr(file, 'status', 'awaiting_review')
        setattr(file, 'last_retry_at', now)
        try:
            setattr(file, 'retry_count', int((getattr(file, 'retry_count') or 0)) + 1)
        except Exception:
            setattr(file, 'retry_count', 1)
        db.commit()
        db.refresh(file)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Retry failed: {str(e)}")
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Retry failed")

    return {"ok": True}