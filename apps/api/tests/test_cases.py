from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.domain.enums import DocumentCategory, DocumentStatus
from app.models import Document, ExtractedField, LandCase, RiskAnalysisResult, User


def test_case_crud_with_auth_bypass(client: TestClient) -> None:
    response = client.post(
        "/cases",
        json={
            "title": "Kajiado parcel",
            "buyer_name": "Jane Wanjiku",
            "seller_name": "John Mwangi",
            "parcel_number_claimed": "LR 209/1234",
            "location_county": "Kajiado",
        },
    )
    assert response.status_code == 201
    case_id = response.json()["id"]

    read_response = client.get(f"/cases/{case_id}")
    assert read_response.status_code == 200
    assert read_response.json()["parcel_number_claimed"] == "LR 209/1234"


def test_upload_rejects_unsupported_file_type(client: TestClient) -> None:
    case_response = client.post("/cases", json={"title": "Upload guard"})
    case_id = case_response.json()["id"]
    response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "script.exe",
            "content_type": "application/x-msdownload",
            "file_size": 100,
            "consent_to_process": True,
        },
    )
    assert response.status_code == 415


def test_upload_requires_user_consent(client: TestClient) -> None:
    case_response = client.post("/cases", json={"title": "Consent guard"})
    case_id = case_response.json()["id"]
    response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "title.pdf",
            "content_type": "application/pdf",
            "file_size": 100,
        },
    )
    assert response.status_code == 422
    assert "Consent is required" in response.text


def test_complete_upload_rejects_mismatched_file_signature(client: TestClient) -> None:
    case_response = client.post("/cases", json={"title": "Signature guard"})
    case_id = case_response.json()["id"]
    signed_response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "title.pdf",
            "content_type": "application/pdf",
            "file_size": 7,
            "consent_to_process": True,
        },
    )
    assert signed_response.status_code == 200
    signed = signed_response.json()
    upload_response = client.put(
        signed["upload_url"],
        content=b"not pdf",
        headers=signed["headers"],
    )
    assert upload_response.status_code == 200
    complete_response = client.post(
        "/uploads/complete",
        json={"document_id": signed["document_id"]},
    )
    assert complete_response.status_code == 415
    assert "valid PDF signature" in complete_response.text


def test_document_response_does_not_expose_storage_keys(client: TestClient) -> None:
    case_response = client.post("/cases", json={"title": "Private document case"})
    case_id = case_response.json()["id"]
    signed_response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "title.pdf",
            "content_type": "application/pdf",
            "file_size": 5,
            "consent_to_process": True,
        },
    )
    assert signed_response.status_code == 200
    case_payload = client.get(f"/cases/{case_id}").json()
    document_payload = case_payload["documents"][0]
    assert "storage_uri" not in document_payload
    assert "file_url" not in document_payload


def test_report_generation_requires_legal_disclaimer_acceptance(client: TestClient) -> None:
    case_response = client.post("/cases", json={"title": "Disclaimer guard"})
    case_id = case_response.json()["id"]
    response = client.post(f"/cases/{case_id}/analysis", json={"accepted_legal_disclaimer": False})
    assert response.status_code == 422
    assert "Legal disclaimer acceptance is required" in response.text


def test_report_generation_endpoint_stores_downloadable_pdf(client: TestClient) -> None:
    case_response = client.post("/cases", json={"title": "Downloadable report"})
    case_id = case_response.json()["id"]
    response = client.post(
        f"/cases/{case_id}/report",
        json={"accepted_legal_disclaimer": True, "force_regenerate": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["report_reference"].startswith("MRA-")
    assert payload["content"]["warning"] == "AI-assisted, not official verification"
    assert payload["is_stale"] is False

    download_response = client.get(f"/cases/{case_id}/report.pdf")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/pdf"
    assert download_response.content.startswith(b"%PDF")


def test_security_headers_are_set(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]


def test_field_correction_does_not_overwrite_ai_extraction(client: TestClient) -> None:
    db = SessionLocal()
    try:
        user = User(clerk_user_id="dev-user", email="dev@example.test", full_name="Dev User")
        db.add(user)
        db.flush()
        land_case = LandCase(owner_user_id=user.id, title="Correction case")
        db.add(land_case)
        db.flush()
        document = Document(
            case_id=land_case.id,
            uploaded_by_user_id=user.id,
            category=DocumentCategory.TITLE_DEED,
            filename="title.pdf",
            content_type="application/pdf",
            file_size=100,
            storage_uri="local://clean/title.pdf",
            status=DocumentStatus.EXTRACTED,
        )
        db.add(document)
        db.flush()
        field = ExtractedField(
            document_id=document.id,
            field_name="parcel_number",
            value="LR 209/1234",
            normalized_value="LR 209/1234",
            confidence=0.78,
            source="native_text",
            page_number=1,
            text_snippet="Parcel No: LR 209/1234",
        )
        db.add(field)
        db.commit()

        response = client.post(
            f"/documents/{document.id}/corrections",
            json={
                "extracted_field_id": field.id,
                "field_name": "parcel_number",
                "corrected_value": "LR 209/1234/5",
                "reason": "Confirmed by buyer review",
            },
        )
        assert response.status_code == 201
        payload = response.json()
        assert payload["ai_value"] == "LR 209/1234"
        assert payload["corrected_value"] == "LR 209/1234/5"
        db.refresh(field)
        assert field.value == "LR 209/1234"
    finally:
        db.close()


def test_risk_analysis_endpoint_persists_versioned_result(client: TestClient) -> None:
    db = SessionLocal()
    try:
        user = User(clerk_user_id="dev-user", email="dev@example.test", full_name="Dev User")
        db.add(user)
        db.flush()
        land_case = LandCase(
            owner_user_id=user.id,
            title="Risk endpoint case",
            seller_name="John Mwangi",
            parcel_number_claimed="LR 209/1234",
        )
        db.add(land_case)
        db.flush()
        document = Document(
            case_id=land_case.id,
            uploaded_by_user_id=user.id,
            category=DocumentCategory.TITLE_DEED,
            filename="title.pdf",
            content_type="application/pdf",
            file_size=100,
            storage_uri="local://clean/title.pdf",
            status=DocumentStatus.EXTRACTED,
        )
        db.add(document)
        db.flush()
        db.add(
            ExtractedField(
                document_id=document.id,
                field_name="parcel_number",
                value="LR 209/1234",
                normalized_value="LR 209/1234",
                confidence=0.9,
                source="fixture",
            )
        )
        db.commit()

        response = client.post(f"/api/cases/{land_case.id}/risk-analysis")
        assert response.status_code == 200
        payload = response.json()
        assert payload["case_id"] == land_case.id
        assert payload["version"].startswith("mradi-risk-engine")
        assert "risk_score" in payload
        assert db.query(RiskAnalysisResult).filter(RiskAnalysisResult.case_id == land_case.id).count() == 1
    finally:
        db.close()
