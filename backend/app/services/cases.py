"""Atomic optimistic locking and a per-case hash-linked, append-only journal."""
from datetime import datetime, timezone
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ..auth import Principal
from ..case_schemas import CaseAction, CaseSnapshot
from ..models import CaseEvent, InvestigationCase

GENESIS = "0" * 64
TRANSITIONS = {"pending": {"reviewed"}, "reviewed": {"pending", "confirmed_fraud", "legitimate"}, "confirmed_fraud": set(), "legitimate": set()}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def case_or_404(db: Session, case_id: str) -> InvestigationCase:
    case = db.get(InvestigationCase, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


def journal(db: Session, case_id: str) -> list[CaseEvent]:
    return list(db.scalars(select(CaseEvent).where(CaseEvent.case_id == case_id).order_by(CaseEvent.version)))


def read_evidence(db: Session, case_id: str) -> tuple[InvestigationCase, list[CaseEvent]]:
    # One SQL statement observes the row and its journal at the same database
    # snapshot. Separate SELECTs can straddle a committed writer, particularly
    # with SQLite's legacy deferred SELECT transactions. Refresh ORM identities
    # too: a prior route/list read may have cached the older case or events.
    rows = db.execute(select(InvestigationCase, CaseEvent)
        .outerjoin(CaseEvent, CaseEvent.case_id == InvestigationCase.id)
        .where(InvestigationCase.id == case_id).order_by(CaseEvent.version)
        .execution_options(populate_existing=True)).all()
    if not rows:
        raise HTTPException(404, "Case not found")
    return rows[0][0], [event for _, event in rows if event is not None]


def verify(case: InvestigationCase, events: list[CaseEvent]) -> bool:
    previous = GENESIS
    if digest(case.snapshot_json) != case.snapshot_sha256 or len(events) != case.version:
        return False
    try:
        if json.loads(case.snapshot_json)["transaction_id"] != case.transaction_id:
            return False
    except (ValueError, KeyError, TypeError):
        return False
    state = "pending"
    for version, event in enumerate(events, 1):
        try:
            payload = json.loads(event.payload_json)
            if event.version != version or event.previous_hash != previous or digest(previous + event.payload_json) != event.event_hash:
                return False
            if payload["case_id"] != case.id or payload["version"] != version or payload["snapshot_sha256"] != case.snapshot_sha256:
                return False
            if version == 1 and (payload["timestamp"] != case.created_at or payload["action"] != "created" or payload["from_status"] is not None or payload["status"] != "pending"):
                return False
            if version > 1 and payload["from_status"] != state:
                return False
            state = payload["status"]
            previous = event.event_hash
        except (ValueError, KeyError, TypeError):
            return False
    return state == case.status and bool(events) and json.loads(events[-1].payload_json)["timestamp"] == case.updated_at


def serialize(db: Session, case: InvestigationCase, include_history=True) -> dict:
    case, events = read_evidence(db, case.id)
    if not verify(case, events):
        raise HTTPException(409, "Case integrity verification failed; administrator investigation required")
    result = {"id": case.id, "transaction_id": case.transaction_id, "status": case.status, "version": case.version,
              "created_at": case.created_at, "updated_at": case.updated_at, "snapshot": json.loads(case.snapshot_json),
              "snapshot_sha256": case.snapshot_sha256, "audit_integrity": "verified",
              "training_label_eligible": False}
    if include_history:
        result["history"] = [{**json.loads(event.payload_json), "previous_hash": event.previous_hash, "event_hash": event.event_hash} for event in events]
    return result


def append_event(db: Session, case: InvestigationCase, principal: Principal, action: str, from_status: str | None, note: str, previous: str) -> None:
    payload = canonical({"case_id": case.id, "version": case.version, "actor": principal.actor, "role": principal.role,
                         "action": action, "from_status": from_status, "status": case.status, "note": note,
                         "timestamp": case.updated_at, "snapshot_sha256": case.snapshot_sha256})
    db.add(CaseEvent(case_id=case.id, version=case.version, payload_json=payload, previous_hash=previous, event_hash=digest(previous + payload)))


def create_case(db: Session, snapshot: CaseSnapshot, principal: Principal) -> dict:
    if snapshot.fraud_probability < snapshot.threshold:
        raise HTTPException(422, "Only flagged transactions can enter the investigation queue")
    timestamp = now()
    data = canonical(snapshot.model_dump(mode="json"))
    case = InvestigationCase(id=str(uuid.uuid4()), transaction_id=snapshot.transaction_id,
                             status="pending", version=1, snapshot_json=data, snapshot_sha256=digest(data),
                             created_at=timestamp, updated_at=timestamp)
    try:
        db.add(case)
        db.flush()
        append_event(db, case, principal, "created", None, "Flagged scored snapshot imported; investigator outcomes are not ground truth.", GENESIS)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Transaction already has a case") from None
    except OperationalError:
        db.rollback()
        raise HTTPException(503, "Case store temporarily busy; retry import") from None
    return serialize(db, case)


def apply_action(db: Session, case_id: str, action: CaseAction, principal: Principal) -> dict:
    case, events = read_evidence(db, case_id)
    if not verify(case, events):
        raise HTTPException(409, "Case integrity verification failed; administrator investigation required")
    if case.version != action.expected_version:
        raise HTTPException(409, "Case changed; reload before applying your action")
    old_status = case.status
    new_status = action.status
    if action.action == "note":
        if new_status is not None:
            raise HTTPException(422, "Notes cannot change case status")
        new_status = old_status
    elif new_status not in TRANSITIONS[old_status] and not (principal.role == "admin" and old_status in {"confirmed_fraud", "legitimate"} and new_status == "reviewed"):
        raise HTTPException(422, "Invalid case transition; review pending cases before resolution; only administrators may reopen resolutions")
    try:
        # The conditional UPDATE is the concurrency arbiter, not a preceding read.
        result = db.execute(update(InvestigationCase).where(InvestigationCase.id == case_id, InvestigationCase.version == action.expected_version)
                            .values(status=new_status, version=action.expected_version + 1, updated_at=now()).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Case changed; reload before applying your action")
        db.refresh(case)
        append_event(db, case, principal, action.action, old_status, action.note, events[-1].event_hash)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Case changed; reload before applying your action") from None
    except OperationalError:
        db.rollback()
        raise HTTPException(503, "Case store temporarily busy; reload and retry") from None
    return serialize(db, case)
