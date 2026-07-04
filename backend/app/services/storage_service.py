"""
Layer 7 storage. If AWS_S3_BUCKET is set, uploads go to S3 (matches the thesis's tech
stack: "AWS S3 (media)"). Otherwise falls back to local disk so the app runs without
an AWS account during early development. The interface (`save_audio` returns a path/key
string, `get_local_path` resolves it back to a real file for the pipeline to read) stays
the same either way, so nothing else in the backend needs to know which mode is active.
"""
import os
import uuid

from ..config import settings

try:
    import boto3
except ImportError:  # boto3 is in requirements.txt, but keep this defensive
    boto3 = None


def _local_dir() -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    return settings.upload_dir


def save_audio(file_bytes: bytes, original_filename: str, session_id: str) -> str:
    ext = os.path.splitext(original_filename)[1] or ".webm"
    key = f"sessions/{session_id}/audio{ext}"

    if settings.aws_s3_bucket and boto3:
        s3 = boto3.client("s3", region_name=settings.aws_region)
        s3.put_object(Bucket=settings.aws_s3_bucket, Key=key, Body=file_bytes)
        return f"s3://{settings.aws_s3_bucket}/{key}"

    local_path = os.path.join(_local_dir(), f"{session_id}{ext}")
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return local_path


def get_local_path(stored_path: str) -> str:
    """
    Resolves a stored path/key to a local file the pipeline can open. Downloads from S3
    to a temp file if needed; returns the path unchanged if it's already local.
    """
    if not stored_path.startswith("s3://"):
        return stored_path

    if not boto3:
        raise RuntimeError("boto3 is required to read S3-backed audio but isn't installed.")

    _, _, rest = stored_path.partition("s3://")
    bucket, _, key = rest.partition("/")
    local_tmp = os.path.join(_local_dir(), f"tmp-{uuid.uuid4()}-{os.path.basename(key)}")
    s3 = boto3.client("s3", region_name=settings.aws_region)
    s3.download_file(bucket, key, local_tmp)
    return local_tmp


def delete_audio(stored_path: str) -> None:
    """Best-effort delete — called when a session is removed. Never raises."""
    try:
        if stored_path.startswith("s3://") and boto3:
            _, _, rest = stored_path.partition("s3://")
            bucket, _, key = rest.partition("/")
            s3 = boto3.client("s3", region_name=settings.aws_region)
            s3.delete_object(Bucket=bucket, Key=key)
        elif stored_path and os.path.exists(stored_path):
            os.remove(stored_path)
    except Exception:
        pass
