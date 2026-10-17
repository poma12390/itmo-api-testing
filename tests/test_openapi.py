import json
from pathlib import Path

import pytest
import schemathesis
from fastapi.testclient import TestClient

from app.main import create_app

pytestmark = pytest.mark.contract
SPEC_PATH = Path(__file__).resolve().parents[1] / "openapi.json"
schema = schemathesis.openapi.from_path(SPEC_PATH)


def test_exported_openapi_matches_application(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json() == json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@schema.parametrize()
def test_generated_requests_follow_openapi(case: schemathesis.Case) -> None:
    # Отдельное приложение на каждый пример Hypothesis, а не только на тест pytest.
    api = create_app()
    with TestClient(api) as client:
        seeded = client.post("/tasks", json={"title": "Задача для контрактного теста"})
        assert seeded.status_code == 201
        case.call_and_validate(app=api)
