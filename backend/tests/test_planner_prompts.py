from app.agent.planner import DECIDE_SYSTEM_PROMPT, PLAN_SYSTEM_PROMPT, _prompt_messages


def test_plan_prompt_is_safe_for_raw_json_examples() -> None:
    tools_text = "web_search: Search web"
    rendered = PLAN_SYSTEM_PROMPT.replace("__TOOLS__", tools_text)
    assert tools_text in rendered
    assert '"analysis": "brief analysis"' in rendered


def test_decide_prompt_is_safe_for_raw_json_examples() -> None:
    tools_text = "web_search: Search web"
    rendered = DECIDE_SYSTEM_PROMPT.replace("__TOOLS__", tools_text)
    assert tools_text in rendered
    assert '"type": "tool_call"' in rendered


def test_prompt_messages_accept_literal_json_braces() -> None:
    system_text = """Respond in JSON:
{
  "analysis": "brief analysis"
}"""
    messages = _prompt_messages(system_text, "Task: hello")
    assert messages[0]["role"] == "system"
    assert '"analysis": "brief analysis"' in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "Task: hello"}
