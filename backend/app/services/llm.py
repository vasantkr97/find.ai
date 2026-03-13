from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from langchain_openai import ChatOpenAI
from openai import APIStatusError, AsyncOpenAI
from pydantic import BaseModel, SecretStr, ValidationError

from app.core.config import get_settings
from app.core.errors import LLMError, LLMParseError, LLMRateLimitError


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


class _CircuitBreaker:
    def __init__(self, threshold: int = 5, reset_ms: int = 60_000) -> None:
        self.threshold = threshold
        self.reset_ms = reset_ms
        self.failures = 0
        self.last_failure_ms = 0
        self.is_open = False

    def check(self) -> None:
        if not self.is_open:
            return
        now = int(time.time() * 1000)
        if now - self.last_failure_ms > self.reset_ms:
            self.is_open = False
            self.failures = 0
            return
        raise LLMError("LLM service circuit breaker is open - too many recent failures")

    def success(self) -> None:
        self.failures = 0
        self.is_open = False

    def failure(self) -> None:
        self.failures += 1
        self.last_failure_ms = int(time.time() * 1000)
        if self.failures >= self.threshold:
            self.is_open = True


cfg = get_settings()
client = AsyncOpenAI(api_key=cfg.OPENAI_API_KEY)
circuit = _CircuitBreaker()
T = TypeVar("T")
SchemaT = TypeVar("SchemaT", bound=BaseModel)
Message = dict[str, Any]


async def _with_retry(fn: Any, max_attempts: int, label: str) -> T:
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            circuit.check()
            result = await fn()
            circuit.success()
            return result
        except LLMRateLimitError as err:
            last_err = err
            await asyncio.sleep(err.retry_after_ms / 1000)
        except Exception as err:  # noqa: BLE001
            last_err = err if isinstance(err, Exception) else Exception(str(err))
            circuit.failure()
            if attempt < max_attempts:
                await asyncio.sleep((2**attempt) * 0.5)
    raise LLMError(f"{label} failed after {max_attempts} attempts", {"error": str(last_err)})


async def _create_chat_completion(**kwargs: Any) -> Any:
    # The OpenAI SDK type surface is stricter than our dynamic payload shape.
    return await cast(Any, client.chat.completions).create(**kwargs)


def _extract_usage(raw_usage: Any) -> LLMUsage:
    if not raw_usage:
        return LLMUsage()
    return LLMUsage(
        prompt_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
    )


async def chat(
    messages: list[Message],
    *,
    response_format: dict[str, Any] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[str, LLMUsage]:
    settings = get_settings()

    async def _call() -> tuple[str, LLMUsage]:
        try:
            payload: dict[str, Any] = {
                "model": model or settings.LLM_MODEL,
                "messages": messages,
                "temperature": (
                    temperature if temperature is not None else settings.LLM_TEMPERATURE
                ),
                "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            }
            if response_format is not None:
                payload["response_format"] = response_format
            response = await _create_chat_completion(**payload)
            content = response.choices[0].message.content or ""
            return content, _extract_usage(response.usage)
        except APIStatusError as err:
            if err.status_code == 429:
                retry_ms = int(err.response.headers.get("retry-after", "1")) * 1000
                raise LLMRateLimitError(max(retry_ms, 1000)) from err
            raise

    return await _with_retry(_call, settings.AGENT_LLM_RETRY_ATTEMPTS, "chat")


async def chat_json(
    messages: list[Message],
    schema: type[SchemaT],
    *,
    temperature: float | None = None,
) -> tuple[SchemaT, LLMUsage]:
    raw, usage = await chat(
        messages,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as err:
        raise LLMParseError("LLM returned invalid JSON", raw) from err
    try:
        return schema.model_validate(parsed), usage
    except ValidationError as err:
        raise LLMParseError(f"Schema validation failed: {err}", raw) from err


async def chat_stream(
    messages: list[Message],
    on_chunk: Any,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[str, LLMUsage]:
    settings = get_settings()

    async def _call() -> tuple[str, LLMUsage]:
        stream = await _create_chat_completion(
            model=model or settings.LLM_MODEL,
            messages=messages,
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            stream=True,
            stream_options={"include_usage": True},
        )
        content: list[str] = []
        usage = LLMUsage()
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                content.append(delta)
                on_chunk(delta)
            if chunk.usage:
                usage = _extract_usage(chunk.usage)
        return "".join(content), usage

    return await _with_retry(_call, settings.AGENT_LLM_RETRY_ATTEMPTS, "chat_stream")


async def create_embedding(text: str) -> list[float]:
    settings = get_settings()
    response = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    result: list[list[float]] = []
    batch_size = settings.EMBEDDING_BATCH_SIZE
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(model=settings.EMBEDDING_MODEL, input=batch)
        result.extend(item.embedding for item in response.data)
    return result


def get_langchain_chat_model() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        api_key=SecretStr(settings.OPENAI_API_KEY),
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        model_kwargs={"max_completion_tokens": settings.LLM_MAX_TOKENS},
    )
