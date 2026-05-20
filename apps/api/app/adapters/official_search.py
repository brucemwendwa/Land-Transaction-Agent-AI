from __future__ import annotations

from app.adapters.verification import VerificationResult
from app.domain.enums import DocumentCategory, VerificationStatus
from app.models import Document


class UploadedOfficialSearchAdapter:
    name = "uploaded_official_search_certificate"

    def evaluate(self, documents: list[Document]) -> VerificationResult:
        search_docs = [doc for doc in documents if doc.category == DocumentCategory.LAND_SEARCH_CERTIFICATE]
        if not search_docs:
            return VerificationResult(
                adapter_name=self.name,
                status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                message=(
                    "No official land search certificate was uploaded. Ownership has not been "
                    "verified from an official registry source."
                ),
            )
        extracted = [
            {"document_id": doc.id, "fields": [field.field_name for field in doc.extracted_fields]}
            for doc in search_docs
        ]
        return VerificationResult(
            adapter_name=self.name,
            status=VerificationStatus.NOT_VERIFIED_FROM_OFFICIAL_SOURCE,
            evidence={"uploaded_search_certificates": extracted},
            message=(
                "An uploaded search certificate was parsed, but the system has not independently "
                "verified it against an official registry API."
            ),
        )
