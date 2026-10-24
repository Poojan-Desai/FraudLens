from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.auth import Principal
from backend.app.case_schemas import CaseAction, CaseSnapshot
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import CaseEvent, InvestigationCase
from backend.app.services import cases

TOKENS = {role: (role + "-") * 12 for role in ("admin", "analyst", "viewer")}


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'cases.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    def database():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = database
    monkeypatch.setenv("FRAUDLENS_CASE_TOKENS", json.dumps({token: {"actor": role + "-identity", "role": role} for role, token in TOKENS.items()}))
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def headers(role="admin"):
    return {"Authorization": f"Bearer {TOKENS[role]}"}


def snapshot(**overrides):
    return {"transaction_id": "DEMO-100", "timestamp": "2026-01-01T00:00:00+00:00", "amount": 123.45,
            "merchant_category": "electronics", "country": "United States", "fraud_probability": .8,
            "threshold": .4, "model_version": "test-v1", "source": "caller_supplied_simulation",
            "features": {"new_device": True}, "reason_codes": ["Observed new device; not a causal explanation"], **overrides}


def created(client):
    response = client.post("/api/v1/cases", json=snapshot(), headers=headers())
    assert response.status_code == 201, response.text
    return response.json()


def act(client, case, status=None, role="analyst", **overrides):
    return client.post(f'/api/v1/cases/{case["id"]}/actions', headers=headers(role), json={
        "expected_version": case["version"], "action": "transition" if status else "note", "note": "Reviewed synthetic evidence",
        **({"status": status} if status else {}), **overrides})


def test_access_fails_closed_without_credentials(store, monkeypatch):
    client, _ = store
    assert client.get("/api/v1/cases").status_code == 401
    assert client.get("/api/v1/cases", headers={"Authorization": "Bearer incorrect"}).status_code == 401
    monkeypatch.delenv("FRAUDLENS_CASE_TOKENS")
    assert client.get("/api/v1/cases", headers=headers()).status_code == 503
    monkeypatch.setenv("FRAUDLENS_CASE_TOKENS", '{"weak":{"actor":"admin","role":"admin"}}')
    assert client.get("/api/v1/cases", headers=headers()).status_code == 503


def test_roles_actor_identity_and_export_redaction(store):
    client, _ = store
    assert client.post("/api/v1/cases", json=snapshot(), headers=headers("analyst")).status_code == 403
    case = created(client)
    assert client.get("/api/v1/cases/identity", headers=headers("viewer")).json()["role"] == "viewer"
    assert client.get(f'/api/v1/cases/{case["id"]}', headers=headers("viewer")).status_code == 200
    assert act(client, case, role="viewer").status_code == 403
    assert client.get(f'/api/v1/cases/{case["id"]}/export', headers=headers("viewer")).status_code == 403
    note = "<script>alert('untrusted text')</script> private note"
    updated = act(client, case, note=note).json()
    assert updated["history"][-1]["actor"] == "analyst-identity"
    assert updated["history"][-1]["note"] == note
    assert updated["training_label_eligible"] is False
    exported = client.get(f'/api/v1/cases/{case["id"]}/export', headers=headers("analyst"))
    assert exported.headers["content-type"] == "application/json"
    assert exported.headers["cache-control"] == "no-store"
    assert exported.headers["x-content-type-options"] == "nosniff"
    assert note not in exported.text and "analyst-identity" not in exported.text
    assert "note" not in exported.json()["case"]["history"][-1]
    assert "Redacted" in exported.json()["disclosure"]


def test_review_resolution_reopen_and_snapshot_preservation(store):
    client, _ = store
    case = created(client)
    original = case["snapshot_sha256"]
    assert act(client, case, "confirmed_fraud").status_code == 422
    case = act(client, case, "reviewed").json()
    case = act(client, case, "confirmed_fraud").json()
    assert act(client, case, "legitimate").status_code == 422
    assert act(client, case, "reviewed").status_code == 422
    case = act(client, case, "reviewed", role="admin").json()
    case = act(client, case, "legitimate").json()
    assert case["snapshot_sha256"] == original
    assert case["audit_integrity"] == "verified"
    assert [event["version"] for event in case["history"]] == [1, 2, 3, 4, 5]
    for previous, current in zip(case["history"], case["history"][1:]):
        assert current["previous_hash"] == previous["event_hash"]
    assert case["training_label_eligible"] is False


def test_stale_updates_and_invalid_actions_leave_no_event(store):
    client, engine = store
    first = created(client)
    case = act(client, first, "reviewed").json()
    assert act(client, first, "reviewed").status_code == 409
    assert act(client, case, action="note", status="pending").status_code == 422
    assert act(client, case, actor="spoof").status_code == 422
    assert act(client, case, note="  ").status_code == 422
    with Session(engine) as db:
        assert len(cases.journal(db, first["id"])) == 2


def test_duplicate_unflagged_missing_invalid_or_labeled_snapshots(store):
    client, _ = store
    created(client)
    assert client.post("/api/v1/cases", json=snapshot(), headers=headers()).status_code == 409
    invalid = [{"fraud_probability": .1}, {"fraud_probability": 1.1}, {"amount": -1}, {"timestamp": "2026-01-01"},
               {"source": "verified_synthetic_study"}, {"features": {"is_fraud": True}}, {"is_fraud": True}, {"features": {"x": "x" * 201}}]
    for override in invalid:
        response = client.post("/api/v1/cases", json=snapshot(transaction_id="DEMO-other", **override), headers=headers())
        assert response.status_code == 422, response.text
    data = snapshot(transaction_id="DEMO-other")
    del data["model_version"]
    assert client.post("/api/v1/cases", json=data, headers=headers()).status_code == 422


def test_search_is_literal_and_pagination_bounded(store):
    client, _ = store
    created(client)
    for identifier in ("DEMO-200", "DEMO-300"):
        assert client.post("/api/v1/cases", json=snapshot(transaction_id=identifier), headers=headers()).status_code == 201
    assert len(client.get("/api/v1/cases?search=DEMO-1", headers=headers()).json()["items"]) == 1
    assert client.get("/api/v1/cases?search=%25", headers=headers()).json()["items"] == []
    assert client.get("/api/v1/cases?search=' OR 1=1 --", headers=headers()).json()["items"] == []
    page = client.get("/api/v1/cases?limit=2", headers=headers()).json()
    assert len(page["items"]) == 2 and page["has_more"]
    page2 = client.get("/api/v1/cases?limit=2&offset=2", headers=headers()).json()
    assert len(page2["items"]) == 1 and not page2["has_more"]
    assert client.get("/api/v1/cases?limit=101", headers=headers()).status_code == 422
    assert client.get("/api/v1/cases?status=unknown", headers=headers()).status_code == 422


def test_real_simultaneous_writers_allow_one_update(store):
    client, engine = store
    case = created(client)
    ready = Barrier(2)
    def update():
        with Session(engine) as db:
            ready.wait(timeout=5)
            try:
                return cases.apply_action(db, case["id"], CaseAction(expected_version=1, action="transition", status="reviewed", note="Simultaneous analyst decision"), Principal("analyst", "analyst"))["version"]
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: update(), range(2)))
    assert sorted(results) == [2, 409]
    with Session(engine) as db:
        saved = db.get(InvestigationCase, case["id"])
        assert saved.version == 2 and cases.verify(saved, cases.journal(db, saved.id))


def test_audit_append_failure_rolls_back_state(store, monkeypatch):
    client, engine = store
    case = created(client)
    def fail(*args, **kwargs):
        raise IntegrityError("synthetic journal failure", {}, Exception("injected"))
    monkeypatch.setattr(cases, "append_event", fail)
    assert act(client, case, "reviewed").status_code == 409
    with Session(engine) as db:
        saved = db.get(InvestigationCase, case["id"])
        assert saved.version == 1 and saved.status == "pending"
        assert cases.verify(saved, cases.journal(db, saved.id))


def test_sqlite_journal_is_append_only_and_snapshot_tamper_fails_closed(store):
    client, engine = store
    case = created(client)
    with engine.begin() as connection:
        with pytest.raises(IntegrityError, match="append-only"):
            connection.execute(text("UPDATE case_events SET event_hash = 'tampered'"))
        with pytest.raises(IntegrityError, match="append-only"):
            connection.execute(text("DELETE FROM case_events"))
        connection.execute(text("UPDATE investigation_cases SET snapshot_json = '{}' WHERE id=:id"), {"id": case["id"]})
    assert client.get(f'/api/v1/cases/{case["id"]}', headers=headers()).status_code == 409
    assert act(client, case).status_code == 409
    assert client.get(f'/api/v1/cases/{case["id"]}/export', headers=headers()).status_code == 409


def test_chain_detects_event_tampering_even_if_database_owner_disables_trigger(store):
    client, engine = store
    case = created(client)
    with engine.begin() as connection:
        connection.execute(text("DROP TRIGGER case_events_no_update"))
        connection.execute(text("UPDATE case_events SET payload_json = '{}'"))
    assert client.get(f'/api/v1/cases/{case["id"]}', headers=headers()).status_code == 409


def test_cors_allows_only_configured_local_origins(store):
    client, _ = store
    response = client.options("/api/v1/cases", headers={"Origin": "http://127.0.0.1:4176", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:4176"
    denied = client.options("/api/v1/cases", headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in denied.headers


def test_cached_read_refreshes_case_and_journal_as_one_snapshot(store):
    client, engine = store
    case = created(client)
    principal = Principal("analyst", "analyst")
    with Session(engine) as stale:
        cached = cases.case_or_404(stale, case["id"])
        assert cached.version == 1
        with Session(engine) as writer:
            cases.apply_action(writer, case["id"], CaseAction(expected_version=1, action="transition", status="reviewed", note="Committed between reader queries"), principal)
        # A cached v1 row plus a newly read v2 journal is valid concurrent work,
        # not corruption. Detail and list serialization must refresh both.
        refreshed = cases.serialize(stale, cached)
        assert refreshed["version"] == 2 and len(refreshed["history"]) == 2
        assert refreshed["audit_integrity"] == "verified"
        with Session(engine) as writer:
            cases.apply_action(writer, case["id"], CaseAction(expected_version=2, action="note", note="Another committed update"), principal)
        # Mutation must also refresh a stale identity before its integrity test.
        latest = cases.apply_action(stale, case["id"], CaseAction(expected_version=3, action="note", note="Reader accepts current version"), principal)
        assert latest["version"] == 4 and latest["audit_integrity"] == "verified"


@pytest.mark.parametrize("column,value", [("transaction_id", "TAMPERED-ID"), ("created_at", "1900-01-01T00:00:00+00:00")])
def test_case_metadata_is_bound_to_snapshot_and_genesis(store, column, value):
    client, engine = store
    case = created(client)
    with engine.begin() as connection:
        # Column names are fixed test parameters, never user-supplied SQL.
        connection.execute(text(f"UPDATE investigation_cases SET {column}=:value WHERE id=:id"), {"id": case["id"], "value": value})
    assert client.get(f'/api/v1/cases/{case["id"]}', headers=headers()).status_code == 409
    assert client.get('/api/v1/cases', headers=headers()).status_code == 409
    assert act(client, case).status_code == 409
    assert client.get(f'/api/v1/cases/{case["id"]}/export', headers=headers()).status_code == 409
