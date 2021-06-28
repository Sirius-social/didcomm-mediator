import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test.com") as cli:
        resp = await cli.get("/maintenance/health_check")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['ok'] is True
    assert 'utc' in payload
