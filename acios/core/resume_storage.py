"""
Private master-resume storage shared by the API and background worker.

Use local storage for development or a private S3-compatible bucket in production.
Never expose the bucket publicly; this module only uses server-side credentials.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional


_OBJECT_KEY = "resumes/master_resume.pdf"
_DEFAULT_FILENAME = "master_resume.pdf"


def _backend() -> str:
    value = os.getenv("RESUME_STORAGE_BACKEND", "local").strip().lower()
    if value not in {"local", "s3"}:
        raise RuntimeError("RESUME_STORAGE_BACKEND must be either 'local' or 's3'.")
    return value


def _local_resume_path(base_dir: Optional[Path] = None) -> Path:
    configured = os.getenv("ACIOS_RESUME_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve() / _DEFAULT_FILENAME
    root = base_dir or Path(__file__).resolve().parents[2]
    return root / "data" / "resume" / _DEFAULT_FILENAME


def _s3_client() -> Any:
    bucket = os.getenv("RESUME_STORAGE_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError(
            "RESUME_STORAGE_BUCKET must be configured when RESUME_STORAGE_BACKEND=s3."
        )
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError("Install boto3 to use S3-compatible resume storage.") from exc

    endpoint = os.getenv("RESUME_STORAGE_ENDPOINT_URL", "").strip() or None
    region = os.getenv("RESUME_STORAGE_REGION", "us-east-1").strip() or "us-east-1"
    return boto3.client("s3", endpoint_url=endpoint, region_name=region)


def save_master_resume(content: bytes, base_dir: Optional[Path] = None) -> dict:
    """Persist a validated PDF and return metadata without exposing the storage URL."""
    if not content.startswith(b"%PDF-"):
        raise ValueError("Resume upload does not have a PDF file signature.")

    if _backend() == "s3":
        bucket = os.getenv("RESUME_STORAGE_BUCKET", "").strip()
        client = _s3_client()
        client.put_object(
            Bucket=bucket,
            Key=_OBJECT_KEY,
            Body=content,
            ContentType="application/pdf",
        )
    else:
        target = _local_resume_path(base_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    return {
        "filename": _DEFAULT_FILENAME,
        "size_kb": round(len(content) / 1024, 1),
        "exists": True,
        "is_ready": True,
    }


def load_master_resume(base_dir: Optional[Path] = None) -> bytes:
    """Load resume bytes for a worker send. Raises clearly when storage is unavailable."""
    if _backend() == "s3":
        bucket = os.getenv("RESUME_STORAGE_BUCKET", "").strip()
        client = _s3_client()
        try:
            result = client.get_object(Bucket=bucket, Key=_OBJECT_KEY)
            body = result["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            code = str((response.get("Error") or {}).get("Code", ""))
            if code in {"NoSuchKey", "404", "NotFound"}:
                raise FileNotFoundError("Master resume is not present in private object storage.") from exc
            raise RuntimeError("Private resume storage could not be read by the worker.") from exc

    target = _local_resume_path(base_dir)
    if not target.is_file():
        raise FileNotFoundError(
            f"Master resume not found at {target}. Upload a PDF before enabling live dispatch."
        )
    return target.read_bytes()


def get_master_resume_metadata(base_dir: Optional[Path] = None) -> dict:
    """Return the private resume's readiness and size; never return a storage URL."""
    if _backend() == "s3":
        bucket = os.getenv("RESUME_STORAGE_BUCKET", "").strip()
        client = _s3_client()
        try:
            result = client.head_object(Bucket=bucket, Key=_OBJECT_KEY)
            size = int(result.get("ContentLength", 0))
            return {
                "filename": _DEFAULT_FILENAME,
                "size_kb": round(size / 1024, 1),
                "exists": True,
                "is_ready": True,
            }
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            code = str((response.get("Error") or {}).get("Code", ""))
            if code in {"NoSuchKey", "404", "NotFound"}:
                return {"filename": "None", "size_kb": 0, "exists": False, "is_ready": False}
            raise RuntimeError("Private resume storage metadata lookup failed.") from exc

    target = _local_resume_path(base_dir)
    if not target.is_file():
        return {"filename": "None", "size_kb": 0, "exists": False, "is_ready": False}
    size = target.stat().st_size
    return {
        "filename": _DEFAULT_FILENAME,
        "size_kb": round(size / 1024, 1),
        "exists": True,
        "is_ready": True,
    }
