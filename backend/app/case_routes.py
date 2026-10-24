from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import Principal, authenticate, require_admin, require_writer
from .case_schemas import CaseAction, CaseSnapshot, Status
from .database import get_db
from .models import InvestigationCase
from .services.cases import apply_action, canonical, case_or_404, create_case, serialize

router = APIRouter(prefix="/api/v1/cases", tags=["investigations"])


@router.get("/identity")
def identity(principal: Principal = Depends(authenticate)):
    return {"actor": principal.actor, "role": principal.role}


@router.get("")
def cases(status: Status | None = None, search: str = Query("", max_length=80),
          limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=100_000),
          principal: Principal = Depends(authenticate), db: Session = Depends(get_db)):
    query = select(InvestigationCase)
    if status:
        query = query.where(InvestigationCase.status == status)
    if search:
        query = query.where(InvestigationCase.transaction_id.contains(search, autoescape=True))
    rows = db.scalars(query.order_by(InvestigationCase.updated_at.desc(), InvestigationCase.id).limit(limit + 1).offset(offset)).all()
    return {"items": [serialize(db, case, include_history=False) for case in rows[:limit]], "has_more": len(rows) > limit, "offset": offset}


@router.post("", status_code=201)
def import_case(snapshot: CaseSnapshot, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    if snapshot.source != "caller_supplied_simulation":
        raise HTTPException(422, "Verified-study provenance is reserved for the local study import command")
    return create_case(db, snapshot, principal)


@router.get("/{case_id}")
def case_detail(case_id: str, principal: Principal = Depends(authenticate), db: Session = Depends(get_db)):
    return serialize(db, case_or_404(db, case_id))


@router.post("/{case_id}/actions")
def act(case_id: str, action: CaseAction, principal: Principal = Depends(require_writer), db: Session = Depends(get_db)):
    return apply_action(db, case_id, action, principal)


@router.get("/{case_id}/export")
def export(case_id: str, principal: Principal = Depends(require_writer), db: Session = Depends(get_db)):
    case = serialize(db, case_or_404(db, case_id))
    # Notes and actor identifiers can hold sensitive text: omit them from a
    # portable report while keeping original event hashes for local comparison.
    for event in case["history"]:
        event.pop("actor", None)
        event.pop("note", None)
    report = {"schema_version": 1, "sanitized": True, "disclosure": "Synthetic/caller-supplied simulated evidence. Human decisions are not verified training labels. Redacted events cannot independently reproduce their original hashes.", "case": case}
    return Response(canonical(report), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="fraudlens-case-{case["id"]}.json"'})
