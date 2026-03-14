from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppError(Exception):
    message: str
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class LLMError(AppError):
    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="LLM_ERROR", status_code=502, context=context or {})


class LLMRateLimitError(LLMError):
    def __init__(self, retry_after_ms: int, detail: str | None = None) -> None:
        message = "LLM rate limit exceeded"
        if detail:
            message = f"{message}: {detail}"
        context: dict[str, Any] = {"retry_after_ms": retry_after_ms}
        if detail:
            context["detail"] = detail
        super().__init__(message, context)
        self.retry_after_ms = retry_after_ms


class LLMParseError(LLMError):
    def __init__(self, message: str, raw_output: str, context: dict[str, Any] | None = None) -> None:
        self.raw_output = raw_output
        payload = {"raw_output": raw_output[:2000]}
        if context:
            payload.update(context)
        super().__init__(message, payload)


class ToolError(AppError):
    def __init__(self, tool_name: str, message: str) -> None:
        super().__init__(
            message=message,
            code="TOOL_ERROR",
            status_code=502,
            context={"tool_name": tool_name},
        )
        self.tool_name = tool_name


class ToolNotFoundError(ToolError):
    def __init__(self, tool_name: str, available_tools: list[str]) -> None:
        super().__init__(tool_name, f"Unknown tool: {tool_name}. Available: {', '.join(available_tools)}")


class ToolTimeoutError(ToolError):
    def __init__(self, tool_name: str, timeout_ms: int) -> None:
        super().__init__(tool_name, f"Tool '{tool_name}' timed out after {timeout_ms}ms")


class ToolValidationError(ToolError):
    def __init__(self, tool_name: str, details: str) -> None:
        super().__init__(tool_name, f"Validation failed for '{tool_name}': {details}")


class DriveAuthError(AppError):
    def __init__(self, message: str = "Google Drive is not connected") -> None:
        super().__init__(message=message, code="DRIVE_AUTH_ERROR", status_code=401)


class DriveError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="DRIVE_ERROR", status_code=502)


class VectorStoreError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VECTOR_STORE_ERROR", status_code=500)


class AgentAbortedError(AppError):
    def __init__(self) -> None:
        super().__init__(message="Agent execution was aborted", code="AGENT_ABORTED", status_code=499)


def to_error_message(err: Exception | BaseException | str | object) -> str:
    if isinstance(err, BaseException):
        return str(err)
    if isinstance(err, str):
        return err
    return "Unknown error"
