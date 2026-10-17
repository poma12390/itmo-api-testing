import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


def test_create_task_and_read_it(client: TestClient) -> None:
    payload = {"title": "Сдать работу", "priority": 2, "completed": False}
    created = client.post("/tasks", json=payload)

    assert created.status_code == 201
    assert created.headers["content-type"] == "application/json"
    task = created.json()
    assert task == {"id": 1, **payload}
    assert created.headers["location"] == f"/tasks/{task['id']}"

    fetched = client.get(created.headers["location"])
    assert fetched.status_code == 200
    assert fetched.json() == task


def test_create_task_uses_defaults(client: TestClient) -> None:
    response = client.post("/tasks", json={"title": "Новая задача"})

    assert response.status_code == 201
    assert response.json() == {"id": 1, "title": "Новая задача", "priority": 3, "completed": False}


@pytest.mark.parametrize("method", ["post", "put"])
def test_integer_valued_json_number_is_accepted(
    client: TestClient,
    task: dict,
    method: str,
) -> None:
    url = "/tasks" if method == "post" else f"/tasks/{task['id']}"
    response = client.request(method, url, json={"title": "Целое число", "priority": 4.0})

    assert response.status_code == (201 if method == "post" else 200)
    assert response.json()["priority"] == 4
    assert type(response.json()["priority"]) is int


def test_list_tasks_is_initially_empty(client: TestClient) -> None:
    response = client.get("/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_list_tasks_applies_pagination(client: TestClient) -> None:
    tasks = []
    for title in ["Первая", "Вторая", "Третья"]:
        response = client.post("/tasks", json={"title": title})
        assert response.status_code == 201
        tasks.append(response.json())

    response = client.get("/tasks", params={"limit": 1, "offset": 1})
    assert response.status_code == 200
    assert response.json() == [tasks[1]]

    beyond_last = client.get("/tasks", params={"offset": 3})
    assert beyond_last.status_code == 200
    assert beyond_last.json() == []


def test_replace_task_persists_changes(client: TestClient, task: dict) -> None:
    payload = {"title": "Проверить контракт", "priority": 5, "completed": True}
    response = client.put(f"/tasks/{task['id']}", json=payload)

    assert response.status_code == 200
    assert response.json() == {"id": task["id"], **payload}
    fetched = client.get(f"/tasks/{task['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == response.json()


def test_put_replaces_the_whole_task(client: TestClient, task: dict) -> None:
    response = client.put(f"/tasks/{task['id']}", json={"title": "Заменённая задача"})

    assert response.status_code == 200
    assert response.json() == {
        "id": task["id"],
        "title": "Заменённая задача",
        "priority": 3,
        "completed": False,
    }


def test_delete_task_removes_it(client: TestClient, task: dict) -> None:
    url = f"/tasks/{task['id']}"
    response = client.delete(url)

    assert response.status_code == 204
    assert response.content == b""
    fetched = client.get(url)
    assert fetched.status_code == 404
    assert fetched.json() == {"detail": "Task not found"}
    repeated = client.delete(url)
    assert repeated.status_code == 404


@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_missing_task_returns_404(client: TestClient, method: str) -> None:
    kwargs = {"json": {"title": "Отсутствующая задача"}} if method == "put" else {}
    response = client.request(method, "/tasks/999", **kwargs)

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}
    assert client.get("/tasks").json() == []


@pytest.mark.parametrize("length", [1, 100], ids=["min-title", "max-title"])
@pytest.mark.parametrize("priority", [1, 5], ids=["min-priority", "max-priority"])
def test_title_and_priority_boundaries(client: TestClient, length: int, priority: int) -> None:
    payload = {"title": "я" * length, "priority": priority}
    response = client.post("/tasks", json=payload)

    assert response.status_code == 201
    assert response.json() == {"id": 1, **payload, "completed": False}


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        pytest.param({}, "title", id="missing-title"),
        pytest.param({"title": ""}, "title", id="empty-title"),
        pytest.param({"title": " \t\n"}, "title", id="blank-title"),
        pytest.param({"title": "x" * 101}, "title", id="too-long-title"),
        pytest.param({"title": None}, "title", id="null-title"),
        pytest.param({"title": 123}, "title", id="numeric-title"),
        pytest.param({"title": "Задача", "priority": 0}, "priority", id="priority-below-min"),
        pytest.param({"title": "Задача", "priority": 6}, "priority", id="priority-above-max"),
        pytest.param({"title": "Задача", "priority": "3"}, "priority", id="string-priority"),
        pytest.param({"title": "Задача", "priority": 2.5}, "priority", id="float-priority"),
        pytest.param({"title": "Задача", "priority": True}, "priority", id="boolean-priority"),
        pytest.param({"title": "Задача", "priority": None}, "priority", id="null-priority"),
        pytest.param({"title": "Задача", "completed": "false"}, "completed", id="string-boolean"),
        pytest.param({"title": "Задача", "completed": 1}, "completed", id="numeric-boolean"),
        pytest.param({"title": "Задача", "completed": None}, "completed", id="null-boolean"),
        pytest.param({"title": "Задача", "id": 10}, "id", id="client-defined-id"),
    ],
)
@pytest.mark.parametrize("method", ["post", "put"])
def test_invalid_body_is_rejected_without_side_effects(
    client: TestClient,
    task: dict,
    payload: dict,
    field: str,
    method: str,
) -> None:
    url = "/tasks" if method == "post" else f"/tasks/{task['id']}"
    response = client.request(method, url, json=payload)

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    assert client.get("/tasks").json() == [task]


def test_malformed_json_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/tasks",
        content='{"title":',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "json_invalid"
    assert client.get("/tasks").json() == []


@pytest.mark.parametrize("method", ["post", "put"])
def test_invalid_body_encoding_is_rejected_without_side_effects(
    client: TestClient,
    task: dict,
    method: str,
) -> None:
    url = "/tasks" if method == "post" else f"/tasks/{task['id']}"
    response = client.request(
        method,
        url,
        content=b'{"title":"\xff"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "There was an error parsing the body"}
    assert client.get("/tasks").json() == [task]


@pytest.mark.parametrize("task_id", ["0", "-1", "abc", "1.5"])
@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_invalid_task_id_is_rejected(client: TestClient, task_id: str, method: str) -> None:
    kwargs = {"json": {"title": "Задача"}} if method == "put" else {}
    response = client.request(method, f"/tasks/{task_id}", **kwargs)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["path", "task_id"]


@pytest.mark.parametrize("limit", [1, 100])
def test_pagination_accepts_boundary_limits(client: TestClient, task: dict, limit: int) -> None:
    response = client.get("/tasks", params={"limit": limit, "offset": 0})

    assert response.status_code == 200
    assert response.json() == [task]


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"limit": "abc"}, "limit"),
        ({"offset": -1}, "offset"),
        ({"offset": "abc"}, "offset"),
    ],
)
def test_invalid_pagination_is_rejected(client: TestClient, params: dict, field: str) -> None:
    response = client.get("/tasks", params=params)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", field]


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("/tasks", {"GET", "POST"}),
        ("/tasks/1", {"GET", "PUT", "DELETE"}),
    ],
)
def test_unsupported_method_lists_all_allowed_methods(
    client: TestClient,
    task: dict,
    path: str,
    allowed: set[str],
) -> None:
    response = client.patch(path, json={"title": "Не должно сохраниться"})

    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}
    assert {method.strip() for method in response.headers["allow"].split(",")} == allowed
    assert client.get("/tasks").json() == [task]
