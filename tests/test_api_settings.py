"""
test_api_settings.py
Integration tests for the model settings and business profile endpoints,
including key masking and the optional ADMIN_TOKEN guard.
"""

import httpx
import pytest

from scripts.serve_api import app


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as c:
        yield c


@pytest.mark.anyio
async def test_model_settings_never_return_the_key(client):
    saved = await client.put(
        "/api/settings/model",
        json={"provider": "openai", "model": "gpt-test", "api_key": "sk-top-secret-9f3c"},
    )
    assert saved.status_code == 200
    assert "sk-top-secret-9f3c" not in saved.text
    assert saved.json()["api_key_hint"] == "…9f3c"
    assert saved.json()["base_url"] == "https://api.openai.com/v1"

    fetched = await client.get("/api/settings/model")
    assert "sk-top-secret-9f3c" not in fetched.text
    assert fetched.json()["is_configured"] is True


@pytest.mark.anyio
async def test_invalid_model_settings_are_rejected(client):
    resp = await client.put("/api/settings/model", json={"provider": "skynet"})
    assert resp.status_code == 422
    resp = await client.put("/api/settings/model", json={"provider": "custom", "base_url": "ftp://x"})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_providers_listing(client):
    providers = (await client.get("/api/providers")).json()
    ids = [p["id"] for p in providers]
    assert {"none", "anthropic", "openai", "ollama", "custom"} <= set(ids)


@pytest.mark.anyio
async def test_connection_test_reports_failure_without_saving(client):
    resp = await client.post(
        "/api/settings/model/test",
        json={"provider": "custom", "base_url": "http://127.0.0.1:9/v1", "model": "x", "timeout_s": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "reach" in body["error"]
    assert (await client.get("/api/settings/model")).json()["provider"] == "none"


@pytest.mark.anyio
async def test_connection_test_needs_a_model(client):
    body = (await client.post("/api/settings/model/test", json={})).json()
    assert body["ok"] is False
    assert "model" in body["error"].lower()


@pytest.mark.anyio
async def test_admin_token_guards_writes(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "letmein")

    denied = await client.put("/api/settings/model", json={"model": "x"})
    assert denied.status_code == 401
    assert (await client.put("/api/settings/profile", json={})).status_code == 401

    allowed = await client.put(
        "/api/settings/model", json={"provider": "ollama", "model": "x"}, headers={"Authorization": "Bearer letmein"}
    )
    assert allowed.status_code == 200
    # Reads stay open
    assert (await client.get("/api/settings/model")).status_code == 200


@pytest.mark.anyio
async def test_profile_round_trip_validation_and_reset(client):
    profile = (await client.get("/api/settings/profile")).json()
    assert sum(profile["scoring"]["weights"].values()) == 100

    profile["business"]["name"] = "Acme Bots"
    assert (await client.put("/api/settings/profile", json=profile)).json()["business"]["name"] == "Acme Bots"

    profile["scoring"]["weights"]["service_fit"] = 90
    bad = await client.put("/api/settings/profile", json=profile)
    assert bad.status_code == 422
    assert "100" in bad.text

    reset = (await client.post("/api/settings/profile/reset")).json()
    assert reset["business"]["name"] != "Acme Bots"


@pytest.mark.anyio
async def test_health_reports_engine(client):
    data = (await client.get("/health")).json()
    assert data["status"] == "ok"
    assert data["engine"] == "Rules only"


@pytest.mark.anyio
async def test_security_headers(client):
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in resp.headers["content-security-policy"]


@pytest.mark.anyio
async def test_foreign_host_header_is_rejected():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://attacker.example") as c:
        assert (await c.get("/health")).status_code == 400


@pytest.mark.anyio
async def test_cross_site_writes_are_rejected(client):
    cross = await client.post("/api/settings/profile/reset", headers={"Sec-Fetch-Site": "cross-site"})
    assert cross.status_code == 403
    other_origin = await client.post("/api/settings/profile/reset", headers={"Origin": "https://evil.example"})
    assert other_origin.status_code == 403
    same = await client.post("/api/settings/profile/reset", headers={"Origin": "http://127.0.0.1", "Sec-Fetch-Site": "same-origin"})
    assert same.status_code == 200


@pytest.mark.anyio
async def test_test_endpoint_does_not_send_saved_key_to_new_url(client):
    await client.put("/api/settings/model", json={"provider": "openai", "model": "gpt-x", "api_key": "sk-keep-me-secret"})
    body = (await client.post("/api/settings/model/test", json={"base_url": "http://127.0.0.1:9/v1"})).json()
    assert body["ok"] is False
    assert "api key" in body["error"].lower()
