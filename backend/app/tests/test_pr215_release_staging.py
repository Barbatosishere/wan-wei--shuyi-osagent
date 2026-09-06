"""Exercise the code shipped after the desktop release-only cleanup patch."""

from __future__ import annotations

import ast
import re
import shutil
import subprocess
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[3]
PATCH = ROOT / "desktop/packaging/release-clean.patch"
SYSTEM_SERVICE = "backend/app/platform_api/_system_svc_runtime.py"
MOBILE_SOURCES = (
    "backend/app/platform_api/mobile_remote.py",
    "frontend/console-vue/src/views/platform/MobileView.vue",
)
SHARED_SECURITY_SOURCES = (
    "backend/app/security/auth.py",
    "backend/app/soul/ownership.py",
)


@pytest.fixture
def staged_release(tmp_path):
    stage = tmp_path / "release-stage"
    stage.mkdir()
    paths = set(MOBILE_SOURCES + SHARED_SECURITY_SOURCES)
    for line in PATCH.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"diff --git a/(.+) b/\1", line)
        if match:
            paths.add(match.group(1))

    originals = {}
    for relative in paths:
        source = ROOT / relative
        source.resolve().relative_to(ROOT)
        originals[relative] = source.read_bytes()
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(originals[relative])

    # Use a separate Git directory: pytest's temporary tree may live inside the
    # checkout, where implicit Git discovery would apply paths at the wrong root.
    metadata = tmp_path / "git-metadata"
    subprocess.run(["git", "init", "--bare", "--quiet", str(metadata)], check=True)
    apply = [
        "git", "-C", str(stage), f"--git-dir={metadata}",
        f"--work-tree={stage}", "apply",
    ]
    for flags in (["--check"], []):
        result = subprocess.run([*apply, *flags, str(PATCH)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    return SimpleNamespace(path=stage, originals=originals)


def test_release_cleanup_is_confined_to_staging_and_preserves_shared_auth(staged_release):
    for relative, original in staged_release.originals.items():
        assert (ROOT / relative).read_bytes() == original
    for relative in MOBILE_SOURCES:
        assert not (staged_release.path / relative).exists()
    for relative in SHARED_SECURITY_SOURCES:
        assert (staged_release.path / relative).read_bytes() == staged_release.originals[relative]


@pytest.fixture
def staged_lan_service(staged_release):
    source = (staged_release.path / SYSTEM_SERVICE).read_text(encoding="utf-8")
    module = ast.parse(source)
    retained_routes = [
        decorator.args[0].value
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call)
        and decorator.args
        and isinstance(decorator.args[0], ast.Constant)
        and isinstance(decorator.args[0].value, str)
        and decorator.args[0].value.startswith("/system/lan/")
    ]
    assert retained_routes == ["/system/lan/disable"]

    # Execute the retained route and its actual router-level dependency without
    # importing the source checkout's platform router or unrelated device I/O.
    selected = [
        node for node in module.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name in {"_require_device_owner", "lan_disable"}
        ) or (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "router" for target in node.targets)
        )
    ]
    assert len(selected) == 3
    # In-memory persisted-state fixture: the test never opens a listening socket.
    saved = {"lan": {"enabled": True, "token": "old-pairing-token", "bind": "0.0.0.0"}}  # nosec B104
    store = Mock()
    store._lock = threading.RLock()
    store.get.side_effect = lambda key: deepcopy(saved.get(key))
    store.set.side_effect = lambda key, value: saved.__setitem__(key, deepcopy(value))
    revoke = Mock(return_value=2)
    namespace = {
        "APIRouter": APIRouter, "Depends": Depends,
        "HTTPException": HTTPException, "Request": Request,
        "actor_id_for_request": lambda request: request.headers.get("x-test-actor", "anonymous"),
        "configured_actor_id": lambda: "device-owner",
        "_sys_store": store, "revoke_lan_sessions": revoke,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), SYSTEM_SERVICE, "exec"), namespace)
    app = FastAPI()
    app.include_router(namespace["router"], prefix="/platform")
    return SimpleNamespace(app=app, saved=saved, revoke=revoke)


def test_staged_disable_rejects_another_owner_before_revocation(staged_lan_service):
    service = staged_lan_service
    with TestClient(service.app) as client:
        response = client.post("/platform/system/lan/disable", headers={"x-test-actor": "other-owner"})
    assert response.status_code == 404
    service.revoke.assert_not_called()
    assert service.saved["lan"]["enabled"] is True


def test_staged_disable_revokes_sessions_and_clears_persisted_pairing(staged_lan_service):
    service = staged_lan_service
    with TestClient(service.app) as client:
        response = client.post("/platform/system/lan/disable", headers={"x-test-actor": "device-owner"})
    assert response.status_code == 200
    assert response.json() == {
        "enabled": False, "bind": "127.0.0.1", "lan_url": None,
        "token_set": False, "revoked_sessions": 2,
    }
    service.revoke.assert_called_once_with()
    assert service.saved["lan"]["enabled"] is False
    assert service.saved["lan"]["token"] is None
    assert service.saved["lan"]["token_consumed"] is False


def test_staged_disable_does_not_report_success_when_revocation_fails(staged_lan_service):
    service = staged_lan_service
    service.revoke.side_effect = RuntimeError("credential store unavailable")
    with TestClient(service.app, raise_server_exceptions=False) as client:
        response = client.post("/platform/system/lan/disable", headers={"x-test-actor": "device-owner"})
    assert response.status_code == 500
    assert service.saved["lan"]["enabled"] is True


def test_staged_desktop_keeps_cold_start_cleanup_without_mobile_entrypoints(staged_release):
    main = staged_release.path / "desktop/src/main.js"
    source = main.read_text(encoding="utf-8")
    assert "function reconcileLanState()" in source
    assert "/platform/system/lan/disable" in source
    assert re.search(r"await startBackend\(py\);\s+await reconcileLanState\(\);", source)
    assert "desktop:lan-enable" not in source
    assert "/console/#/mobile" not in source
    router = (staged_release.path / "frontend/console-vue/src/router/platform.ts").read_text(encoding="utf-8")
    assert "MobileView" not in router
    assert not re.search(r"path:\s*['\"]/?mobile['\"]", router)
    node = shutil.which("node")
    if node:
        subprocess.run([node, "--check", str(main)], check=True, capture_output=True)
