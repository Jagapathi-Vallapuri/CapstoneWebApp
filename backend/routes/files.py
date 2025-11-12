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
from services.s3_service import delete_object_if_exists
from services.file_service import delete_file_and_related
from datetime import datetime, timedelta

router = APIRouter()
@router.post("/upload", response_model=UploadedFileOut)
def upload_file(
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    try:
        # Read and validate content
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

        # Prepare S3 keys
        safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', file.filename or "uploaded_file")
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        user_prefix = f"users/{current_user.id}/"
        s3_key_original = f"{user_prefix}{unique_filename}"

        # Upload original
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
        try:
            presigned_url = s3.generate_presigned_url('get_object', Params={"Bucket": settings.S3_BUCKET, "Key": s3_key_original}, ExpiresIn=900)
        except Exception:
            presigned_url = None

        # Friendly display name
        try:
            if display_name and display_name.strip():
                friendly_name = display_name.strip()
            else:
                total = db.query(UploadedFile).filter(UploadedFile.user_id == current_user.id).count()
                _, ext = os.path.splitext(file.filename or '')
                ext = (ext or '').lower()
                friendly_name = f"Document {total + 1}{ext}"
        except Exception:
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
        detection_img_bytes: Optional[bytes] = None

        def call_detection():
            try:
                ct = file.content_type or "application/octet-stream"
                resp = requests.post(
                    f"{detection_url}/detect/boxes/",
                    files={"file": (safe_filename or "uploaded_image", io.BytesIO(contents), ct)},
                    timeout=20,
                )
                if resp.ok:
                    data = resp.json()
                    return data.get('boxes')
            except Exception as e:
                logging.warning(f"Detection call failed: {str(e)}")
            return None

        def call_detection_image():
            try:
                ct = file.content_type or "application/octet-stream"
                resp = requests.post(
                    f"{detection_url}/detect/image/",
                    files={"file": (safe_filename or "uploaded_image", io.BytesIO(contents), ct)},
                    timeout=30,
                )
                if resp.ok:
                    return resp.content
            except Exception as e:
                logging.warning(f"Detection image call failed: {str(e)}")
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

        # Run detection (boxes and image) and LLM concurrently
        try:
            with ThreadPoolExecutor(max_workers=3) as ex:
                futures = {
                    ex.submit(call_detection): 'detection',
                    ex.submit(call_detection_image): 'detection_image',
                    ex.submit(call_llm): 'llm',
                }
                for fut in as_completed(futures):
                    name = futures.get(fut)
                    try:
                        res = fut.result()
                        if name == 'detection':
                            boxes = res
                        elif name == 'detection_image' and isinstance(res, (bytes, bytearray)):
                            detection_img_bytes = bytes(res)
                        elif name == 'llm' and isinstance(res, dict):
                            llm_result = res.get('llm_result')
                            llm_parsed = res.get('llm_parsed')
                    except Exception as e:
                        logging.warning(f"Concurrent task {name} failed: {str(e)}")

            # Normalize llm payload if present
            normalized_llm = None
            if isinstance(llm_parsed, dict):
                try:
                    pl = ExtractionPayload.model_validate(llm_parsed)
                    normalized_llm = json.loads(pl.model_dump_json())
                except Exception:
                    normalized_llm = llm_parsed

            # Upload detection image if available
            detection_image_key = None
            detection_image_s3 = None
            try:
                if detection_img_bytes:
                    base_no_ext = os.path.splitext(unique_filename)[0]
                    detection_image_key = f"{user_prefix}detection-results/{base_no_ext}.jpg"
                    s3.upload_fileobj(
                        io.BytesIO(detection_img_bytes),
                        settings.S3_BUCKET,
                        detection_image_key,
                        ExtraArgs={"ContentType": "image/jpeg"}
                    )
                    detection_image_s3 = f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{detection_image_key}"
            except Exception as e:
                logging.warning(f"Failed to upload detection image: {str(e)}")

            extracted_payload = {
                "boxes": boxes,
                "original_s3": s3_url,
                "llm_result": llm_result,
                "llm_parsed": normalized_llm,
                "detection_image_key": detection_image_key,
                "detection_image_s3": detection_image_s3,
            }

            # Create prescription row
            prescription = Prescription(
                user_id=db_file.user_id,
                file_id=db_file.id,
                extracted_fields=json.dumps(extracted_payload)
            )
            db.add(prescription)
            db.commit()
            db.refresh(prescription)
        except Exception as e:
            logging.error(f"Failed during detection/LLM or prescription creation: {str(e)}")
            try:
                db.rollback()
            except Exception:
                pass

        # Update uploaded file with extracted payload
        try:
            setattr(db_file, 'status', 'awaiting_review')
            setattr(db_file, 'extracted_data', json.dumps(extracted_payload))
            db.commit()
            db.refresh(db_file)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        return db_file
    except HTTPException:
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
        try:
            s3.head_object(Bucket=settings.S3_BUCKET, Key=file.filename)
        except ClientError as ce:
            err_code = getattr(ce, 'response', {}).get('Error', {}).get('Code')
            logging.warning(f"S3 head_object failed for key={file.filename}: {err_code}")
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
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file or file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        raw = cast(Optional[str], getattr(file, 'extracted_data', None))
        extracted = json.loads(raw or '{}')
    except Exception:
        extracted = {}

    if body and isinstance(body, dict):
        incoming = body.get('payload')
        if incoming is not None:
            try:
                payload = ExtractionPayload.model_validate(incoming)
                normalized = json.loads(payload.model_dump_json())
                extracted["llm_parsed"] = normalized
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    try:
        setattr(file, 'status', 'accepted')
        if hasattr(file, 'accepted'):
            setattr(file, 'accepted', True)
        setattr(file, 'extracted_data', json.dumps(extracted))

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
                summary = ", ".join(meds) if meds else None
                if summary:
                    setattr(profile, 'medications_current', summary)
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
    file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not file or file.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    delete_object_if_exists(file.filename)

    delete_file_and_related(db, file)

    return {"ok": True}


@router.post("/{file_id}/retry")
def retry_extraction(
    file_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
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

    s3_url = file.s3_url
    presigned_url = None
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
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