from __future__ import annotations

from hashlib import sha256

from app.domain.enums import DocumentStatus

VALID_TINY_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def test_successful_pdf_upload_moves_from_quarantine_to_clean_storage(client) -> None:  # type: ignore[no-untyped-def]
    case_response = client.post("/cases", json={"title": "Successful upload case"})
    case_id = case_response.json()["id"]
    digest = sha256(VALID_TINY_PDF).hexdigest()

    signed_response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "title.pdf",
            "content_type": "application/pdf",
            "file_size": len(VALID_TINY_PDF),
            "sha256": digest,
            "consent_to_process": True,
        },
    )
    assert signed_response.status_code == 200
    signed = signed_response.json()

    upload_response = client.put(
        signed["upload_url"],
        content=VALID_TINY_PDF,
        headers=signed["headers"],
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["sha256"] == digest

    complete_response = client.post(
        "/uploads/complete",
        json={"document_id": signed["document_id"], "sha256": digest},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == DocumentStatus.CLEAN.value
    assert complete_response.json()["scan_status"] == "not_configured"

    case_payload = client.get(f"/cases/{case_id}").json()
    [document] = case_payload["documents"]
    assert document["status"] == DocumentStatus.CLEAN.value
    assert document["sha256"] == digest


def test_local_signed_read_uses_private_download_headers(client) -> None:  # type: ignore[no-untyped-def]
    case_response = client.post("/cases", json={"title": "Signed read case"})
    case_id = case_response.json()["id"]
    digest = sha256(VALID_TINY_PDF).hexdigest()
    signed_response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "title.pdf",
            "content_type": "application/pdf",
            "file_size": len(VALID_TINY_PDF),
            "sha256": digest,
            "consent_to_process": True,
        },
    )
    signed = signed_response.json()
    assert client.put(signed["upload_url"], content=VALID_TINY_PDF, headers=signed["headers"]).status_code == 200
    assert client.post("/uploads/complete", json={"document_id": signed["document_id"], "sha256": digest}).status_code == 200

    read_url_response = client.get(f"/documents/{signed['document_id']}/read-url")
    assert read_url_response.status_code == 200
    response = client.get(read_url_response.json()["read_url"])

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content.startswith(b"%PDF")


def test_signed_upload_rejects_content_type_drift(client) -> None:  # type: ignore[no-untyped-def]
    case_response = client.post("/cases", json={"title": "Content type drift"})
    case_id = case_response.json()["id"]
    signed_response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "title.pdf",
            "content_type": "application/pdf",
            "file_size": len(VALID_TINY_PDF),
            "consent_to_process": True,
        },
    )
    assert signed_response.status_code == 200
    signed = signed_response.json()

    response = client.put(
        signed["upload_url"],
        content=VALID_TINY_PDF,
        headers={"content-type": "image/png"},
    )

    assert response.status_code == 415
    assert "content type does not match" in response.text.lower()


def test_upload_completion_rejects_sha256_mismatch(client) -> None:  # type: ignore[no-untyped-def]
    case_response = client.post("/cases", json={"title": "SHA mismatch"})
    case_id = case_response.json()["id"]
    signed_response = client.post(
        "/uploads/signed-url",
        json={
            "case_id": case_id,
            "category": "title_deed",
            "filename": "title.pdf",
            "content_type": "application/pdf",
            "file_size": len(VALID_TINY_PDF),
            "consent_to_process": True,
        },
    )
    assert signed_response.status_code == 200
    signed = signed_response.json()
    upload_response = client.put(
        signed["upload_url"],
        content=VALID_TINY_PDF,
        headers=signed["headers"],
    )
    assert upload_response.status_code == 200

    response = client.post(
        "/uploads/complete",
        json={"document_id": signed["document_id"], "sha256": "0" * 64},
    )

    assert response.status_code == 400
    assert "SHA-256 mismatch" in response.text
