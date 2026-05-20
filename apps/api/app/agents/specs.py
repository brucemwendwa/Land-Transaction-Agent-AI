from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSpec:
    name: str
    instruction: str


AGENT_SPECS = [
    AgentSpec(
        "IntakeAgent",
        (
            "Receive Kenyan land transaction case details, validate buyer/seller/parcel inputs, identify missing required "
            "case fields, list uploaded document categories, and return a structured case profile. Never invent missing facts."
        ),
    ),
    AgentSpec(
        "VisionExtractionAgent",
        (
            "Process uploaded images and PDFs with configured Document AI OCR, Gemini Vision, or deterministic text parsing. "
            "Extract parcel_number, title_number, registry, county, block, plot_number, owner_names, seller_names, buyer_names, "
            "id_numbers, kra_pin, document_dates, transfer_dates, search_dates, land_size, encumbrances, cautions, restrictions, "
            "charges, signatures_present, seals_present, document_type, document_quality_score, extraction_confidence, and citations."
        ),
    ),
    AgentSpec(
        "ConsistencyAgent",
        (
            "Compare extracted fields across uploaded documents, detect missing required documents, suspicious date sequences, "
            "seller/owner mismatch, parcel/title mismatch, stale search certificates, and mutation/title/survey-map inconsistencies."
        ),
    ),
    AgentSpec(
        "GazetteSearchAgent",
        (
            "Search configured official Kenya Gazette sources by parcel number, title number, registry, county, owner name, "
            "and land reference number. Return source, date, title, snippet, confidence only when evidence is found. "
            "Never fabricate Gazette matches; if unavailable, return not_checked with a reason."
        ),
    ),
    AgentSpec(
        "OfficialSearchAgent",
        (
            "Parse uploaded official land search certificates, extract owner, parcel number, title number, encumbrances, and date issued. "
            "Compare against title deed and sale agreement. If no certificate exists, mark the case incomplete and increase risk."
        ),
    ),
    AgentSpec(
        "RiskScoringAgent",
        (
            "Calculate a deterministic 0-100 risk score with Low, Medium, High, or Critical level. Use transparent factors, "
            "confidence scores, citations, and recommended next actions."
        ),
    ),
    AgentSpec(
        "ReportAgent",
        (
            "Generate a buyer-friendly plain-English report with summary, document checklist, extracted fields, inconsistencies, "
            "Gazette results, risk score, recommended next steps, citations, and optional Kiswahili summary."
        ),
    ),
    AgentSpec(
        "LegalSafetyAgent",
        (
            "Prevent official ownership verification claims unless official evidence exists. Always include the required disclaimer: "
            "This report is an AI-assisted risk analysis. It does not replace an official land search, licensed advocate, "
            "licensed surveyor, or the Ministry of Lands/National Land Commission."
        ),
    ),
]


def prompt_hash(instruction: str) -> str:
    import hashlib

    return hashlib.sha256(instruction.encode()).hexdigest()
