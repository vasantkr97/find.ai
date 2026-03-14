from app.services.llm import parse_json_object


def test_parse_json_object_from_code_fence() -> None:
    raw = "```json\n{\"analysis\":\"ok\",\"steps\":[]}\n```"
    assert parse_json_object(raw) == {"analysis": "ok", "steps": []}


def test_parse_json_object_from_embedded_text() -> None:
    raw = "Here is the plan:\\n{\"analysis\":\"ok\",\"steps\":[]}\\nThanks."
    assert parse_json_object(raw) == {"analysis": "ok", "steps": []}


def test_parse_json_object_from_stringified_json() -> None:
    raw = "\"{\\\"analysis\\\":\\\"ok\\\",\\\"steps\\\":[]}\""
    assert parse_json_object(raw) == {"analysis": "ok", "steps": []}
