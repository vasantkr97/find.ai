from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

request_user_id_var: ContextVar[str | None] = ContextVar("request_user_id", default=None)
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
request_runtime_var: ContextVar[dict[str, Any] | None] = ContextVar("request_runtime", default=None)


def get_request_user_id() -> str | None:
    return request_user_id_var.get()


@contextmanager
def request_user_context(user_id: str) -> Iterator[None]:
    token = request_user_id_var.set(user_id)
    try:
        yield
    finally:
        request_user_id_var.reset(token)


@contextmanager
def request_runtime_context(data: dict[str, Any]) -> Iterator[None]:
    token = request_runtime_var.set(data)
    try:
        yield
    finally:
        request_runtime_var.reset(token)


def get_request_runtime() -> dict[str, Any] | None:
    return request_runtime_var.get()
