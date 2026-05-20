from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, selectinload

from app.agents.orchestrator import extract_single_document
from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.models import Document, ExtractedField, FieldCorrection, LandCase, User
from app.schemas import (
    DocumentRead,
    DocumentReadUrlResponse,
    ExtractedFieldRead,
    ExtractionResult,
    FieldCorrectionCreate,
    FieldCorrectionRead,
)
from app.services.audit import write_audit, write_timeline
from app.services.extraction import normalize
from app.services.storage import get_storage_provider

router = APIRouter(tags=["documents"])


@router.get("/cases/{case_id}/documents", response_model=list[DocumentRead])
async def list_case_documents(
    case_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Document]:
    get_case_for_user(case_id, db, current_user)
    return (
        db.query(Document)
        .options(selectinload(Document.extracted_fields), selectinload(Document.field_corrections))
        .filter(Document.case_id == case_id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.post("/documents/{document_id}/extract", response_model=ExtractionResult)
async def extract_document(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ExtractionResult:
    document = (
        db.query(Document)
        .options(selectinload(Document.extracted_fields), selectinload(Document.field_corrections))
        .filter(Document.id == document_id)
        .one_or_none()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    get_case_for_user(document.case_id, db, current_user)
    status_value = document.status.value if hasattr(document.status, "value") else str(document.status)
    if status_value not in {"clean", "extracted", "needs_review"}:
        raise HTTPException(status_code=409, detail="Document must pass upload validation before extraction")
    verification_status = await extract_single_document(
        db=db, document=document, storage=get_storage_provider()
    )
    write_timeline(
        db,
        case_id=document.case_id,
        actor=current_user,
        event_type="document_extracted",
        title=f"Extraction completed: {document.category.value}",
        metadata={"document_id": document.id, "verification_status": verification_status.value},
    )
    write_audit(
        db,
        action="document.extract",
        target_type="document",
        target_id=document.id,
        actor=current_user,
        request=request,
        case_id=document.case_id,
    )
    db.commit()
    db.refresh(document)
    return ExtractionResult(
        document=DocumentRead.model_validate(document),
        extracted_fields=[ExtractedFieldRead.model_validate(field) for field in document.extracted_fields],
        verification_status=verification_status,
    )


@router.get("/documents/{document_id}/read-url", response_model=DocumentReadUrlResponse)
async def document_read_url(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentReadUrlResponse:
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    get_case_for_user(document.case_id, db, current_user)
    expires = 10
    write_audit(
        db,
        action="download.signed_url.create",
        target_type="document",
        target_id=document.id,
        actor=current_user,
        request=request,
        case_id=document.case_id,
        metadata={"expires_in_minutes": expires},
    )
    db.commit()
    return DocumentReadUrlResponse(
        document_id=document.id,
        read_url=get_storage_provider().create_read_url(document.storage_uri, expires_minutes=expires),
        expires_in_minutes=expires,
    )


@router.post("/documents/{document_id}/corrections", response_model=FieldCorrectionRead, status_code=201)
async def create_field_correction(
    document_id: str,
    payload: FieldCorrectionCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FieldCorrection:
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    get_case_for_user(document.case_id, db, current_user)
    extracted_field = None
    if payload.extracted_field_id:
        extracted_field = (
            db.query(ExtractedField)
            .filter(ExtractedField.id == payload.extracted_field_id, ExtractedField.document_id == document_id)
            .one_or_none()
        )
        if extracted_field is None:
            raise HTTPException(status_code=404, detail="Extracted field not found for this document")
    correction = FieldCorrection(
        document_id=document.id,
        extracted_field_id=extracted_field.id if extracted_field else None,
        corrected_by_user_id=current_user.id,
        field_name=payload.field_name,
        ai_value=extracted_field.value if extracted_field else "",
        corrected_value=payload.corrected_value,
        normalized_value=normalize(payload.corrected_value),
        reason=payload.reason,
        metadata_json={
            "preserves_ai_extraction": True,
            "source": "user_review",
        },
    )
    db.add(correction)
    write_timeline(
        db,
        case_id=document.case_id,
        actor=current_user,
        event_type="document_field_corrected",
        title=f"Field corrected: {payload.field_name}",
        metadata={"document_id": document.id, "field_name": payload.field_name},
    )
    write_audit(
        db,
        action="document.field_correction.create",
        target_type="document",
        target_id=document.id,
        actor=current_user,
        request=request,
        case_id=document.case_id,
        metadata={"field_name": payload.field_name, "extracted_field_id": payload.extracted_field_id},
    )
    db.commit()
    db.refresh(correction)
    return correction


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    document = db.query(Document).filter(Document.id == document_id).one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    case: LandCase = get_case_for_user(document.case_id, db, current_user)
    get_storage_provider().delete_uri(document.storage_uri)
    db.delete(document)
    write_audit(
        db,
        action="document.delete",
        target_type="document",
        target_id=document_id,
        actor=current_user,
        request=request,
        case_id=case.id,
    )
    db.commit()
