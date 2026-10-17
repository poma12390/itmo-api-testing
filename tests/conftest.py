from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def task(client: TestClient) -> dict:
    response = client.post("/tasks", json={"title": "Подготовить API-тесты", "priority": 2})
    assert response.status_code == 201
    return response.json()
