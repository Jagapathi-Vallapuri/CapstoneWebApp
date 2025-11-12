import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from core.config import settings
from fastapi import HTTPException


def _client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    )


def delete_object_if_exists(key: str) -> None:
    """Delete an object from S3; ignore if missing. Raise HTTPException on other errors."""
    try:
        s3 = _client()
        try:
            s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
        except ClientError as ce:
            code = getattr(ce, 'response', {}).get('Error', {}).get('Code')
            if str(code) not in ("NoSuchKey", "404"):
                logging.error(f"S3 delete_object failed for key={key}: {code}")
                raise HTTPException(status_code=500, detail="Failed to delete from S3")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected S3 error during delete: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete from S3")


def head_exists(key: str) -> bool:
    try:
        s3 = _client()
        s3.head_object(Bucket=settings.S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False
    except Exception:
        return False


def generate_presigned_get(key: str, response_disposition: Optional[str] = None, expires_in: int = 900) -> Optional[str]:
    try:
        s3 = _client()
        params = {"Bucket": settings.S3_BUCKET, "Key": key}
        if response_disposition:
            params["ResponseContentDisposition"] = response_disposition
        return s3.generate_presigned_url('get_object', Params=params, ExpiresIn=expires_in)
    except Exception:
        return None
