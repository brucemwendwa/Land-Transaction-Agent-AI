from __future__ import annotations

import html
import io
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
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
    recommended_next_steps = _dedupe(
        [
            *_string_list(agent_context.get("recommended_next_actions", [])),
            "Obtain or refresh the official land search certificate.",
            "Have an advocate verify the seller, title, consents, and completion documents.",
            "Have a surveyor confirm boundaries, mutation forms, and survey maps where relevant.",
            "Do not release purchase funds until official and professional checks are complete.",
        ]
    )
    plain_english = _plain_summary(score, band, verification_status)
    sw_summary = ""
    if language == "sw":
        sw_summary = (
            f"Ripoti hii inaonyesha alama ya hatari {score}/100 ({band_value}). "
            "Ni msaada wa AI kwa uamuzi wa awali, si uthibitisho rasmi wa umiliki wala ushauri wa kisheria."
        )
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
        "official_search_certificate_review": official_review,
        "risk_score": score,
        "risk_level": band_value,
        "risk_factors": risk_factors,
        "detailed_risk_factors": risk_factors,
        "recommended_next_steps": recommended_next_steps,
        "plain_english_explanation": plain_english,
        "kiswahili_summary": sw_summary,
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

    _add_section(story, styles, "10. Risk Score")
    story.append(RiskMeterFlowable(content.get("risk_score", 0), content.get("risk_level", "not recorded")))
    story.append(Spacer(1, 8))
    story.append(
        _small_table(
            [["Score", f"{content.get('risk_score', 0)}/100"], ["Risk level", str(content.get("risk_level", "")).title()]],
            styles,
        )
    )

    _add_section(story, styles, "11. Risk Level")
    story.append(_risk_level_panel(content, styles))

    _add_section(story, styles, "12. Detailed Risk Factors")
    story.append(_risk_factor_table(content.get("detailed_risk_factors") or content.get("risk_factors", []), styles))

    _add_section(story, styles, "13. Recommended Next Actions")
    _append_bullets(story, content.get("recommended_next_steps", []), styles)

    _add_section(story, styles, "14. Plain-English Explanation")
    plain_english = content.get("plain_english_explanation") or content.get("summary", {}).get("plain_english", "")
    story.append(_paragraph(plain_english, styles["BodyText"]))

    if content.get("kiswahili_summary") or content.get("summary", {}).get("kiswahili"):
        _add_section(story, styles, "15. Optional Kiswahili Summary")
        story.append(_paragraph(content.get("kiswahili_summary") or content.get("summary", {}).get("kiswahili", ""), styles["BodyText"]))

    _add_section(story, styles, "16. Legal Disclaimer")
    story.append(_paragraph(content.get("legal_disclaimer", LEGAL_DISCLAIMER), styles["BodyText"]))

    _add_section(story, styles, "17. Appendix With Evidence References")
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
        fields = [{"name": name, "value": document.get(name)} for name in field_names if document.get(name) not in (None, "", [], {})]
        if fields:
            output.append(
                {
                    "document_id": document.get("document_id", ""),
                    "document_label": f"{_label(document.get('category', 'Document'))}: {document.get('filename') or 'Uploaded file'}",
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
