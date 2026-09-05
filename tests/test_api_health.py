def test_health_returns_bootstrap_status():
    """A missing route or changed health payload breaks the bootstrap contract."""
    import asyncio

    from httpx import ASGITransport, AsyncClient

    from qualor.api import app

    async def get_health():
        async with AsyncClient(transport=ASGITransport(app), base_url="http://qualor") as client:
            return await client.get("/health")

    response = asyncio.run(get_health())
    assert response.status_code == 200
    assert response.json() == {"service": "qualor", "status": "ok", "phase": "bootstrap"}
