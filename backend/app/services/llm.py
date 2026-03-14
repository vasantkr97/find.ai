from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

import httpx
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
_http_client = httpx.AsyncClient(trust_env=False, timeout=60.0)
_openai_client: AsyncOpenAI | None = None
_openai_api_key: str | None = None
circuit = _CircuitBreaker()
T = TypeVar("T")
SchemaT = TypeVar("SchemaT", bound=BaseModel)
Message = dict[str, Any]
OnChunk = Callable[[str], None]
_JSON_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\\s*|\\s*```$", re.MULTILINE)


def _as_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    return None


def _strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = _JSON_FENCE_RE.sub("", text)
    return text.strip()


def _extract_json_object(raw: str) -> str | None:
    text = raw.strip()
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "\"":
                in_string = False
            continue
        if ch == "\"":
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def parse_json_object(raw: str) -> Any:
    text = _strip_json_fences(raw)
    last_err: json.JSONDecodeError | None = None

    for _ in range(3):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as err:
            last_err = err
            extracted = _extract_json_object(text) or _extract_json_object(raw)
            if extracted and extracted != text:
                text = extracted
                continue
            break

        if isinstance(parsed, str):
            inner = parsed.strip()
            if inner.startswith("{") or inner.startswith("["):
                text = inner
                continue
        return parsed

    if last_err:
        raise last_err
    raise json.JSONDecodeError("Invalid JSON", raw, 0)


def _get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    key = settings.OPENAI_API_KEY
    if not key:
        raise LLMError("OPENAI_API_KEY not configured")
    global _openai_client, _openai_api_key
    if _openai_client is None or _openai_api_key != key:
        _openai_client = AsyncOpenAI(api_key=key, http_client=_http_client)
        _openai_api_key = key
    return _openai_client


def _extract_openai_error_detail(err: APIStatusError) -> str | None:
    try:
        payload = _as_dict(err.response.json())
    except Exception:  # noqa: BLE001
        return None
    if not payload:
        return None
    error_obj = _as_dict(payload.get("error"))
    if not error_obj:
        return None
    code = error_obj.get("code")
    message = error_obj.get("message")
    if isinstance(code, str) and code:
        return code
    if isinstance(message, str) and message:
        return message
    return None


def _extract_gemini_error_detail(response: httpx.Response) -> str | None:
    try:
        payload = _as_dict(response.json())
    except Exception:  # noqa: BLE001
        text = response.text.strip()
        return text[:200] if text else None
    if not payload:
        return None
    error_obj = _as_dict(payload.get("error"))
    if not error_obj:
        return None
    status = error_obj.get("status")
    code = error_obj.get("code")
    message = error_obj.get("message")
    if isinstance(message, str) and message:
        if isinstance(status, str) and status:
            return f"{status}: {message}"
        return message
    if isinstance(status, str) and status:
        return status
    if isinstance(code, str) and code:
        return code
    return None


def _extract_ollama_error_detail(response: httpx.Response) -> str | None:
    try:
        payload = _as_dict(response.json())
    except Exception:  # noqa: BLE001
        text = response.text.strip()
        return text[:400] if text else None
    if not payload:
        return None
    err = payload.get("error")
    if isinstance(err, str) and err:
        return err
    msg = payload.get("message")
    if isinstance(msg, str) and msg:
        return msg
    return None


def _build_gemini_payload(
    messages: list[Message],
    *,
    temperature: float | None,
    max_tokens: int | None,
    response_format: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for row in messages:
        role = str(row.get("role", "user"))
        content = row.get("content")
        text = content if isinstance(content, str) else str(content or "")
        if not text.strip():
            continue
        if role == "system":
            system_parts.append(text)
            continue
        mapped_role = "model" if role == "assistant" else "user"
        contents.append({"role": mapped_role, "parts": [{"text": text}]})

    if not contents:
        contents.append({"role": "user", "parts": [{"text": " "}]} )

    generation_config: dict[str, Any] = {
        "temperature": (
            temperature if temperature is not None else settings.LLM_TEMPERATURE
        ),
        "maxOutputTokens": max_tokens or settings.LLM_MAX_TOKENS,
    }
    if response_format and response_format.get("type") == "json_object":
        generation_config["responseMimeType"] = "application/json"

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": generation_config,
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    return payload


def _extract_gemini_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        feedback = payload.get("promptFeedback")
        if isinstance(feedback, dict):
            block_reason = feedback.get("blockReason")
            if isinstance(block_reason, str) and block_reason:
                raise LLMError(f"Gemini blocked request: {block_reason}")
        return ""
    first = candidates[0]
    if not isinstance(first, dict):
        return ""
    content = first.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def _extract_gemini_usage(payload: Any) -> LLMUsage:
    if not isinstance(payload, dict):
        return LLMUsage()
    usage = payload.get("usageMetadata")
    if not isinstance(usage, dict):
        return LLMUsage()
    return LLMUsage(
        prompt_tokens=int(usage.get("promptTokenCount", 0) or 0),
        completion_tokens=int(usage.get("candidatesTokenCount", 0) or 0),
    )


def _normalize_gemini_model_name(model: str) -> str:
    return model.removeprefix("models/")


def _normalize_ollama_base_url(url: str) -> str:
    return url.rstrip("/")


def _convert_messages_for_ollama(messages: list[Message]) -> list[dict[str, str]]:
    converted: list[dict[str, str]] = []
    for row in messages:
        role = str(row.get("role", "user"))
        content = row.get("content")
        text = content if isinstance(content, str) else str(content or "")
        if not text.strip():
            continue
        mapped_role = "assistant" if role == "assistant" else "user"
        if role == "system":
            mapped_role = "system"
        converted.append({"role": mapped_role, "content": text})
    if not converted:
        converted.append({"role": "user", "content": " "})
    return converted


def _ollama_options(temperature: float | None, max_tokens: int | None) -> dict[str, Any]:
    settings = get_settings()
    return {
        "temperature": (
            temperature if temperature is not None else settings.LLM_TEMPERATURE
        ),
        "num_predict": max_tokens or settings.LLM_MAX_TOKENS,
    }


def _extract_ollama_usage(payload: Any) -> LLMUsage:
    if not isinstance(payload, dict):
        return LLMUsage()
    return LLMUsage(
        prompt_tokens=int(payload.get("prompt_eval_count", 0) or 0),
        completion_tokens=int(payload.get("eval_count", 0) or 0),
    )


async def _create_ollama_chat_completion(
    messages: list[Message],
    *,
    response_format: dict[str, Any] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[str, LLMUsage]:
    settings = get_settings()
    ollama_model = model or settings.OLLAMA_MODEL
    payload: dict[str, Any] = {
        "model": ollama_model,
        "messages": _convert_messages_for_ollama(messages),
        "stream": False,
        "options": _ollama_options(temperature, max_tokens),
    }
    if response_format and response_format.get("type") == "json_object":
        payload["format"] = "json"

    url = f"{_normalize_ollama_base_url(settings.OLLAMA_BASE_URL)}/api/chat"
    try:
        response = await _http_client.post(url, json=payload)
    except httpx.HTTPError as err:
        raise LLMError(f"Ollama request failed: {err}") from err

    if response.status_code == 429:
        detail = _extract_ollama_error_detail(response)
        raise LLMRateLimitError(1000, detail)
    if response.status_code >= 400:
        detail = _extract_ollama_error_detail(response) or f"HTTP {response.status_code}"
        raise LLMError(
            f"Ollama API error: {detail}",
            {"status_code": response.status_code},
        )

    payload_json = response.json()
    if not isinstance(payload_json, dict):
        return "", LLMUsage()
    message = payload_json.get("message")
    content = ""
    if isinstance(message, dict):
        value = message.get("content")
        if isinstance(value, str):
            content = value
    usage = _extract_ollama_usage(payload_json)
    return content, usage


async def _create_ollama_chat_stream(
    messages: list[Message],
    on_chunk: OnChunk,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[str, LLMUsage]:
    settings = get_settings()
    ollama_model = model or settings.OLLAMA_MODEL
    payload = {
        "model": ollama_model,
        "messages": _convert_messages_for_ollama(messages),
        "stream": True,
        "options": _ollama_options(temperature, max_tokens),
    }
    url = f"{_normalize_ollama_base_url(settings.OLLAMA_BASE_URL)}/api/chat"

    content_chunks: list[str] = []
    usage = LLMUsage()
    try:
        async with _http_client.stream("POST", url, json=payload) as response:
            if response.status_code == 429:
                detail = _extract_ollama_error_detail(response)
                raise LLMRateLimitError(1000, detail)
            if response.status_code >= 400:
                detail = _extract_ollama_error_detail(response) or f"HTTP {response.status_code}"
                raise LLMError(
                    f"Ollama API error: {detail}",
                    {"status_code": response.status_code},
                )
            async for line in response.aiter_lines():
                row = line.strip()
                if not row:
                    continue
                try:
                    payload_json = json.loads(row)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload_json, dict):
                    continue
                message = payload_json.get("message")
                if isinstance(message, dict):
                    chunk = message.get("content")
                    if isinstance(chunk, str) and chunk:
                        content_chunks.append(chunk)
                        on_chunk(chunk)
                if payload_json.get("done") is True:
                    usage = _extract_ollama_usage(payload_json)
    except httpx.HTTPError as err:
        raise LLMError(f"Ollama request failed: {err}") from err

    return "".join(content_chunks), usage


async def _ollama_embed(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    url = f"{_normalize_ollama_base_url(settings.OLLAMA_BASE_URL)}/api/embed"
    payload = {"model": settings.OLLAMA_EMBEDDING_MODEL, "input": texts}
    try:
        response = await _http_client.post(url, json=payload)
    except httpx.HTTPError as err:
        raise LLMError(f"Ollama embedding request failed: {err}") from err
    if response.status_code >= 400:
        detail = _extract_ollama_error_detail(response) or f"HTTP {response.status_code}"
        raise LLMError(
            f"Ollama embedding API error: {detail}",
            {"status_code": response.status_code},
        )
    payload_json = response.json()
    if not isinstance(payload_json, dict):
        return []
    embeddings = payload_json.get("embeddings")
    if not isinstance(embeddings, list):
        return []
    result: list[list[float]] = []
    for row in embeddings:
        if isinstance(row, list):
            result.append([float(v) for v in row])
    return result


async def _create_gemini_chat_completion(
    messages: list[Message],
    *,
    response_format: dict[str, Any] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[str, LLMUsage]:
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY not configured")

    gemini_model = _normalize_gemini_model_name(model or settings.GEMINI_MODEL)
    payload = _build_gemini_payload(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"
    try:
        response = await _http_client.post(
            url,
            params={"key": settings.GEMINI_API_KEY},
            json=payload,
        )
    except httpx.HTTPError as err:
        raise LLMError(f"Gemini request failed: {err}") from err

    if response.status_code == 429:
        detail = _extract_gemini_error_detail(response)
        raise LLMRateLimitError(1000, detail)
    if response.status_code >= 400:
        detail = _extract_gemini_error_detail(response) or f"HTTP {response.status_code}"
        raise LLMError(
            f"Gemini API error: {detail}",
            {"status_code": response.status_code},
        )

    payload_json = response.json()
    content = _extract_gemini_content(payload_json)
    usage = _extract_gemini_usage(payload_json)
    return content, usage


async def _with_retry(fn: Callable[[], Awaitable[T]], max_attempts: int, label: str) -> T:
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
    details = str(last_err) if last_err else "unknown error"
    raise LLMError(f"{label} failed after {max_attempts} attempts: {details}", {"error": details})


async def _create_chat_completion(**kwargs: Any) -> Any:
    # The OpenAI SDK type surface is stricter than our dynamic payload shape.
    client = _get_openai_client()
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
        if settings.LLM_PROVIDER == "ollama":
            return await _create_ollama_chat_completion(
                messages,
                response_format=response_format,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if settings.LLM_PROVIDER == "gemini":
            return await _create_gemini_chat_completion(
                messages,
                response_format=response_format,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
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
                detail = _extract_openai_error_detail(err)
                raise LLMRateLimitError(max(retry_ms, 1000), detail) from err
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
        parsed = parse_json_object(raw)
    except json.JSONDecodeError as err:
        raise LLMParseError(
            "LLM returned invalid JSON",
            raw,
            {"usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}},
        ) from err
    try:
        return schema.model_validate(parsed), usage
    except ValidationError as err:
        raise LLMParseError(
            f"Schema validation failed: {err}",
            raw,
            {"usage": {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}},
        ) from err


async def chat_stream(
    messages: list[Message],
    on_chunk: OnChunk,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> tuple[str, LLMUsage]:
    settings = get_settings()

    async def _call() -> tuple[str, LLMUsage]:
        if settings.LLM_PROVIDER == "ollama":
            return await _create_ollama_chat_stream(
                messages,
                on_chunk,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if settings.LLM_PROVIDER == "gemini":
            content, usage = await _create_gemini_chat_completion(
                messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if content:
                chunk_size = 120
                for index in range(0, len(content), chunk_size):
                    on_chunk(content[index : index + chunk_size])
            return content, usage

        stream = await _create_chat_completion(
            model=model or settings.LLM_MODEL,
            messages=messages,
            temperature=temperature if temperature is not None else settings.LLM_TEMPERATURE,
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            stream=True,
            stream_options={"include_usage": True},
        )
        content_chunks: list[str] = []
        usage = LLMUsage()
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                content_chunks.append(delta)
                on_chunk(delta)
            if chunk.usage:
                usage = _extract_usage(chunk.usage)
        return "".join(content_chunks), usage

    return await _with_retry(_call, settings.AGENT_LLM_RETRY_ATTEMPTS, "chat_stream")


async def create_embedding(text: str) -> list[float]:
    settings = get_settings()
    if settings.LLM_PROVIDER == "ollama":
        vectors = await _ollama_embed([text])
        return vectors[0] if vectors else []
    if not settings.OPENAI_API_KEY:
        raise LLMError("Embeddings require OPENAI_API_KEY")
    response = await _get_openai_client().embeddings.create(model=settings.EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


async def create_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    if settings.LLM_PROVIDER == "ollama":
        return await _ollama_embed(texts)
    if not settings.OPENAI_API_KEY:
        raise LLMError("Embeddings require OPENAI_API_KEY")
    result: list[list[float]] = []
    batch_size = settings.EMBEDDING_BATCH_SIZE
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await _get_openai_client().embeddings.create(model=settings.EMBEDDING_MODEL, input=batch)
        result.extend(item.embedding for item in response.data)
    return result


def get_langchain_chat_model() -> ChatOpenAI:
    settings = get_settings()
    if settings.LLM_PROVIDER != "openai":
        raise LLMError("LangChain chat model is only supported for LLM_PROVIDER=openai")
    if not settings.OPENAI_API_KEY:
        raise LLMError("OPENAI_API_KEY not configured")
    return ChatOpenAI(
        api_key=SecretStr(settings.OPENAI_API_KEY),
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        model_kwargs={"max_completion_tokens": settings.LLM_MAX_TOKENS},
    )
