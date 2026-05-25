from __future__ import annotations

import base64
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings


class MpesaNotConfiguredError(RuntimeError):
    pass


class MpesaClient:
    def __init__(self) -> None:
        self.base_url = (
            "https://api.safaricom.co.ke"
            if settings.mpesa_environment.lower() == "production"
            else "https://sandbox.safaricom.co.ke"
        )

    @property
    def configured(self) -> bool:
        return settings.mpesa_configured

    async def initiate_stk_push(
        self,
        *,
        payment_id: str,
        amount: Decimal,
        phone_number: str,
        account_reference: str,
        description: str,
    ) -> dict[str, Any]:
        if not self.configured:
            raise MpesaNotConfiguredError("M-Pesa Daraja credentials are not configured")
        token = await self._access_token()
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{settings.mpesa_shortcode}{settings.mpesa_passkey}{timestamp}".encode()).decode()
        payload = {
            "BusinessShortCode": settings.mpesa_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": _normalize_phone(phone_number),
            "PartyB": settings.mpesa_shortcode,
            "PhoneNumber": _normalize_phone(phone_number),
            "CallBackURL": settings.mpesa_callback_url,
            "AccountReference": account_reference[:12] or payment_id[:12],
            "TransactionDesc": description[:120],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            return response.json()

    async def _access_token(self) -> str:
        credentials = f"{settings.mpesa_consumer_key}:{settings.mpesa_consumer_secret}"
        auth = base64.b64encode(credentials.encode()).decode()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers={"Authorization": f"Basic {auth}"},
            )
            response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("M-Pesa access token was not returned")
        return str(token)


def _normalize_phone(phone_number: str) -> str:
    digits = "".join(char for char in phone_number if char.isdigit())
    if digits.startswith("0"):
        return f"254{digits[1:]}"
    if digits.startswith("7") and len(digits) == 9:
        return f"254{digits}"
    return digits


def parse_stk_callback(payload: dict[str, Any]) -> dict[str, Any]:
    callback = payload.get("Body", {}).get("stkCallback", {})
    metadata_items = callback.get("CallbackMetadata", {}).get("Item", []) or []
    metadata = {str(item.get("Name")): item.get("Value") for item in metadata_items if isinstance(item, dict)}
    return {
        "merchant_request_id": str(callback.get("MerchantRequestID", "")),
        "checkout_request_id": str(callback.get("CheckoutRequestID", "")),
        "result_code": str(callback.get("ResultCode", "")),
        "result_description": str(callback.get("ResultDesc", "")),
        "receipt_number": str(metadata.get("MpesaReceiptNumber", "")),
        "amount": metadata.get("Amount"),
        "phone_number": str(metadata.get("PhoneNumber", "")),
        "transaction_date": str(metadata.get("TransactionDate", "")),
    }
