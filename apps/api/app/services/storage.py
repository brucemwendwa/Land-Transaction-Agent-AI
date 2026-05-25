from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

from fastapi import HTTPException, status

from app.core.config import settings


class UploadTicket(dict[str, Any]):
    document_id: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime
    storage_uri: str
    storage_bucket: str


class StorageProvider(Protocol):
    def create_upload_ticket(
        self, *, document_id: str, filename: str, content_type: str, max_bytes: int
    ) -> UploadTicket: ...
    def read_bytes(self, storage_uri: str) -> bytes: ...
    def write_bytes(self, storage_uri: str, content: bytes, content_type: str) -> None: ...
    def create_read_url(self, storage_uri: str, expires_minutes: int = 10) -> str: ...
    def delete_uri(self, storage_uri: str) -> None: ...


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace("/", "_").replace("\\", "_")


def _signature(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class LocalStorageProvider:
    def __init__(self) -> None:
        self.root = settings.local_storage_root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, storage_uri: str) -> Path:
        if not storage_uri.startswith("local://"):
            raise ValueError("Unsupported local storage URI")
        relative = storage_uri.removeprefix("local://")
        path = (self.root / relative).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError("Storage path escapes root")
        return path

    def create_upload_ticket(
        self, *, document_id: str, filename: str, content_type: str, max_bytes: int
    ) -> UploadTicket:
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        storage_uri = f"local://quarantine/{document_id}/{_safe_filename(filename)}"
        payload = f"{document_id}:{int(expires_at.timestamp())}:{content_type}:{max_bytes}"
        token = _signature(payload, settings.upload_signing_secret)
        query = urlencode(
            {
                "expires": int(expires_at.timestamp()),
                "content_type": content_type,
                "max_bytes": max_bytes,
                "token": token,
            }
        )
        return UploadTicket(
            document_id=document_id,
            upload_url=f"{settings.api_base_url}/uploads/local/{document_id}?{query}",
            method="PUT",
            headers={"content-type": content_type},
            expires_at=expires_at,
            storage_uri=storage_uri,
            storage_bucket="local",
        )

    def verify_upload_token(
        self, *, document_id: str, expires: int, content_type: str, max_bytes: int, token: str
    ) -> None:
        if datetime.now(UTC).timestamp() > expires:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Upload URL expired")
        expected = _signature(
            f"{document_id}:{expires}:{content_type}:{max_bytes}", settings.upload_signing_secret
        )
        if not hmac.compare_digest(expected, token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid upload token")

    async def accept_upload_stream(
        self,
        *,
        storage_uri: str,
        chunks: AsyncIterator[bytes],
        max_bytes: int,
    ) -> tuple[int, str]:
        path = self._path(storage_uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        total = 0
        with path.open("wb") as destination:
            async for chunk in chunks:
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File exceeds configured upload limit")
                digest.update(chunk)
                destination.write(chunk)
        return total, digest.hexdigest()

    def read_bytes(self, storage_uri: str) -> bytes:
        return self._path(storage_uri).read_bytes()

    def write_bytes(self, storage_uri: str, content: bytes, content_type: str) -> None:
        path = self._path(storage_uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def move_to_clean(self, storage_uri: str) -> str:
        source = self._path(storage_uri)
        clean_uri = storage_uri.replace("local://quarantine/", "local://clean/", 1)
        target = self._path(clean_uri)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        return clean_uri

    def create_read_url(self, storage_uri: str, expires_minutes: int = 10) -> str:
        expires_at = datetime.now(UTC) + timedelta(minutes=expires_minutes)
        payload = f"{storage_uri}:{int(expires_at.timestamp())}"
        token = _signature(payload, settings.report_signing_secret)
        return (
            f"{settings.api_base_url}/uploads/local-read?"
            + urlencode({"uri": storage_uri, "expires": int(expires_at.timestamp()), "token": token})
        )

    def delete_uri(self, storage_uri: str) -> None:
        self._path(storage_uri).unlink(missing_ok=True)


class GCSStorageProvider:
    def __init__(self) -> None:
        from google.cloud import storage  # type: ignore[attr-defined]

        if not settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs")
        self.client = storage.Client(project=settings.gcp_project_id or None)
        self.bucket = self.client.bucket(settings.gcs_bucket)

    def create_upload_ticket(
        self, *, document_id: str, filename: str, content_type: str, max_bytes: int
    ) -> UploadTicket:
        expires_at = datetime.now(UTC) + timedelta(minutes=15)
        blob_name = f"quarantine/{document_id}/{_safe_filename(filename)}"
        blob = self.bucket.blob(blob_name)
        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=expires_at,
            method="PUT",
            content_type=content_type,
        )
        return UploadTicket(
            document_id=document_id,
            upload_url=upload_url,
            method="PUT",
            headers={"content-type": content_type},
            expires_at=expires_at,
            storage_uri=f"gs://{settings.gcs_bucket}/{blob_name}",
            storage_bucket=settings.gcs_bucket,
        )

    def _blob_from_uri(self, storage_uri: str) -> Any:
        prefix = f"gs://{settings.gcs_bucket}/"
        if not storage_uri.startswith(prefix):
            raise ValueError("Unsupported GCS URI")
        return self.bucket.blob(storage_uri.removeprefix(prefix))

    def read_bytes(self, storage_uri: str) -> bytes:
        return bytes(self._blob_from_uri(storage_uri).download_as_bytes())

    def write_bytes(self, storage_uri: str, content: bytes, content_type: str) -> None:
        self._blob_from_uri(storage_uri).upload_from_string(content, content_type=content_type)

    def move_to_clean(self, storage_uri: str) -> str:
        source = self._blob_from_uri(storage_uri)
        clean_uri = storage_uri.replace(f"gs://{settings.gcs_bucket}/quarantine/", f"gs://{settings.gcs_bucket}/clean/", 1)
        target_name = clean_uri.removeprefix(f"gs://{settings.gcs_bucket}/")
        self.bucket.copy_blob(source, self.bucket, target_name)
        source.delete()
        return clean_uri

    def create_read_url(self, storage_uri: str, expires_minutes: int = 10) -> str:
        blob = self._blob_from_uri(storage_uri)
        return str(
            blob.generate_signed_url(
                version="v4",
                expiration=datetime.now(UTC) + timedelta(minutes=expires_minutes),
                method="GET",
            )
        )

    def delete_uri(self, storage_uri: str) -> None:
        self._blob_from_uri(storage_uri).delete()


def get_storage_provider() -> StorageProvider:
    if settings.gcs_enabled:
        return GCSStorageProvider()
    return LocalStorageProvider()
