from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models import PricingPlanSelection, User
from app.schemas import PricingSelectionRequest
from app.services.audit import write_audit

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.post("/selection")
async def select_pricing_plan(
    payload: PricingSelectionRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    selection = PricingPlanSelection(user_id=current_user.id, plan_key=payload.plan_key)
    db.add(selection)
    db.flush()
    write_audit(
        db,
        action="pricing.select",
        target_type="pricing_plan_selection",
        target_id=selection.id,
        actor=current_user,
        request=request,
        metadata={"plan_key": payload.plan_key},
    )
    db.commit()
    return {"status": "selected", "plan_key": payload.plan_key}
