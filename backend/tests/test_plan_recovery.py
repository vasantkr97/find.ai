from app.agent.planner import _coerce_plan_payload


def test_coerce_plan_payload_recovers_analysis_key() -> None:
    payload = {"\n \"analysis\"": "Recovered", "steps": [{"description": "Step A"}]}
    plan = _coerce_plan_payload(payload)
    assert plan.analysis == "Recovered"
    assert plan.steps[0].description == "Step A"


def test_coerce_plan_payload_from_string_steps() -> None:
    payload = {"analysis": "Test", "steps": ["Do thing", "Finish"]}
    plan = _coerce_plan_payload(payload)
    assert plan.analysis == "Test"
    assert plan.steps[0].description == "Do thing"
    assert plan.steps[1].description == "Finish"
