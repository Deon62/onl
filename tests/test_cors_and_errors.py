from app.routers import platform

PANEL = {"Origin": "https://panel.oryne.org"}
REQ = {"business": "Kilele Foods", "contact_name": "Jane Doe", "email": "jane@kilele.co.ke", "phone": "0712345678",
       "domain": "kilelefoods.co.ke", "volume": "Under KES 100,000"}


async def test_server_errors_keep_cors_headers(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("database exploded")
    monkeypatch.setattr(platform, "log_activity", boom)
    r = await client.post("/v1/access-requests", json=REQ, headers=PANEL)
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == "https://panel.oryne.org"
    assert r.json()["error"]["code"] == "internal_error"


async def test_preflight_allows_put_for_settlement(client):
    r = await client.options("/v1/merchant/settlement", headers=PANEL | {
        "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "authorization,content-type"})
    assert r.status_code == 200 and "PUT" in r.headers["access-control-allow-methods"]


async def test_unknown_origin_gets_no_cors(client):
    r = await client.post("/v1/access-requests", json={}, headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_startup_migrations_apply(tmp_path, monkeypatch):
    """run_migrations() upgrades a fresh database to head without an alembic.ini."""
    import sqlite3

    from app.config import get_settings
    from app.main import run_migrations

    url = f"sqlite+aiosqlite:///{(tmp_path / 'm.db').as_posix()}"
    monkeypatch.setattr(get_settings(), "database_url", url)
    run_migrations()
    cols = [r[1] for r in sqlite3.connect(tmp_path / "m.db").execute("PRAGMA table_info(access_requests)")]
    assert "domain" in cols
