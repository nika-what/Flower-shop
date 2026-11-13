import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_healthcheck():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


@pytest.mark.asyncio
async def test_docs_available():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/docs')
    assert response.status_code == 200
