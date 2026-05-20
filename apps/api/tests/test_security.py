from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.security import Principal


def test_cookie_authenticated_unsafe_requests_require_matching_csrf_token(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post(
        "/cases",
        headers={"cookie": "csrf_token=known-token"},
        json={"title": "CSRF blocked"},
    )

    assert response.status_code == 403
    assert response.text == "CSRF validation failed"


def test_unauthorized_user_cannot_access_another_users_case(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    owner_response = client.post("/cases", json={"title": "Owner only case"})
    assert owner_response.status_code == 201
    case_id = owner_response.json()["id"]

    def intruder_principal() -> Principal:
        return Principal(
            subject="intruder-user",
            email="intruder@example.test",
            full_name="Intruder User",
            role="buyer",
        )

    monkeypatch.setattr("app.deps.local_dev_principal", intruder_principal)

    response = client.get(f"/cases/{case_id}")

    assert response.status_code == 403
    assert response.json()["detail"] == "Case is not accessible"


def test_production_settings_reject_insecure_auth_and_secret_defaults() -> None:
    with pytest.raises(ValueError) as exc_info:
        Settings(app_env="production")

    message = str(exc_info.value)
    assert "AUTH_BYPASS must be false in production" in message
    assert "PUBLIC_APP_URL must use HTTPS in production" in message
    assert "STORAGE_BACKEND must be gcs in production" in message
    assert "UPLOAD_SIGNING_SECRET must be set to a strong environment-provided secret" in message
