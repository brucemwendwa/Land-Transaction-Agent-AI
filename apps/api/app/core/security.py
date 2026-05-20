from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.core.config import settings


class Principal(BaseModel):
    subject: str
    email: str
    full_name: str = ""
    role: str = "buyer"
    claims: dict[str, Any] = Field(default_factory=dict)


_jwks_cache: dict[str, Any] = {"keys": None, "expires_at": 0.0}


async def _fetch_jwks() -> dict[str, Any]:
    if not settings.clerk_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk JWKS URL is not configured",
        )
    now = time.time()
    cached_keys = _jwks_cache["keys"]
    if isinstance(cached_keys, dict) and _jwks_cache["expires_at"] > now:
        return cached_keys
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(settings.clerk_jwks_url)
        response.raise_for_status()
    jwks = response.json()
    if not isinstance(jwks, dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWKS response")
    _jwks_cache["keys"] = jwks
    _jwks_cache["expires_at"] = now + 300
    return jwks


def _select_key(jwks: dict[str, Any], kid: str) -> dict[str, Any]:
    for key in jwks.get("keys", []):
        if isinstance(key, dict) and key.get("kid") == kid:
            return key
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown token key")


async def verify_clerk_jwt(token: str) -> Principal:
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != settings.auth_allowed_algorithm:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported token algorithm")
        jwks = await _fetch_jwks()
        key = _select_key(jwks, header["kid"])
        audience = settings.clerk_audience or None
        claims = jwt.decode(
            token,
            key,
            algorithms=[settings.auth_allowed_algorithm],
            issuer=settings.clerk_issuer or None,
            audience=audience,
            options={"verify_aud": bool(audience)},
        )
    except (JWTError, httpx.HTTPError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    subject = claims.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    email = claims.get("email") or ""
    if not email and claims.get("email_addresses"):
        primary = claims.get("primary_email_address_id")
        for item in claims["email_addresses"]:
            if item.get("id") == primary:
                email = item.get("email_address", "")
                break
    metadata = claims.get("public_metadata", {}) or {}
    return Principal(
        subject=subject,
        email=email or f"{subject}@clerk.local",
        full_name=claims.get("name") or claims.get("given_name") or "",
        role=metadata.get("role", "buyer"),
        claims=claims,
    )


def local_dev_principal() -> Principal:
    return Principal(
        subject="dev-user",
        email="buyer@example.test",
        full_name="Local Buyer",
        role="buyer",
        claims={
            "sub": "dev-user",
            "email": "buyer@example.test",
            "exp": int((datetime.now(UTC) + timedelta(days=1)).timestamp()),
        },
    )
