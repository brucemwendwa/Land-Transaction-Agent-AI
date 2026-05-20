from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_case_for_user, get_current_user
from app.models import User
from app.schemas import GazetteSearchResponse
from app.services.audit import write_audit, write_timeline
from app.services.gazette_search import run_gazette_search_for_case, serialize_gazette_search

router = APIRouter(prefix="/api/cases", tags=["gazette"])


@router.post("/{case_id}/gazette-search", response_model=GazetteSearchResponse)
async def search_case_gazette(
    case_id: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    case = get_case_for_user(case_id, db, current_user)
    result = await run_gazette_search_for_case(db=db, case=case)
    write_timeline(
        db,
        case_id=case.id,
        actor=current_user,
        event_type="gazette_search_completed",
        title=f"Gazette search completed: {result.status}",
        metadata={"status": result.status, "matches": len(result.notices), "query_terms": result.query_terms},
    )
    write_audit(
        db,
        action="case.gazette_search.run",
        target_type="case",
        target_id=case.id,
        actor=current_user,
        request=request,
        case_id=case.id,
        metadata={"status": result.status, "matches": len(result.notices)},
    )
    db.commit()
    return serialize_gazette_search(result)
