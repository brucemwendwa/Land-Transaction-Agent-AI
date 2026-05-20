from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/mradi_test.sqlite3")
os.environ.setdefault("AUTH_BYPASS", "true")
os.environ.setdefault("LOCAL_STORAGE_ROOT", "./test-local-storage")
os.environ.setdefault("API_BASE_URL", "http://testserver")

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.db.session import Base, engine
from app.main import app


class ASGITestClient:
    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        return asyncio.run(self._request(method, url, **kwargs))

    async def _request(self, method: str, url: str, **kwargs: Any) -> Response:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Response:
        return self.request("PATCH", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Response:
        return self.request("DELETE", url, **kwargs)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> ASGITestClient:
    return ASGITestClient()
