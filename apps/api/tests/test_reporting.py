from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from app.domain.enums import RiskBand, RiskFactorCode, VerificationStatus
from app.models import LandCase, RiskFactor
from app.services.reporting import LEGAL_DISCLAIMER, build_report_content, finalize_report_content, render_report_pdf


def test_report_contains_legal_safety_disclaimer() -> None:
    case = LandCase(id="case-1", owner_user_id="user-1", title="Test parcel")
    content = build_report_content(
        case=case,
        score=25,
        band=RiskBand.LOW,
        verification_status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
        factors=[],
        language="en",
    )
    assert content["legal_disclaimer"] == LEGAL_DISCLAIMER
    assert "not independently verified" in content["summary"]["plain_english"]
    assert content["brand"] == "Mradi wa Ardhi"
    assert content["warning"] == "AI-assisted, not official verification"
    assert content["case_summary"]["risk_score"] == 25
    assert "appendix_evidence_references" in content
    pdf = render_report_pdf(content)
    assert pdf.startswith(b"%PDF")


def test_pdf_report_contains_buyer_critical_sections_and_evidence() -> None:
    case = LandCase(
        id="case-1",
        owner_user_id="user-1",
        title="Seller mismatch parcel",
        buyer_name="Jane Wanjiku",
        seller_name="John Mwangi",
        parcel_number_claimed="LR 209/1234",
        location_county="Kajiado",
    )
    factor = RiskFactor(
        case_id=case.id,
        code=RiskFactorCode.SELLER_NAME_MISMATCH,
        label="Seller does not match official owner",
        severity="critical",
        points=30,
        evidence={
            "evidence": [
                {
                    "document_id": "search",
                    "document_category": "land_search_certificate",
                    "field_name": "owner_name",
                    "value": "Grace Achieng",
                    "text_snippet": "Owner: Grace Achieng",
                }
            ],
            "explanation": "The search owner and seller name differ.",
        },
        recommendation="Ask a licensed advocate to confirm the registered owner before releasing money or signing.",
    )
    content = finalize_report_content(
        build_report_content(
            case=case,
            score=81,
            band=RiskBand.CRITICAL,
            verification_status=VerificationStatus.CONFLICT_FOUND,
            factors=[factor],
            language="en",
        ),
        case_id=case.id,
        analysis_run_id="analysis-1",
    )

    pdf = render_report_pdf(content)
    reader = PdfReader(BytesIO(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert len(reader.pages) >= 2
    assert "Mradi wa Ardhi" in text
    assert "AI-assisted, not official verification" in text
    assert "Seller does not match official owner" in text
    assert "Legal Disclaimer" in text
    assert "Grace Achieng" in text
