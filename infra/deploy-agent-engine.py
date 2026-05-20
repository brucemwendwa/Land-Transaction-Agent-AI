from __future__ import annotations

from app.agents.adk_runtime import build_adk_agents
from app.core.config import settings


def main() -> None:
    project = settings.gcp_project_id
    location = settings.vertex_ai_location
    if not project:
        raise SystemExit("GOOGLE_CLOUD_PROJECT is required to prepare Agent Engine deployment.")
    agents = build_adk_agents()
    if not agents:
        raise SystemExit("Google ADK is not installed or no agents could be built.")
    print(f"Prepared {len(agents)} ADK agents for {project}/{location}.")
    if settings.adk_agent_config:
        print(f"Using ADK_AGENT_CONFIG={settings.adk_agent_config}.")
    print("Deploy with Vertex AI Agent Engine using your organization's release pipeline and service account.")


if __name__ == "__main__":
    main()
