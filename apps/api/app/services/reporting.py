from __future__ import annotations

import html
import io
import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.enums import RiskBand, VerificationStatus
from app.models import (
    Document,
    ExtractedField,
    FieldCorrection,
    GazetteSearch,
    GazetteSearchResult,
    LandCase,
    Report,
    RiskAnalysisResult,
    RiskFactor,
    VerificationAttempt,
)

BRAND_NAME = "Mradi wa Ardhi"
REPORT_SCHEMA_VERSION = "mradi-report-v1"
AI_WARNING = "AI-assisted, not official verification"

LEGAL_DISCLAIMER = (
    "This report is an AI-assisted risk analysis. It does not replace an official land search, "
    "licensed advocate, licensed surveyor, or the Ministry of Lands/National Land Commission."
)

BAND_COLORS = {
    "low": "#16803c",
    "medium": "#b7791f",
    "high": "#c05621",
    "critical": "#c53030",
}

SEVERITY_COLORS = {
    "low": "#e7f7ee",
    "medium": "#fff8dc",
    "high": "#fff0df",
    "critical": "#fde8e8",
}


def build_report_content(
    *,
    case: LandCase,
    score: int,
    band: RiskBand,
    verification_status: VerificationStatus,
    factors: list[RiskFactor],
    language: str,
    agent_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    agent_context = agent_context or {}
    generated_at = datetime.now(UTC).isoformat()
    report_id = agent_context.get("report_id", "")
    verification_value = _enum_value(verification_status)
    band_value = _enum_value(band)
    risk_factors = _risk_factor_payloads(factors, agent_context.get("risk_factors"))
    document_checklist = _json_safe(agent_context.get("document_checklist", []))
    extracted_documents = _json_safe(agent_context.get("extracted_documents", []))
    consistency = _json_safe(agent_context.get("inconsistencies", {}))
    gazette = _json_safe(agent_context.get("gazette_results", {}))
    official_search = _json_safe(agent_context.get("official_search", {}))
    missing_documents = _missing_documents(document_checklist, consistency, agent_context.get("missing_documents"))
    documents_reviewed = _documents_reviewed(document_checklist, extracted_documents)
    extracted_information = _extracted_information(extracted_documents)
    inconsistencies_found = _inconsistencies_found(consistency)
    gazette_summary = _gazette_search_results(gazette)
    official_review = _official_search_certificate_review(official_search)
    search_certificate_intelligence = _search_certificate_intelligence(case, official_review)
    gazette_intelligence = _gazette_risk_intelligence(gazette_summary)
    trust_evidence_panel = _trust_evidence_panel(
        risk_factors=risk_factors,
        extracted_documents=extracted_documents,
        official_search=official_review,
        gazette=gazette_summary,
    )
    risk_factors = _attach_trust_evidence(risk_factors, trust_evidence_panel)
    verification_status_labels = _verification_status_labels(
        verification_status=verification_status,
        extracted_documents=extracted_documents,
        inconsistencies_found=inconsistencies_found,
        official_search=official_review,
        gazette=gazette_summary,
        risk_factors=risk_factors,
    )
    before_deposit_warnings = _before_deposit_warnings(
        missing_documents=missing_documents,
        risk_factors=risk_factors,
        official_search=official_review,
        search_certificate=search_certificate_intelligence,
        gazette=gazette_summary,
        score=score,
        band_value=band_value,
    )
    recommended_next_steps = _dedupe(
        [
            *_string_list(agent_context.get("recommended_next_actions", [])),
            "Obtain or refresh the official land search certificate.",
            "Have an advocate verify the seller, title, consents, and completion documents.",
            "Have a surveyor confirm boundaries, mutation forms, and survey maps where relevant.",
            "Do not release purchase funds until official and professional checks are complete.",
        ]
    )
    confidence_scores = _confidence_score_payload(extracted_documents)
    kiswahili_summaries = _kiswahili_summaries(
        score=score,
        band_value=band_value,
        warnings=before_deposit_warnings,
        next_steps=recommended_next_steps,
        missing_documents=missing_documents,
    )
    human_review_workflow = _human_review_workflow(before_deposit_warnings, risk_factors)
    plain_english = _plain_summary(score, band, verification_status)
    sw_summary = ""
    if language == "sw":
        sw_summary = kiswahili_summaries["risk_report"]
    case_summary = {
        "case_id": getattr(case, "id", ""),
        "case_title": getattr(case, "title", ""),
        "county": getattr(case, "location_county", ""),
        "location": getattr(case, "location", ""),
        "transaction_value": _money(getattr(case, "transaction_value", None)),
        "documents_reviewed_count": len(documents_reviewed),
        "verification_status": verification_value,
        "risk_score": score,
        "risk_level": band_value,
    }
    buyer_seller_details = {
        "buyer_name": getattr(case, "buyer_name", "") or "Not recorded",
        "seller_name": getattr(case, "seller_name", "") or "Not recorded",
    }
    parcel_title_details = {
        "parcel_number_claimed": getattr(case, "parcel_number_claimed", "") or "Not recorded",
        "title_number": getattr(case, "title_number", "") or _first_extracted_value(extracted_documents, "title_number") or "Not recorded",
        "county": getattr(case, "location_county", "") or _first_extracted_value(extracted_documents, "county") or "Not recorded",
        "registry": _first_extracted_value(extracted_documents, "registry") or "Not recorded",
        "land_size": _first_extracted_value(extracted_documents, "land_size") or "Not recorded",
    }
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "brand": BRAND_NAME,
        "report_id": report_id,
        "warning": AI_WARNING,
        "title": f"Land Risk Report: {case.title}",
        "generated_at": generated_at,
        "summary": {
            "score": score,
            "band": band_value,
            "verification_status": verification_value,
            "plain_english": plain_english,
            "kiswahili": sw_summary,
        },
        "case_summary": case_summary,
        "buyer_seller_details": buyer_seller_details,
        "parcel_title_details": parcel_title_details,
        "case": {
            "buyer_name": case.buyer_name,
            "seller_name": case.seller_name,
            "parcel_number_claimed": case.parcel_number_claimed,
            "location_county": case.location_county,
            "location": getattr(case, "location", ""),
            "title_number": getattr(case, "title_number", ""),
            "transaction_value": _money(getattr(case, "transaction_value", None)),
        },
        "documents_reviewed": documents_reviewed,
        "extracted_information": extracted_information,
        "missing_documents": missing_documents,
        "inconsistencies_found": inconsistencies_found,
        "gazette_search_results": gazette_summary,
        "gazette_risk_intelligence": gazette_intelligence,
        "official_search_certificate_review": official_review,
        "search_certificate_intelligence": search_certificate_intelligence,
        "verification_status_labels": verification_status_labels,
        "before_deposit_warnings": before_deposit_warnings,
        "trust_evidence_panel": trust_evidence_panel,
        "confidence_scores": confidence_scores,
        "human_review_workflow": human_review_workflow,
        "risk_score": score,
        "risk_level": band_value,
        "risk_factors": risk_factors,
        "detailed_risk_factors": risk_factors,
        "recommended_next_steps": recommended_next_steps,
        "plain_english_explanation": plain_english,
        "kiswahili_summary": sw_summary,
        "kiswahili_summaries": kiswahili_summaries,
        "legal_disclaimer": LEGAL_DISCLAIMER,
        "appendix_evidence_references": _evidence_references(
            risk_factors=risk_factors,
            extracted_documents=extracted_documents,
            official_search=official_search,
            inconsistencies=consistency,
        ),
        "document_checklist": document_checklist,
        "extracted_documents": extracted_documents,
        "inconsistencies": consistency,
        "gazette_results": gazette,
        "official_search": official_search,
    }


def _plain_summary(score: int, band: RiskBand, verification_status: VerificationStatus) -> str:
    if verification_status != VerificationStatus.VERIFIED:
        verification = "The system has not independently verified ownership from an official registry API."
    else:
        verification = "An official source check has been recorded."
    return f"The transaction currently scores {score}/100 ({band.value} risk). {verification}"


def finalize_report_content(content: dict[str, Any], *, case_id: str, analysis_run_id: str) -> dict[str, Any]:
    report_id = content.get("report_id") or f"MRA-{case_id[:8].upper()}-{analysis_run_id[:8].upper()}"
    finalized = dict(content)
    finalized["report_id"] = report_id
    finalized["brand"] = finalized.get("brand") or BRAND_NAME
    finalized["warning"] = finalized.get("warning") or AI_WARNING
    finalized["schema_version"] = finalized.get("schema_version") or REPORT_SCHEMA_VERSION
    return finalized


def report_stale_reasons(db: Session, *, case: LandCase, report: Report) -> list[str]:
    reasons: list[str] = []

    def changed_after(timestamp: datetime | None) -> bool:
        return bool(timestamp and timestamp > report.created_at)

    if changed_after(case.updated_at):
        reasons.append("Case details changed after this report was generated.")

    document_updated_at = db.query(func.max(Document.updated_at)).filter(Document.case_id == case.id).scalar()
    if changed_after(document_updated_at):
        reasons.append("Uploaded documents or document review status changed after this report was generated.")

    field_updated_at = (
        db.query(func.max(ExtractedField.updated_at))
        .join(Document, ExtractedField.document_id == Document.id)
        .filter(Document.case_id == case.id)
        .scalar()
    )
    correction_updated_at = (
        db.query(func.max(FieldCorrection.updated_at))
        .join(Document, FieldCorrection.document_id == Document.id)
        .filter(Document.case_id == case.id)
        .scalar()
    )
    if changed_after(field_updated_at) or changed_after(correction_updated_at):
        reasons.append("Extracted or corrected document information changed after this report was generated.")

    gazette_updated_at = db.query(func.max(GazetteSearch.updated_at)).filter(GazetteSearch.case_id == case.id).scalar()
    gazette_result_updated_at = (
        db.query(func.max(GazetteSearchResult.updated_at)).filter(GazetteSearchResult.case_id == case.id).scalar()
    )
    if changed_after(gazette_updated_at) or changed_after(gazette_result_updated_at):
        reasons.append("Gazette search evidence changed after this report was generated.")

    verification_updated_at = (
        db.query(func.max(VerificationAttempt.updated_at)).filter(VerificationAttempt.case_id == case.id).scalar()
    )
    if changed_after(verification_updated_at):
        reasons.append("Official-source or verification evidence changed after this report was generated.")

    risk_updated_at = (
        db.query(func.max(RiskAnalysisResult.updated_at))
        .filter(RiskAnalysisResult.case_id == case.id, RiskAnalysisResult.created_at > report.created_at)
        .scalar()
    )
    if changed_after(risk_updated_at):
        reasons.append("A newer risk analysis exists after this report was generated.")

    return _dedupe(reasons)


def render_report_pdf(content: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=content["title"],
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
    )
    story: list[Any] = []

    story.extend(_cover_page(content, styles))
    story.append(PageBreak())
    _add_section(story, styles, "1. Case Summary")
    story.append(_key_value_table(content.get("case_summary", {}), styles))
    story.append(Spacer(1, 8))
    _add_warning(story, styles)

    _add_section(story, styles, "2. Buyer And Seller Details")
    story.append(_key_value_table(content.get("buyer_seller_details", {}), styles))

    _add_section(story, styles, "3. Parcel/Title Details")
    story.append(_key_value_table(content.get("parcel_title_details", {}), styles))

    _add_section(story, styles, "4. Documents Reviewed")
    story.append(_documents_table(content.get("documents_reviewed", []), styles))

    _add_section(story, styles, "5. Extracted Information")
    _append_extracted_information(story, content.get("extracted_information", []), styles)

    _add_section(story, styles, "6. Missing Documents")
    story.append(_findings_table(content.get("missing_documents", []), styles, empty="No missing required documents were recorded."))

    _add_section(story, styles, "7. Inconsistencies Found")
    story.append(
        _findings_table(
            content.get("inconsistencies_found", []),
            styles,
            empty="No material inconsistencies were recorded from the uploaded documents.",
        )
    )

    _add_section(story, styles, "8. Gazette Search Results")
    _append_gazette(story, content.get("gazette_search_results", {}), styles)

    _add_section(story, styles, "9. Official Search Certificate Review")
    _append_official_search(story, content.get("official_search_certificate_review", {}), styles)

    _add_section(story, styles, "10. Before You Pay Deposit Warning")
    story.append(
        _findings_table(
            content.get("before_deposit_warnings", []),
            styles,
            empty="No automated deposit-stopper warning was triggered. Continue with official and professional checks.",
        )
    )

    _add_section(story, styles, "11. Verification Status Labels")
    story.append(_status_label_table(content.get("verification_status_labels", []), styles))

    _add_section(story, styles, "12. Risk Score")
    story.append(RiskMeterFlowable(content.get("risk_score", 0), content.get("risk_level", "not recorded")))
    story.append(Spacer(1, 8))
    story.append(
        _small_table(
            [["Score", f"{content.get('risk_score', 0)}/100"], ["Risk level", str(content.get("risk_level", "")).title()]],
            styles,
        )
    )

    _add_section(story, styles, "13. Risk Level")
    story.append(_risk_level_panel(content, styles))

    _add_section(story, styles, "14. Detailed Risk Factors")
    story.append(_risk_factor_table(content.get("detailed_risk_factors") or content.get("risk_factors", []), styles))

    _add_section(story, styles, "15. Trust Evidence Panel")
    story.append(_trust_evidence_table(content.get("trust_evidence_panel", []), styles))

    _add_section(story, styles, "16. Recommended Next Actions")
    _append_bullets(story, content.get("recommended_next_steps", []), styles)

    _add_section(story, styles, "17. Plain-English Explanation")
    plain_english = content.get("plain_english_explanation") or content.get("summary", {}).get("plain_english", "")
    story.append(_paragraph(plain_english, styles["BodyText"]))

    if content.get("kiswahili_summary") or content.get("summary", {}).get("kiswahili"):
        _add_section(story, styles, "18. Optional Kiswahili Summary")
        story.append(_paragraph(content.get("kiswahili_summary") or content.get("summary", {}).get("kiswahili", ""), styles["BodyText"]))

    _add_section(story, styles, "19. Legal Disclaimer")
    story.append(_paragraph(content.get("legal_disclaimer", LEGAL_DISCLAIMER), styles["BodyText"]))

    _add_section(story, styles, "20. Appendix With Evidence References")
    story.append(_evidence_table(content.get("appendix_evidence_references", []), styles))

    doc.build(story, onFirstPage=_draw_header_footer(content), onLaterPages=_draw_header_footer(content))
    return buffer.getvalue()


class RiskMeterFlowable(Flowable):  # type: ignore[misc]
    def __init__(self, score: int, band: str, width: float = 155 * mm, height: float = 26 * mm) -> None:
        super().__init__()
        self.score = max(0, min(int(score or 0), 100))
        self.band = str(band or "not recorded")
        self.width = width
        self.height = height

    def draw(self) -> None:
        canvas = self.canv
        segment_width = self.width / 4
        labels = [("Low", "#16803c"), ("Medium", "#b7791f"), ("High", "#c05621"), ("Critical", "#c53030")]
        y = 14 * mm
        canvas.saveState()
        for index, (label, color) in enumerate(labels):
            x = index * segment_width
            canvas.setFillColor(colors.HexColor(color))
            canvas.roundRect(x, y, segment_width - 1, 6 * mm, 2, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#334155"))
            canvas.setFont("Helvetica", 7)
            canvas.drawString(x, y - 4 * mm, label)
        marker_x = (self.score / 100) * self.width
        canvas.setFillColor(colors.HexColor("#0f172a"))
        canvas.circle(marker_x, y + 3 * mm, 3.2, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(0, 2 * mm, f"{self.score}/100")
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor(BAND_COLORS.get(self.band.lower(), "#475569")))
        canvas.drawString(28 * mm, 3 * mm, f"{self.band.title()} risk")
        canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        **sample.byName,
        "Brand": ParagraphStyle(
            "Brand",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            textColor=colors.HexColor("#12372a"),
            leading=18,
        ),
        "ReportTitle": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            alignment=TA_LEFT,
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8,
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#12372a"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "Small": ParagraphStyle("Small", parent=sample["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#475569")),
        "Warning": ParagraphStyle(
            "Warning",
            parent=sample["BodyText"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#92400e"),
            backColor=colors.HexColor("#fff7ed"),
            borderColor=colors.HexColor("#fdba74"),
            borderPadding=6,
            borderWidth=0.5,
        ),
        "Center": ParagraphStyle("Center", parent=sample["BodyText"], alignment=TA_CENTER),
    }


def _cover_page(content: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    generated = _format_datetime(content.get("generated_at"))
    case_summary = content.get("case_summary", {})
    story: list[Any] = [
        Spacer(1, 20 * mm),
        Paragraph(BRAND_NAME, styles["Brand"]),
        Spacer(1, 5 * mm),
        Paragraph(_escape(content.get("title", "Land Risk Report")), styles["ReportTitle"]),
        Spacer(1, 2 * mm),
        Paragraph(_escape(content.get("summary", {}).get("plain_english", "")), styles["BodyText"]),
        Spacer(1, 7 * mm),
        _warning_table(styles),
        Spacer(1, 8 * mm),
        RiskMeterFlowable(
            content.get("risk_score") or content.get("summary", {}).get("score", 0),
            content.get("risk_level") or content.get("summary", {}).get("band", ""),
        ),
        Spacer(1, 9 * mm),
        _small_table(
            [
                ["Report ID", content.get("report_id") or "Pending"],
                ["Generated", generated],
                ["Case", case_summary.get("case_title") or content.get("title", "")],
                ["Parcel/title", case_summary.get("case_id", "")],
                ["Warning", AI_WARNING],
            ],
            styles,
        ),
        Spacer(1, 8 * mm),
        Paragraph(
            "Prepared for decision support by buyers, advocates, surveyors, SACCOs, banks, and family reviewers.",
            styles["Small"],
        ),
    ]
    return story


def _draw_header_footer(content: dict[str, Any]) -> Callable[[Any, SimpleDocTemplate], None]:
    def draw(canvas: Any, doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        width, height = A4
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#12372a"))
        canvas.drawString(doc.leftMargin, height - 10 * mm, BRAND_NAME)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#92400e"))
        canvas.drawRightString(width - doc.rightMargin, height - 10 * mm, AI_WARNING)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, 9 * mm, f"Report ID: {content.get('report_id') or 'Pending'}")
        canvas.drawRightString(width - doc.rightMargin, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    return draw


def _add_section(story: list[Any], styles: dict[str, ParagraphStyle], title: str) -> None:
    story.append(Paragraph(_escape(title), styles["SectionHeading"]))


def _add_warning(story: list[Any], styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph(AI_WARNING, styles["Warning"]))


def _warning_table(styles: dict[str, ParagraphStyle]) -> Table:
    return _table(
        [
            [
                Paragraph(
                    "<b>AI-assisted, not official verification.</b> "
                    "Use this report with official registry checks and professional review.",
                    styles["BodyText"],
                )
            ]
        ],
        [168 * mm],
        header=False,
        background="#fff7ed",
        border="#fdba74",
    )


def _key_value_table(values: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [[_label(key), _display(value)] for key, value in values.items()]
    return _small_table(rows or [["Status", "No information recorded."]], styles)


def _small_table(rows: list[list[Any]], styles: dict[str, ParagraphStyle]) -> Table:
    return _table(
        [[_cell(item, styles) for item in row] for row in rows],
        [50 * mm, 112 * mm],
        header=False,
    )


def _documents_table(documents: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    if not documents:
        return _table([[Paragraph("No documents were reviewed for this report.", styles["BodyText"])]], [162 * mm], header=False)
    rows: list[list[Any]] = [["Document", "Filename", "Status", "Extraction"]]
    for doc in documents:
        rows.append(
            [
                _label(doc.get("category", "")),
                doc.get("filename") or "Not recorded",
                doc.get("status") or ("Uploaded" if doc.get("uploaded") else "Missing"),
                doc.get("confidence_label") or doc.get("quality_label") or "Not recorded",
            ]
        )
    return _table([[_cell(item, styles) for item in row] for row in rows], [42 * mm, 56 * mm, 28 * mm, 36 * mm])


def _append_extracted_information(story: list[Any], items: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> None:
    if not items:
        story.append(Paragraph("No structured information was extracted from uploaded documents.", styles["BodyText"]))
        return
    for item in items[:12]:
        rows = [["Field", "Value"]]
        for field in item.get("fields", [])[:14]:
            rows.append([_label(field.get("name", "")), _display(field.get("value"))])
        story.append(
            KeepTogether(
                [
                    Paragraph(_escape(item.get("document_label", "Document")), styles["Small"]),
                    _small_table(rows, styles),
                ]
            )
        )
        story.append(Spacer(1, 5))


def _findings_table(items: list[dict[str, Any]], styles: dict[str, ParagraphStyle], *, empty: str) -> Table:
    if not items:
        return _table([[Paragraph(_escape(empty), styles["BodyText"])]], [162 * mm], header=False)
    rows: list[list[Any]] = [["Finding", "Severity", "Explanation"]]
    for item in items:
        rows.append(
            [
                item.get("label") or _label(item.get("category") or item.get("code") or "Finding"),
                item.get("severity") or "review",
                item.get("explanation") or item.get("reason") or item.get("summary") or _compact_json(item),
            ]
        )
    return _table([[_cell(value, styles) for value in row] for row in rows], [48 * mm, 28 * mm, 86 * mm])


def _append_gazette(story: list[Any], gazette: dict[str, Any], styles: dict[str, ParagraphStyle]) -> None:
    if not gazette:
        story.append(Paragraph("Gazette search results were not available for this report.", styles["BodyText"]))
        return
    story.append(
        _small_table(
            [
                ["Status", gazette.get("status") or "Not checked"],
                ["Reason", gazette.get("reason") or gazette.get("message") or "No reason recorded."],
                ["Query terms", ", ".join(gazette.get("query_terms", [])[:12]) or "No query terms recorded."],
            ],
            styles,
        )
    )
    notices = gazette.get("notices") or gazette.get("results") or []
    if notices:
        rows: list[list[Any]] = [["Source", "Notice", "Date", "Snippet"]]
        for notice in notices[:8]:
            rows.append(
                [
                    notice.get("source") or notice.get("source_name") or "Source",
                    notice.get("title") or notice.get("notice_title") or "Notice",
                    notice.get("date") or notice.get("publication_date") or "",
                    notice.get("snippet") or "",
                ]
        )
        story.append(Spacer(1, 6))
        story.append(_table([[_cell(item, styles) for item in row] for row in rows], [30 * mm, 48 * mm, 24 * mm, 60 * mm]))


def _append_official_search(story: list[Any], official: dict[str, Any], styles: dict[str, ParagraphStyle]) -> None:
    if not official:
        story.append(Paragraph("No official search certificate review was recorded.", styles["BodyText"]))
        return
    story.append(
        _small_table(
            [
                ["Status", official.get("official_search_status") or "Not recorded"],
                ["Verification status", official.get("verification_status") or "Not recorded"],
                ["Review note", official.get("reason") or "No review note recorded."],
            ],
            styles,
        )
    )
    certificate = official.get("certificate") or {}
    if certificate:
        story.append(Spacer(1, 6))
        story.append(
            _small_table(
                [
                    ["Owner names", ", ".join(certificate.get("owner_names", [])) or "Not recorded"],
                    ["Parcel number", certificate.get("parcel_number") or "Not recorded"],
                    ["Title number", certificate.get("title_number") or "Not recorded"],
                    ["Date issued", certificate.get("date_issued") or "Not recorded"],
                    ["Encumbrances", ", ".join(certificate.get("encumbrances", [])) or "None recorded"],
                ],
                styles,
            )
        )
    conflicts = official.get("conflicts") or []
    if conflicts:
        story.append(Spacer(1, 6))
        story.append(_findings_table(conflicts, styles, empty="No conflicts recorded."))


def _risk_level_panel(content: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    band = str(content.get("risk_level") or content.get("summary", {}).get("band") or "not recorded")
    color = BAND_COLORS.get(band.lower(), "#64748b")
    text = (
        f"The case is currently classified as {band.upper()} risk. "
        "Higher risk means the buyer should pause, collect missing evidence, and escalate to official or professional "
        "review before paying or signing."
    )
    table = _table(
        [[Paragraph(_escape(text), styles["BodyText"])]],
        [162 * mm],
        header=False,
        background=SEVERITY_COLORS.get(band.lower(), "#f8fafc"),
        border=color,
    )
    return table


def _risk_factor_table(factors: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    if not factors:
        return _table([[Paragraph("No risk factors were recorded for this report.", styles["BodyText"])]], [162 * mm], header=False)
    rows: list[list[Any]] = [["Factor", "Severity", "Points", "Recommendation"]]
    for factor in factors:
        rows.append(
            [
                factor.get("label", "Risk factor"),
                factor.get("severity", "review"),
                str(factor.get("points", 0)),
                factor.get("recommendation", "Review with a professional."),
            ]
        )
    table = _table([[_cell(item, styles) for item in row] for row in rows], [50 * mm, 26 * mm, 18 * mm, 68 * mm])
    for row_index, factor in enumerate(factors, start=1):
        color = SEVERITY_COLORS.get(str(factor.get("severity", "")).lower())
        if color:
            table.setStyle(TableStyle([("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor(color))]))
    return table


def _status_label_table(labels: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    if not labels:
        return _table([[Paragraph("No verification labels were recorded.", styles["BodyText"])]], [162 * mm], header=False)
    rows: list[list[Any]] = [["Label", "Status", "Explanation"]]
    for item in labels:
        rows.append(
            [
                item.get("label", "Status"),
                "Recorded" if item.get("applies") else "Not recorded",
                item.get("explanation", ""),
            ]
        )
    return _table([[_cell(value, styles) for value in row] for row in rows], [42 * mm, 28 * mm, 92 * mm])


def _trust_evidence_table(rows: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    if not rows:
        return _table([[Paragraph("No risk-factor evidence rows were recorded.", styles["BodyText"])]], [162 * mm], header=False)
    table_rows: list[list[Any]] = [["Risk", "Document", "Extracted", "Compared", "Action"]]
    for row in rows[:18]:
        confidence = row.get("confidence_score")
        confidence_label = f" ({_percent(confidence)})" if confidence not in (None, "") else ""
        table_rows.append(
            [
                row.get("risk_label") or row.get("risk_code") or "Risk",
                row.get("document_caused") or "Case evidence",
                f"{row.get('extracted_value') or 'Not recorded'}{confidence_label}",
                row.get("compared_value") or "Not recorded",
                row.get("recommended_action") or "Review with a professional.",
            ]
        )
    return _table([[_cell(value, styles) for value in row] for row in table_rows], [34 * mm, 35 * mm, 32 * mm, 31 * mm, 30 * mm])


def _append_bullets(story: list[Any], items: list[str], styles: dict[str, ParagraphStyle]) -> None:
    if not items:
        story.append(Paragraph("No next actions were recorded.", styles["BodyText"]))
        return
    for item in items:
        story.append(Paragraph(f"- {_escape(str(item))}", styles["BodyText"]))


def _evidence_table(items: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Table:
    if not items:
        return _table([[Paragraph("No evidence references were attached.", styles["BodyText"])]], [162 * mm], header=False)
    rows: list[list[Any]] = [["Reference", "Source", "Field", "Evidence"]]
    for index, item in enumerate(items[:40], start=1):
        rows.append(
            [
                f"E{index:03d}",
                item.get("document_category") or item.get("source") or "Case evidence",
                item.get("field_name") or "General",
                item.get("quote") or item.get("text_snippet") or item.get("summary") or _compact_json(item),
            ]
        )
    return _table([[_cell(value, styles) for value in row] for row in rows], [20 * mm, 40 * mm, 32 * mm, 70 * mm])


def _table(
    rows: list[list[Any]],
    widths: list[float],
    *,
    header: bool = True,
    background: str = "#ffffff",
    border: str = "#cbd5e1",
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor(border)),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header and rows:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f3ee")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _cell(value: Any, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return _paragraph(_display(value), styles["Small"])


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_escape(_display(value)), style)


def _escape(value: Any) -> str:
    return html.escape(str(value or ""))


def _display(value: Any) -> str:
    if value is None or value == "":
        return "Not recorded"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(_display(item) for item in value) if value else "None recorded"
    if isinstance(value, dict):
        return _compact_json(value)
    return str(value).replace("_", " ")


def _compact_json(value: Any) -> str:
    if isinstance(value, dict):
        pieces = []
        for key, item in list(value.items())[:5]:
            if item not in (None, "", [], {}):
                pieces.append(f"{_label(key)}: {_display(item)}")
        return "; ".join(pieces) or "No details recorded"
    if isinstance(value, list):
        return "; ".join(_display(item) for item in value[:5]) or "No details recorded"
    return _display(value)


def _label(value: Any) -> str:
    text = str(value or "Not recorded").replace("_", " ").strip()
    return text[:1].upper() + text[1:]


def _format_datetime(value: Any) -> str:
    if not value:
        return "Not recorded"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def _risk_factor_payloads(factors: list[RiskFactor], raw_factors: Any) -> list[dict[str, Any]]:
    if raw_factors:
        return [_json_safe(dict(factor)) for factor in raw_factors]
    return [
        {
            "code": _enum_value(factor.code),
            "label": factor.label,
            "severity": factor.severity,
            "points": factor.points,
            "evidence": _json_safe(factor.evidence),
            "recommendation": factor.recommendation,
        }
        for factor in factors
    ]


def _documents_reviewed(checklist: list[dict[str, Any]], extracted_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in extracted_documents:
        key = str(document.get("document_id") or document.get("category") or len(documents))
        seen.add(str(document.get("category", "")))
        confidence = document.get("extraction_confidence")
        quality = document.get("document_quality_score")
        documents.append(
            {
                "document_id": document.get("document_id", ""),
                "category": document.get("category", ""),
                "filename": document.get("filename", ""),
                "status": "Reviewed",
                "uploaded": True,
                "confidence_label": _percent(confidence),
                "quality_label": _percent(quality),
                "key": key,
            }
        )
    for item in checklist:
        category = str(item.get("category", ""))
        if category and category not in seen:
            documents.append(
                {
                    "category": category,
                    "filename": "",
                    "status": "Uploaded" if item.get("uploaded") else "Missing",
                    "uploaded": bool(item.get("uploaded")),
                    "confidence_label": "",
                }
            )
    return documents


def _extracted_information(extracted_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    field_names = [
        "parcel_number",
        "title_number",
        "registry",
        "county",
        "block",
        "plot_number",
        "owner_names",
        "seller_names",
        "buyer_names",
        "id_numbers",
        "kra_pin",
        "document_dates",
        "transfer_dates",
        "search_dates",
        "land_size",
        "encumbrances",
        "cautions",
        "restrictions",
        "charges",
        "signatures_present",
        "seals_present",
    ]
    output: list[dict[str, Any]] = []
    for document in extracted_documents:
        evidence_by_field: dict[str, list[dict[str, Any]]] = {}
        for ref in document.get("evidence", []) or []:
            if isinstance(ref, dict) and ref.get("field_name"):
                evidence_by_field.setdefault(str(ref.get("field_name")), []).append(ref)
        fields = []
        for name in field_names:
            if document.get(name) in (None, "", [], {}):
                continue
            refs = evidence_by_field.get(name, [])
            fields.append(
                {
                    "name": name,
                    "value": document.get(name),
                    "confidence": _mean_float([ref.get("confidence") for ref in refs]) if refs else document.get("extraction_confidence"),
                    "source": ", ".join(sorted({str(ref.get("source")) for ref in refs if ref.get("source")})) or "extracted_document",
                    "status_labels": _field_status_labels(refs[0], extracted_documents) if refs else ["AI extracted"],
                }
            )
        if fields:
            output.append(
                {
                    "document_id": document.get("document_id", ""),
                    "document_label": f"{_label(document.get('category', 'Document'))}: {document.get('filename') or 'Uploaded file'}",
                    "extraction_confidence": document.get("extraction_confidence"),
                    "document_quality_score": document.get("document_quality_score"),
                    "fields": fields,
                }
            )
    return output


def _missing_documents(
    checklist: list[dict[str, Any]],
    consistency: dict[str, Any],
    explicit_missing: Any,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in _json_safe(explicit_missing or consistency.get("missing_required_documents") or []):
        if isinstance(item, dict):
            output.append(
                {
                    "category": item.get("category", ""),
                    "label": _label(item.get("category", "Missing document")),
                    "severity": item.get("severity", "medium"),
                    "explanation": item.get("explanation", "Required document was not available."),
                }
            )
    known = {item.get("category") for item in output}
    for item in checklist:
        category = item.get("category")
        if category and not item.get("uploaded") and category not in known:
            output.append(
                {
                    "category": category,
                    "label": _label(category),
                    "severity": "high" if category not in {"national_id_or_passport", "kra_pin_certificate"} else "medium",
                    "explanation": f"{_label(category)} was not uploaded or reviewed.",
                }
            )
    return output


def _inconsistencies_found(consistency: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in ("mismatches", "suspicious_date_sequences"):
        for item in consistency.get(key, []) or []:
            if isinstance(item, dict):
                findings.append(
                    {
                        "code": item.get("code", key),
                        "label": item.get("label") or _label(item.get("code", key)),
                        "severity": item.get("severity", "high"),
                        "explanation": item.get("explanation") or _compact_json(item),
                        "values": item.get("values", []),
                    }
                )
    if consistency.get("old_search_certificate"):
        findings.append(
            {
                "code": "old_search_certificate",
                "label": "Old search certificate",
                "severity": "high",
                "explanation": "The uploaded search certificate appears older than the recommended freshness window.",
            }
        )
    if consistency.get("mutation_survey_inconsistency"):
        findings.append(
            {
                "code": "mutation_survey_inconsistency",
                "label": "Mutation or survey inconsistency",
                "severity": "high",
                "explanation": "Mutation form, survey map, or boundary evidence requires surveyor review.",
            }
        )
    return findings


def _gazette_search_results(gazette: dict[str, Any]) -> dict[str, Any]:
    notices = gazette.get("notices") or gazette.get("results") or []
    return {
        "status": gazette.get("gazette_status") or gazette.get("status") or "not_checked",
        "query_terms": gazette.get("query_terms", []),
        "notices": notices,
        "source_results": gazette.get("source_results", []),
        "reason": gazette.get("reason") or gazette.get("message") or "Gazette search was not checked or did not return a recorded note.",
        "checked_at": gazette.get("checked_at", ""),
    }


def _official_search_certificate_review(official: dict[str, Any]) -> dict[str, Any]:
    return {
        "official_search_status": official.get("official_search_status") or "missing",
        "verification_status": official.get("verification_status") or "not_verified_from_official_source",
        "certificate": official.get("certificate"),
        "conflicts": official.get("conflicts", []),
        "reason": official.get("reason") or "No official registry API verification was recorded.",
    }


def _verification_status_labels(
    *,
    verification_status: VerificationStatus,
    extracted_documents: list[dict[str, Any]],
    inconsistencies_found: list[dict[str, Any]],
    official_search: dict[str, Any],
    gazette: dict[str, Any],
    risk_factors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    status_value = _enum_value(verification_status)
    has_extraction = any(document.get("evidence") for document in extracted_documents)
    has_corrections = any(
        ref.get("source") == "user_correction"
        for document in extracted_documents
        for ref in document.get("evidence", []) or []
        if isinstance(ref, dict)
    )
    mismatch_codes = {
        str(item.get("code", ""))
        for item in inconsistencies_found
        if "mismatch" in str(item.get("code", ""))
    }
    checked_gazette = _normalized_gazette_status(gazette) in {"checked_no_match", "checked_match_found"}
    official_uploaded = official_search.get("official_search_status") == "parsed"
    manual_review = (
        status_value in {"manual_review_required", "adapter_unavailable", "conflict_found"}
        or any(str(factor.get("severity")) == "critical" for factor in risk_factors)
    )
    return [
        _verification_label("ai_extracted", "AI extracted", has_extraction, "Structured fields were read from uploaded documents."),
        _verification_label(
            "user_corrected",
            "user corrected",
            has_corrections,
            "A user correction exists for at least one extracted field.",
        ),
        _verification_label(
            "matched_across_documents",
            "matched across documents",
            has_extraction and not mismatch_codes,
            "No parcel, title, seller, owner, or ID mismatch was recorded in the current analysis.",
        ),
        _verification_label(
            "checked_against_gazette",
            "checked against Gazette",
            checked_gazette,
            f"Gazette status: {_normalized_gazette_status(gazette).replace('_', ' ')}.",
        ),
        _verification_label(
            "official_search_uploaded",
            "official search uploaded",
            official_uploaded,
            "An uploaded search certificate was parsed. This is not independent registry API verification.",
        ),
        _verification_label(
            "not_verified_from_official_registry",
            "not verified from official registry",
            status_value != VerificationStatus.VERIFIED.value,
            "No successful official registry ownership verification is recorded for this case.",
            tone="warning",
        ),
        _verification_label(
            "manual_review_required",
            "manual review required",
            manual_review,
            "A professional should review unresolved, high, or critical evidence before funds move.",
            tone="danger" if manual_review else "neutral",
        ),
    ]


def _verification_label(
    code: str,
    label: str,
    applies: bool,
    explanation: str,
    *,
    tone: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "applies": applies,
        "status": "applies" if applies else "not_recorded",
        "tone": tone or ("success" if applies else "neutral"),
        "explanation": explanation,
    }


def _search_certificate_intelligence(case: LandCase, official: dict[str, Any]) -> dict[str, Any]:
    certificate = official.get("certificate") or {}
    uploaded = official.get("official_search_status") == "parsed" and bool(certificate)
    date_issued = certificate.get("date_issued") if isinstance(certificate, dict) else ""
    parsed_date = _parse_date(date_issued)
    older_than_30_days = bool(parsed_date and parsed_date < date.today() - timedelta(days=30))
    owner_names = certificate.get("owner_names", []) if isinstance(certificate, dict) else []
    seller_name = getattr(case, "seller_name", "") or ""
    owner_matches_seller = None
    if uploaded and owner_names and seller_name:
        owner_matches_seller = any(_names_match(str(owner), seller_name) for owner in owner_names)
    encumbrances = certificate.get("encumbrances", []) if isinstance(certificate, dict) else []
    conflicts = official.get("conflicts") or []
    return {
        "status": "uploaded" if uploaded else "missing",
        "uploaded": uploaded,
        "registry_verification_claimed": official.get("verification_status") == VerificationStatus.VERIFIED.value,
        "registry_verification_note": "Official ownership verification is only claimed when an official registry result is recorded.",
        "date_issued": date_issued or "",
        "older_than_30_days": older_than_30_days,
        "owner_names": owner_names,
        "seller_name": seller_name,
        "owner_matches_seller": owner_matches_seller,
        "parcel_number": certificate.get("parcel_number", "") if isinstance(certificate, dict) else "",
        "title_number": certificate.get("title_number", "") if isinstance(certificate, dict) else "",
        "mentions_encumbrances": bool(encumbrances),
        "encumbrances": encumbrances,
        "mentions_cautions_restrictions_or_charges": any(
            word in " ".join(str(item).lower() for item in encumbrances)
            for word in ("caution", "restriction", "charge", "encumbrance")
        ),
        "conflicts": conflicts,
        "recommended_action": _search_certificate_action(uploaded, older_than_30_days, owner_matches_seller, encumbrances, conflicts),
    }


def _search_certificate_action(
    uploaded: bool,
    older_than_30_days: bool,
    owner_matches_seller: bool | None,
    encumbrances: list[Any],
    conflicts: list[Any],
) -> str:
    if not uploaded:
        return "Upload a fresh official search certificate before paying any deposit."
    if older_than_30_days:
        return "Request a fresh official search certificate issued within the last 30 days."
    if owner_matches_seller is False:
        return "Ask an advocate to verify why the seller differs from the owner on the uploaded search certificate."
    if encumbrances or conflicts:
        return "Resolve the certificate conflict, caution, restriction, charge, or encumbrance before completion."
    return "Keep the uploaded search certificate with the file and still confirm official registry status through a qualified professional."


def _gazette_risk_intelligence(gazette: dict[str, Any]) -> dict[str, Any]:
    status = _normalized_gazette_status(gazette)
    return {
        "status": status,
        "query_terms": gazette.get("query_terms", []),
        "notices": gazette.get("notices", []),
        "source_results": gazette.get("source_results", []),
        "reason": gazette.get("reason") or gazette.get("message") or "",
        "manual_review_required": status in {"checked_match_found", "search_failed", "manual_review_required", "not_configured"},
        "searched_fields": _gazette_searched_fields(gazette.get("query_terms", [])),
        "recommended_action": _gazette_action(status),
    }


def _normalized_gazette_status(gazette: dict[str, Any]) -> str:
    raw = str(gazette.get("status") or gazette.get("gazette_status") or "not_checked")
    reason = str(gazette.get("reason") or gazette.get("message") or "").lower()
    if raw in {"checked_match_found", "checked_no_match", "search_failed", "not_configured", "manual_review_required"}:
        return raw
    if raw == "matches_found":
        return "checked_match_found"
    if raw == "checked_no_match":
        return "checked_no_match"
    if raw == "failed":
        return "search_failed"
    if raw == "not_checked" and "not configured" in reason:
        return "not_configured"
    if raw == "not_checked" and ("no parcel" in reason or "no usable" in reason or "no query" in reason):
        return "manual_review_required"
    if raw == "not_checked":
        return "not_configured"
    return "manual_review_required"


def _gazette_action(status: str) -> str:
    if status == "checked_no_match":
        return "Keep the search record, but do not treat Gazette no-match as ownership verification."
    if status == "checked_match_found":
        return "Have an advocate review the Gazette notice before signing or paying."
    if status == "search_failed":
        return "Retry configured Gazette search or perform a manual Gazette review."
    if status == "not_configured":
        return "Configure Gazette sources or route the case to manual Gazette review."
    return "Add stronger parcel, LR/title, owner, county, and location terms, then review manually."


def _gazette_searched_fields(query_terms: list[Any]) -> list[str]:
    labels: set[str] = set()
    for term in query_terms:
        value = str(term)
        if re.search(r"\b(LR|L\.R\.|PLOT|PARCEL|BLOCK|/)\b", value, re.I):
            labels.add("parcel number / LR number")
        elif re.search(r"\bCOUNTY\b", value, re.I):
            labels.add("county")
        elif len(value.split()) >= 2:
            labels.add("owner name / location")
        else:
            labels.add("title number / keyword")
    return sorted(labels)


def _before_deposit_warnings(
    *,
    missing_documents: list[dict[str, Any]],
    risk_factors: list[dict[str, Any]],
    official_search: dict[str, Any],
    search_certificate: dict[str, Any],
    gazette: dict[str, Any],
    score: int,
    band_value: str,
) -> list[dict[str, Any]]:
    missing_categories = {item.get("category") for item in missing_documents}
    factor_codes = {str(factor.get("code")) for factor in risk_factors}

    warnings = [
        _deposit_warning(
            "search_certificate_missing",
            "Search certificate is missing",
            "critical",
            not search_certificate.get("uploaded")
            or "missing_official_land_search" in factor_codes
            or "land_search_certificate" in missing_categories,
            "No uploaded official search certificate is available for comparison.",
            "Obtain a fresh official land search before paying a deposit.",
        ),
        _deposit_warning(
            "seller_owner_mismatch",
            "Seller does not match owner",
            "critical",
            "seller_name_mismatch" in factor_codes or search_certificate.get("owner_matches_seller") is False,
            "Seller/owner evidence does not align across the uploaded documents or parsed search certificate.",
            "Ask an advocate to confirm the registered owner and seller authority.",
        ),
        _deposit_warning(
            "parcel_title_mismatch",
            "Parcel/title number mismatch exists",
            "critical",
            "parcel_number_mismatch" in factor_codes
            or _has_official_conflict(
                official_search,
                {"parcel_number_mismatch", "title_number_mismatch"},
            ),
            "Parcel or title identifiers differ across uploaded evidence.",
            "Stop and reconcile parcel, title, LR, block, and plot numbers before paying.",
        ),
        _deposit_warning(
            "consent_missing",
            "Consent is missing",
            "high",
            "missing_consent_to_transfer" in factor_codes or "consent_to_transfer" in missing_categories,
            "Consent to transfer was not uploaded or was flagged as missing.",
            "Confirm whether consent is required and obtain it before completion.",
        ),
        _deposit_warning(
            "gazette_possible_conflict",
            "Gazette possible conflict exists",
            "critical",
            "gazette_notice_conflict" in factor_codes or _normalized_gazette_status(gazette) == "checked_match_found",
            "A configured Gazette search produced a possible match or conflict signal.",
            "Have an advocate inspect the Gazette notice and source context.",
        ),
        _deposit_warning(
            "poor_document_quality",
            "Document quality is poor",
            "high",
            bool({"poor_image_quality", "low_document_confidence", "suspicious_document_edits"} & factor_codes),
            "One or more documents have low OCR confidence, poor quality, or suspicious edit signals.",
            "Request clearer originals and manually review altered or unreadable files.",
        ),
        _deposit_warning(
            "critical_transaction_risk",
            "Transaction has critical risk",
            "critical",
            band_value == "critical" or score >= 81 or any(str(factor.get("severity")) == "critical" for factor in risk_factors),
            f"The current risk score is {score}/100 ({band_value}).",
            "Do not release funds until official and professional checks are complete.",
        ),
    ]
    return [warning for warning in warnings if warning["triggered"]]


def _deposit_warning(
    code: str,
    label: str,
    severity: str,
    triggered: bool,
    explanation: str,
    recommended_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "severity": severity,
        "triggered": triggered,
        "explanation": explanation,
        "recommended_action": recommended_action,
    }


def _has_official_conflict(official_search: dict[str, Any], codes: set[str]) -> bool:
    return any(str(item.get("code")) in codes for item in official_search.get("conflicts", []) if isinstance(item, dict))


def _confidence_score_payload(extracted_documents: list[dict[str, Any]]) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    fields: list[dict[str, Any]] = []
    for document in extracted_documents:
        documents.append(
            {
                "document_id": document.get("document_id", ""),
                "category": document.get("category", ""),
                "filename": document.get("filename", ""),
                "extraction_confidence": document.get("extraction_confidence"),
                "document_quality_score": document.get("document_quality_score"),
                "status_label": _confidence_status(document.get("extraction_confidence")),
            }
        )
        for ref in document.get("evidence", []) or []:
            if not isinstance(ref, dict) or not ref.get("field_name"):
                continue
            fields.append(
                {
                    "document_id": document.get("document_id", ""),
                    "document_category": document.get("category", ""),
                    "filename": document.get("filename", ""),
                    "field_name": ref.get("field_name"),
                    "value": ref.get("quote"),
                    "confidence": ref.get("confidence"),
                    "source": ref.get("source"),
                    "status_labels": _field_status_labels(ref, extracted_documents),
                }
            )
    return {"documents": documents, "fields": fields}


def _field_status_labels(ref: dict[str, Any], extracted_documents: list[dict[str, Any]]) -> list[str]:
    labels = ["AI extracted" if ref.get("source") != "user_correction" else "user corrected"]
    value = _norm_text(ref.get("quote"))
    field_name = str(ref.get("field_name") or "")
    matches = 0
    for document in extracted_documents:
        for candidate in document.get("evidence", []) or []:
            if isinstance(candidate, dict) and candidate.get("field_name") == field_name and _norm_text(candidate.get("quote")) == value:
                matches += 1
    if matches > 1:
        labels.append("matched across documents")
    return labels


def _confidence_status(value: Any) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "confidence not recorded"
    if score >= 0.8:
        return "high confidence"
    if score >= 0.55:
        return "medium confidence"
    return "manual review required"


def _trust_evidence_panel(
    *,
    risk_factors: list[dict[str, Any]],
    extracted_documents: list[dict[str, Any]],
    official_search: dict[str, Any],
    gazette: dict[str, Any],
) -> list[dict[str, Any]]:
    document_labels = {
        str(document.get("document_id")): f"{_label(document.get('category', 'Document'))}: {document.get('filename') or 'Uploaded file'}"
        for document in extracted_documents
        if document.get("document_id")
    }
    rows: list[dict[str, Any]] = []
    for factor in risk_factors:
        refs = _factor_evidence_refs(factor)
        first_ref = refs[0] if refs else {}
        evidence = factor.get("evidence") if isinstance(factor.get("evidence"), dict) else {}
        document_id = str(first_ref.get("document_id") or "")
        compared_value = _compared_value_for_factor(factor, official_search, gazette)
        extracted_value = _extracted_value_for_factor(factor, refs)
        confidence = _mean_float([ref.get("confidence") for ref in refs if isinstance(ref, dict)])
        rows.append(
            {
                "risk_code": factor.get("code"),
                "risk_label": factor.get("label"),
                "what_detected": factor.get("explanation") or evidence.get("explanation") or factor.get("label"),
                "document_caused": document_labels.get(document_id)
                or _label(first_ref.get("document_category") or evidence.get("required_document") or "Case evidence"),
                "document_id": document_id or None,
                "extracted_value": extracted_value,
                "compared_value": compared_value,
                "confidence_score": confidence if confidence is not None else _factor_confidence(factor),
                "recommended_action": factor.get("recommendation"),
            }
        )
    return rows


def _attach_trust_evidence(risk_factors: list[dict[str, Any]], panel: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_code = {row.get("risk_code"): row for row in panel}
    output: list[dict[str, Any]] = []
    for factor in risk_factors:
        enriched = dict(factor)
        enriched["trust_evidence"] = by_code.get(factor.get("code"))
        output.append(enriched)
    return output


def _factor_evidence_refs(factor: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = factor.get("evidence")
    refs: list[Any] = []
    refs.extend(factor.get("evidence_refs", []) or [])
    if isinstance(evidence, dict):
        refs.extend(evidence.get("evidence_refs", []) or [])
        refs.extend(evidence.get("evidence", []) or [])
    return [ref for ref in refs if isinstance(ref, dict)]


def _extracted_value_for_factor(factor: dict[str, Any], refs: list[dict[str, Any]]) -> str:
    for ref in refs:
        value = ref.get("quote") or ref.get("value") or ref.get("text_snippet")
        if value:
            return str(value)
    evidence = factor.get("evidence") if isinstance(factor.get("evidence"), dict) else {}
    for key in ("values", "required_document", "dates", "quality_score", "signals", "notices"):
        if evidence.get(key):
            return _display(evidence[key])
    return "Not recorded"


def _compared_value_for_factor(factor: dict[str, Any], official_search: dict[str, Any], gazette: dict[str, Any]) -> str:
    evidence = factor.get("evidence") if isinstance(factor.get("evidence"), dict) else {}
    for key in ("values", "official_search_conflicts", "dates"):
        if evidence.get(key):
            return _display(evidence[key])
    code = str(factor.get("code") or "")
    if code == "gazette_notice_conflict":
        return _display(gazette.get("notices", []))
    if code in {"parcel_number_mismatch", "seller_name_mismatch"}:
        return _display(official_search.get("conflicts", []))
    return "Compared against uploaded case evidence"


def _factor_confidence(factor: dict[str, Any]) -> float | None:
    evidence = factor.get("evidence") if isinstance(factor.get("evidence"), dict) else {}
    for key in ("confidence", "confidence_score", "quality_score"):
        try:
            return float(evidence[key])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def _kiswahili_summaries(
    *,
    score: int,
    band_value: str,
    warnings: list[dict[str, Any]],
    next_steps: list[str],
    missing_documents: list[dict[str, Any]],
) -> dict[str, str]:
    warning_count = len(warnings)
    missing = ", ".join(_label(item.get("category", "")) for item in missing_documents[:4]) or "hakuna iliyoandikwa"
    steps = "; ".join(next_steps[:3]) or "omba ukaguzi wa mtaalamu kabla ya kuendelea"
    return {
        "risk_report": (
            f"Ripoti inaonyesha alama ya hatari {score}/100 ({band_value}). "
            "Huu ni uchambuzi wa AI kwa kusaidia uamuzi, si uthibitisho rasmi wa umiliki."
        ),
        "warnings": (
            f"Kabla ya kulipa depositi, kuna onyo {warning_count}. "
            "Usilipe mpaka ushahidi rasmi na ukaguzi wa mtaalamu ukamilike."
        ),
        "next_steps": f"Hatua zinazofuata: {steps}.",
        "missing_documents": f"Nyaraka zinazokosekana au zinazohitaji kuangaliwa: {missing}.",
    }


def _human_review_workflow(warnings: list[dict[str, Any]], risk_factors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warning_codes = {str(warning.get("code")) for warning in warnings}
    factor_codes = {str(factor.get("code")) for factor in risk_factors}
    return [
        {
            "role": "advocate",
            "label": "Advocate review",
            "recommended": bool(warning_codes & {"seller_owner_mismatch", "gazette_possible_conflict", "critical_transaction_risk"})
            or bool(factor_codes & {"seller_name_mismatch", "power_of_attorney_unverified", "missing_consent_to_transfer"}),
            "reason": "Use for ownership, seller authority, agreements, consents, POA, and legal transfer conditions.",
        },
        {
            "role": "surveyor",
            "label": "Surveyor review",
            "recommended": "boundary_or_mutation_inconsistency" in factor_codes,
            "reason": "Use for parcel identity, maps, mutation forms, acreage, boundaries, and beacons.",
        },
        {
            "role": "site_visit",
            "label": "Site visit",
            "recommended": bool(factor_codes & {"boundary_or_mutation_inconsistency", "duplicate_parcel_number"}),
            "reason": "Use when the buyer needs physical confirmation of occupation, access, and neighborhood context.",
        },
        {
            "role": "boundary_verification",
            "label": "Boundary verification",
            "recommended": bool(factor_codes & {"boundary_or_mutation_inconsistency", "parcel_number_mismatch"}),
            "reason": "Use when parcel, title, map, mutation, or survey evidence does not line up.",
        },
        {
            "role": "official_search_assistance",
            "label": "Official search assistance",
            "recommended": bool(warning_codes & {"search_certificate_missing", "seller_owner_mismatch"})
            or "stale_search_certificate" in factor_codes,
            "reason": "Use to obtain or refresh official registry search evidence before funds move.",
        },
    ]


def _evidence_references(
    *,
    risk_factors: list[dict[str, Any]],
    extracted_documents: list[dict[str, Any]],
    official_search: dict[str, Any],
    inconsistencies: dict[str, Any],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for factor in risk_factors:
        for ref in factor.get("evidence_refs", []) or factor.get("evidence", {}).get("evidence_refs", []) or []:
            if isinstance(ref, dict):
                refs.append(ref)
        evidence = factor.get("evidence")
        if isinstance(evidence, dict) and evidence and not any(key in evidence for key in {"evidence_refs", "evidence"}):
            refs.append({"source": "risk_factor", "field_name": factor.get("code"), "summary": _compact_json(evidence)})
        for item in evidence.get("evidence", []) if isinstance(evidence, dict) else []:
            if isinstance(item, dict):
                refs.append(item)
    for document in extracted_documents:
        for ref in document.get("evidence", []) or []:
            if isinstance(ref, dict):
                refs.append(ref)
    certificate = official_search.get("certificate") or {}
    for ref in certificate.get("evidence", []) or []:
        if isinstance(ref, dict):
            refs.append(ref)
    for key in ("mismatches", "suspicious_date_sequences"):
        for finding in inconsistencies.get(key, []) or []:
            for ref in finding.get("evidence", []) if isinstance(finding, dict) else []:
                if isinstance(ref, dict):
                    refs.append(ref)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref in refs:
        marker = "|".join(str(ref.get(key, "")) for key in ("document_id", "document_category", "field_name", "quote", "text_snippet"))
        if marker not in seen:
            seen.add(marker)
            deduped.append(_json_safe(ref))
    return deduped


def _first_extracted_value(extracted_documents: list[dict[str, Any]], field_name: str) -> str:
    for document in extracted_documents:
        value = document.get(field_name)
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item)
        if value:
            return str(value)
    return ""


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _names_match(left: str, right: str) -> bool:
    left_key = _norm_text(left)
    right_key = _norm_text(right)
    if not left_key or not right_key:
        return False
    return left_key == right_key or SequenceMatcher(None, left_key, right_key).ratio() >= 0.86


def _norm_text(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _mean_float(values: list[Any]) -> float | None:
    clean: list[float] = []
    for value in values:
        try:
            clean.append(float(value))
        except (TypeError, ValueError):
            continue
    if not clean:
        return None
    return round(sum(clean) / len(clean), 2)


def _money(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        amount = Decimal(str(value))
    except Exception:
        return str(value)
    return f"KES {amount:,.2f}"


def _percent(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _string_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item) for item in items if str(item).strip()]


def _dedupe(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = " ".join(str(item).split()).lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(str(item))
    return output


def _enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value
