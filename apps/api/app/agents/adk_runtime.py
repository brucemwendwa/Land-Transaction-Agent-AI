from __future__ import annotations

from typing import Any

from app.agents.specs import AGENT_SPECS
from app.core.config import settings


def build_adk_agents() -> dict[str, Any]:
    try:
        try:
            from google.adk.agents import Agent
        except Exception:
            from google.adk import Agent
    except Exception:
        return {}
    return {
        spec.name: Agent(
            name=spec.name,
            model=settings.gemini_model,
            instruction=spec.instruction,
        )
        for spec in AGENT_SPECS
    }
