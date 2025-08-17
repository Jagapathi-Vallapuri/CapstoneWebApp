from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from utils.security import get_current_user
from sqlalchemy.orm import Session
from db.session import get_db
from models.uploaded_file import UploadedFile
from schemas.uploaded_file import UploadedFileOut
from typing import List
from core.config import settings
import boto3
from botocore.exceptions import ClientError
from fastapi.responses import JSONResponse
import re
import uuid
import logging

router = APIRouter()

@router.post("/upload", response_model=UploadedFileOut)
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    try:
        # Validate file size (max 5MB)
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        if size > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail={"error": "File too large (max 5MB)."})

        # Read first bytes for magic number check
        magic = file.file.read(4)
        file.file.seek(0)
        # JPEG: ff d8 ff, PNG: 89 50 4e 47, PDF: 25 50 44 46
        is_jpeg = magic[:3] == b'\xff\xd8\xff'
        is_png = magic == b'\x89PNG'
        is_pdf = magic == b'%PDF'
        if not (is_jpeg or is_png or is_pdf):
            raise HTTPException(status_code=400, detail={"error": "Invalid file type (magic number check failed)."})

        # Sanitize filename
        safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', file.filename or "uploaded_file")
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"

        # Upload to S3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION
        )
        try:
            s3.upload_fileobj(
                file.file,
                settings.S3_BUCKET,
                unique_filename,
                ExtraArgs={"ContentType": file.content_type}
            )
        except Exception as e:
            logging.error(f"S3 upload failed: {str(e)}")
            raise HTTPException(status_code=500, detail={"error": f"S3 upload failed: {str(e)}"})

        s3_url = f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{unique_filename}"

        db_file = UploadedFile(
            user_id=current_user.id,
            filename=unique_filename,
            file_type=file.content_type,
            status="pending"
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
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

        url = s3.generate_presigned_url('get_object', Params=params, ExpiresIn=600)
        return JSONResponse({"presigned_url": url, "expires_in": 600})
    except ClientError as e:
        logging.error(f"Failed to generate presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate presigned URL")