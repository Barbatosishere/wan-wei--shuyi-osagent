"""Owner isolation for work that runs outside an HTTP request context."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def owners(tmp_path, monkeypatch, seed_identity):
    monkeypatch.setenv("WANWEI_API_KEY", "pr215-configured-owner")
    monkeypatch.setenv("WANWEI_MEMORY_DB", str(tmp_path / "memory.db"))
    monkeypatch.setenv("WANWEI_PLATFORM_DIR", str(tmp_path / "platform"))
    monkeypatch.delenv("WANWEI_DEVICE_GEAR_ENABLED", raising=False)

    from backend.app.init_db import main as init_db
    from backend.app.soul.ownership import configured_actor_id

    init_db()
    return configured_actor_id(), seed_identity("pr215-other-owner")


@pytest.mark.parametrize("gear,expected_status", [("sandbox", "done"), ("device", "failed")])
def test_background_flow_audits_use_persisted_run_owner(owners, gear, expected_status):
    from backend.app.audit import service as audit
    from backend.app.platform_api import automation

    configured_owner, run_owner = owners
    flow = {
        "id": "flow_background_private",
        "owner_id": run_owner,
        "gear": gear,
        "steps": [{"id": "private-step", "type": "condition", "config": {"expr": "1 < 2"}}],
    }
    automation._flows.set(flow["id"], flow)
    run = automation._try_create_run(flow, triggered_by="manual", mode="real")
    assert run is not None

    # A scheduler or recovered task has no authenticated request to inherit.
    # A stale outer context must not override the persisted run's owner either.
    with audit.audit_owner_context(configured_owner):
        asyncio.run(automation._dispatch_run(run["id"], flow, "real"))
        assert audit.current_audit_owner() == configured_owner

    assert automation._runs.get(run["id"])["status"] == expected_status
    owned_events = audit.list_logs(owner_id=run_owner)
    assert any(event["event_type"] == "flow_run_finished" for event in owned_events)
    if gear == "device":
        assert any(event["event_type"] == "gear_denied" for event in owned_events)
    assert audit.list_logs(owner_id=configured_owner) == []


def test_scheduler_audits_use_each_flow_owner(owners, monkeypatch):
    from backend.app.audit import service as audit
    from backend.app.platform_api import automation

    configured_owner, flow_owner = owners
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    flow = {
        "id": "flow_scheduled_private",
        "owner_id": flow_owner,
        "name": "Private scheduled flow",
        "trigger": "schedule",
        "cron": "* * * * *",
        "enabled": True,
        "gear": "sandbox",
        "updated_at": now.isoformat(),
        "steps": [],
    }
    automation._flows.set(flow["id"], flow)
    monkeypatch.setattr(automation, "_schedule_state", {
        flow["id"]: {"updated_at": flow["updated_at"], "due": now},
    })
    monkeypatch.setattr(automation, "_launch_run", lambda *_args: None)
    monkeypatch.setattr(
        automation, "_next_cron_dt", lambda _cron, current: (current + timedelta(minutes=1), False),
    )

    first = automation._scheduler_tick(now)
    assert len(first) == 1
    assert automation._scheduler_tick(now + timedelta(minutes=1)) == []
    owned_events = audit.list_logs(owner_id=flow_owner)
    assert {event["event_type"] for event in owned_events} == {
        "flow_run_started", "flow_run_skipped",
    }
    assert all(json.loads(event["payload"])["flow_id"] == flow["id"] for event in owned_events)
    assert audit.list_logs(owner_id=configured_owner) == []
