from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.models import Payment, PaymentEvent, User
from app.schemas import MpesaCallbackResponse, MpesaPaymentInitiateRequest, MpesaPaymentInitiateResponse, PaymentRead
from app.services.audit import write_audit, write_timeline
from app.services.mpesa import MpesaClient, MpesaNotConfiguredError, parse_stk_callback

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/mpesa/stk-push", response_model=MpesaPaymentInitiateResponse)
async def initiate_mpesa_stk_push(
    payload: MpesaPaymentInitiateRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> MpesaPaymentInitiateResponse:
    case = get_case_for_user(payload.case_id, db, current_user)
    payment = Payment(
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        case_id=case.id,
        provider="mpesa",
        purpose=payload.purpose,
        amount=payload.amount,
        currency="KES",
        phone_number=payload.phone_number,
        status="pending",
        metadata_json={"initiated_by": current_user.id},
    )
    db.add(payment)
    db.flush()
    client = MpesaClient()
    if not client.configured:
        payment.status = "not_configured"
        db.add(
            PaymentEvent(
                payment_id=payment.id,
                provider="mpesa",
                event_type="not_configured",
                payload={"message": "M-Pesa Daraja credentials are not configured"},
            )
        )
        write_audit(
            db,
            action="payment.mpesa.not_configured",
            target_type="payment",
            target_id=payment.id,
            actor=current_user,
            request=request,
            case_id=case.id,
        )
        db.commit()
        db.refresh(payment)
        return MpesaPaymentInitiateResponse(
            payment=PaymentRead.model_validate(payment),
            status="not_configured",
            message="M-Pesa Daraja credentials are not configured.",
        )
    try:
        response = await client.initiate_stk_push(
            payment_id=payment.id,
            amount=payload.amount,
            phone_number=payload.phone_number,
            account_reference=f"MRA-{case.id[:8]}",
            description=f"Mradi wa Ardhi {payload.purpose}",
        )
    except MpesaNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        payment.status = "failed"
        payment.result_description = str(exc)
        db.add(
            PaymentEvent(
                payment_id=payment.id,
                provider="mpesa",
                event_type="initiation_failed",
                payload={"error": str(exc)},
            )
        )
        db.commit()
        raise HTTPException(status_code=502, detail="M-Pesa STK Push initiation failed") from exc

    payment.provider_merchant_request_id = str(response.get("MerchantRequestID", ""))
    payment.provider_checkout_request_id = str(response.get("CheckoutRequestID", ""))
    payment.result_code = str(response.get("ResponseCode", ""))
    payment.result_description = str(response.get("ResponseDescription", ""))
    payment.status = "initiated"
    db.add(
        PaymentEvent(
            payment_id=payment.id,
            provider="mpesa",
            provider_event_id=payment.provider_checkout_request_id,
            event_type="stk_push_initiated",
            payload=response,
        )
    )
    write_timeline(
        db,
        case_id=case.id,
        actor=current_user,
        event_type="payment_initiated",
        title="M-Pesa payment initiated",
        metadata={"payment_id": payment.id, "amount": str(payment.amount), "status": payment.status},
    )
    write_audit(
        db,
        action="payment.mpesa.initiate",
        target_type="payment",
        target_id=payment.id,
        actor=current_user,
        request=request,
        case_id=case.id,
    )
    db.commit()
    db.refresh(payment)
    return MpesaPaymentInitiateResponse(
        payment=PaymentRead.model_validate(payment),
        status=payment.status,
        message="M-Pesa STK Push initiated.",
    )


@router.post("/mpesa/callback", response_model=MpesaCallbackResponse)
async def mpesa_callback(
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db)],
) -> MpesaCallbackResponse:
    parsed = parse_stk_callback(payload)
    payment = (
        db.query(Payment)
        .filter(Payment.provider_checkout_request_id == parsed["checkout_request_id"])
        .one_or_none()
    )
    result_code = parsed["result_code"]
    status = "successful" if result_code == "0" else "failed"
    if payment is not None:
        payment.status = status
        payment.result_code = result_code
        payment.result_description = parsed["result_description"]
        payment.provider_receipt_number = parsed["receipt_number"]
        if status == "successful":
            payment.paid_at = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        PaymentEvent(
            payment_id=payment.id if payment else None,
            provider="mpesa",
            provider_event_id=parsed["checkout_request_id"],
            event_type=f"stk_push_{status}",
            payload=payload,
        )
    )
    db.commit()
    return MpesaCallbackResponse(status="accepted")


@router.get("/{payment_id}", response_model=PaymentRead)
async def payment_status(
    payment_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> PaymentRead:
    payment = db.query(Payment).filter(Payment.id == payment_id).one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    if current_user.role.value != "admin" and payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Payment is not accessible")
    return PaymentRead.model_validate(payment)


def has_successful_report_payment(db: Session, *, case_id: str, user_id: str) -> bool:
    return (
        db.query(Payment)
        .filter(
            Payment.case_id == case_id,
            Payment.user_id == user_id,
            Payment.purpose == "report_unlock",
            Payment.status == "successful",
        )
        .first()
        is not None
    )
