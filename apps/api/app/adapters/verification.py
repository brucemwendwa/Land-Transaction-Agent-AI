from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import VerificationStatus


@dataclass(frozen=True)
class VerificationResult:
    adapter_name: str
    status: VerificationStatus
    query: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    message: str = ""
