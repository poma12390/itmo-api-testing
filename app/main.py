from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=100, pattern=r"\S", examples=["Сдать лабораторную"])
    priority: int = Field(default=3, ge=1, le=5)
    completed: bool = False


class Task(TaskInput):
    id: int = Field(ge=1)


class Error(BaseModel):
    detail: str


TaskId = Annotated[int, Path(ge=1)]
NOT_FOUND = {404: {"model": Error, "description": "Task does not exist"}}


def create_app() -> FastAPI:
    api = FastAPI(
        title="Tasks API",
        version="1.0.0",
        description="Учебный REST API. Данные хранятся в памяти до перезапуска процесса.",
    )
    tasks: dict[int, Task] = {}
    next_id = 1

    def find_task(task_id: int) -> Task:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        return tasks[task_id]

    @api.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED, tags=["tasks"])
    async def create_task(payload: TaskInput, response: Response) -> Task:
        nonlocal next_id
        task = Task(id=next_id, **payload.model_dump())
        tasks[task.id] = task
        next_id += 1
        response.headers["Location"] = f"/tasks/{task.id}"
        return task

    @api.get("/tasks", response_model=list[Task], tags=["tasks"])
    async def list_tasks(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[Task]:
        return list(tasks.values())[offset : offset + limit]

    @api.get("/tasks/{task_id}", response_model=Task, responses=NOT_FOUND, tags=["tasks"])
    async def get_task(task_id: TaskId) -> Task:
        return find_task(task_id)

    @api.put("/tasks/{task_id}", response_model=Task, responses=NOT_FOUND, tags=["tasks"])
    async def replace_task(task_id: TaskId, payload: TaskInput) -> Task:
        find_task(task_id)
        task = Task(id=task_id, **payload.model_dump())
        tasks[task_id] = task
        return task

    @api.delete(
        "/tasks/{task_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        responses=NOT_FOUND,
        tags=["tasks"],
    )
    async def delete_task(task_id: TaskId) -> Response:
        find_task(task_id)
        del tasks[task_id]
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return api


app = create_app()
