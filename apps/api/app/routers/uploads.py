from __future__ import annotations

import hmac
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.domain.enums import CaseStatus, DocumentStatus
from app.models import Document, Report, User
from app.schemas import CompleteUploadRequest, SignedUploadRequest, SignedUploadResponse
from app.services.audit import write_audit, write_timeline
from app.services.file_validation import validate_declared_file, validate_file_signature
from app.services.malware import scan_bytes
from app.services.storage import LocalStorageProvider, _signature, get_storage_provider

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/signed-url", response_model=SignedUploadResponse)
async def create_signed_upload_url(
    payload: SignedUploadRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SignedUploadResponse:
    if payload.file_size > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds configured upload limit")
    if validation_error := validate_declared_file(filename=payload.filename, content_type=payload.content_type):
        raise HTTPException(status_code=415, detail=validation_error)
    case = get_case_for_user(payload.case_id, db, current_user)
    document = Document(
        case_id=case.id,
        uploaded_by_user_id=current_user.id,
        category=payload.category,
        filename=payload.filename,
        content_type=payload.content_type,
        file_size=payload.file_size,
        sha256=payload.sha256,
        storage_uri="pending",
        status=DocumentStatus.UPLOADING,
    )
    db.add(document)
    db.flush()
    ticket = get_storage_provider().create_upload_ticket(
        document_id=document.id,
        filename=payload.filename,
        content_type=payload.content_type,
        max_bytes=payload.file_size,
    )
    document.storage_uri = ticket["storage_uri"]
    write_timeline(
        db,
        case_id=case.id,
        actor=current_user,
        event_type="document_upload_started",
        title=f"Upload started: {payload.category.value}",
        metadata={"document_id": document.id, "filename": payload.filename},
    )
    write_audit(
        db,
        action="upload.signed_url.create",
        target_type="document",
        target_id=document.id,
        actor=current_user,
        request=request,
        case_id=case.id,
    )
    db.commit()
    return SignedUploadResponse(
        document_id=document.id,
        upload_url=ticket["upload_url"],
        method=ticket["method"],
        headers=ticket["headers"],
        expires_at=ticket["expires_at"],
    )


@router.put("/local/{document_id}")
async def local_signed_upload(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    expires: Annotated[int, Query(gt=0)],
    content_type: Annotated[str, Query(min_length=1, max_length=120)],
    max_bytes: Annotated[int, Query(gt=0)],
    token: Annotated[str, Query(min_length=16, max_length=256)],
) -> dict[str, str | int]:
    provider = get_storage_provider()
    if not isinstance(provider, LocalStorageProvider):
        raise HTTPException(status_code=404, detail="Local upload route is disabled")
    provider.verify_upload_token(
        document_id=document_id, expires=expires, content_type=content_type, max_bytes=max_bytes, token=token
    )
    request_content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if request_content_type and request_content_type != content_type:
        raise HTTPException(status_code=415, detail="Upload content type does not match signed URL")
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    status_value = document.status.value if hasattr(document.status, "value") else str(document.status)
    if status_value != DocumentStatus.UPLOADING.value:
        raise HTTPException(status_code=409, detail="Document upload is not accepting writes")
    limit = min(settings.max_upload_bytes, max_bytes)
    bytes_written, digest = await provider.accept_upload_stream(
        storage_uri=document.storage_uri,
        chunks=request.stream(),
        max_bytes=limit,
    )
    document.file_size = bytes_written
    document.sha256 = digest
    document.status = DocumentStatus.QUARANTINED
    db.commit()
    return {"document_id": document.id, "bytes": bytes_written, "sha256": document.sha256}


@router.get("/local-read")
async def local_signed_read(
    uri: Annotated[str, Query(min_length=1, max_length=500)],
    expires: Annotated[int, Query(gt=0)],
    token: Annotated[str, Query(min_length=16, max_length=256)],
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    if datetime.now(UTC).timestamp() > expires:
        raise HTTPException(status_code=401, detail="Read URL expired")
    expected = _signature(f"{uri}:{expires}", settings.report_signing_secret)
    if not hmac.compare_digest(expected, token):
        raise HTTPException(status_code=401, detail="Invalid read token")
    provider = get_storage_provider()
    if not isinstance(provider, LocalStorageProvider):
        raise HTTPException(status_code=404, detail="Local read route is disabled")
    document = db.query(Document).filter(Document.storage_uri == uri).one_or_none()
    report = None if document else db.query(Report).filter(Report.pdf_storage_uri == uri).one_or_none()
    target_type = "document" if document else "report" if report else "storage_object"
    target_id = document.id if document else report.id if report else sha256(uri.encode()).hexdigest()[:16]
    case_id = document.case_id if document else report.case_id if report else None
    media_type = document.content_type if document else "application/pdf" if report else "application/octet-stream"
    write_audit(
        db,
        action="download.signed_url.consume",
        target_type=target_type,
        target_id=target_id,
        request=request,
        case_id=case_id,
        metadata={"delivery": "signed_url"},
    )
    db.commit()
    filename = "mradi-document.pdf" if media_type == "application/pdf" else "mradi-document"
    return Response(
        provider.read_bytes(uri),
        media_type=media_type,
        headers={
            "cache-control": "no-store",
            "content-disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/complete")
async def complete_upload(
    payload: CompleteUploadRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    document = db.query(Document).filter(Document.id == payload.document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    case = get_case_for_user(document.case_id, db, current_user)
    provider = get_storage_provider()
    content = provider.read_bytes(document.storage_uri)
    if len(content) > settings.max_upload_bytes:
        document.status = DocumentStatus.REJECTED
        document.rejection_reason = "File exceeds configured upload limit"
        write_audit(
            db,
            action="upload.rejected",
            target_type="document",
            target_id=document.id,
            actor=current_user,
            request=request,
            case_id=case.id,
            metadata={"reason": "file_size_limit"},
        )
        db.commit()
        raise HTTPException(status_code=413, detail="File exceeds configured upload limit")
    actual_sha = sha256(content).hexdigest()
    if payload.sha256 and payload.sha256 != actual_sha:
        document.status = DocumentStatus.REJECTED
        document.rejection_reason = "SHA-256 mismatch"
        write_audit(
            db,
            action="upload.rejected",
            target_type="document",
            target_id=document.id,
            actor=current_user,
            request=request,
            case_id=case.id,
            metadata={"reason": "sha256_mismatch"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="SHA-256 mismatch")
    if validation_error := validate_file_signature(content=content, content_type=document.content_type):
        document.status = DocumentStatus.REJECTED
        document.rejection_reason = validation_error
        write_audit(
            db,
            action="upload.rejected",
            target_type="document",
            target_id=document.id,
            actor=current_user,
            request=request,
            case_id=case.id,
            metadata={"reason": "file_signature"},
        )
        db.commit()
        raise HTTPException(status_code=415, detail=validation_error)
    scan = scan_bytes(content)
    document.scan_status = scan["status"]
    if scan["status"] in {"infected", "scanner_unavailable"}:
        document.status = DocumentStatus.REJECTED
        document.rejection_reason = scan["detail"]
    else:
        mover = getattr(provider, "move_to_clean", None)
        if mover is not None:
            document.storage_uri = mover(document.storage_uri)
        document.status = DocumentStatus.CLEAN
        case.status = CaseStatus.READY_FOR_ANALYSIS
    write_timeline(
        db,
        case_id=case.id,
        actor=current_user,
        event_type="document_upload_completed",
        title=f"Upload completed: {document.category.value}",
        metadata={"document_id": document.id, "scan_status": document.scan_status},
    )
    write_audit(
        db,
        action="upload.complete",
        target_type="document",
        target_id=document.id,
        actor=current_user,
        request=request,
        case_id=case.id,
        metadata={"scan_status": document.scan_status},
    )
    db.commit()
    return {"document_id": document.id, "status": document.status.value, "scan_status": document.scan_status}
