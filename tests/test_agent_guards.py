
from types import SimpleNamespace

import agent
from google.genai import types


def make_response(parts, text=""):
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=types.Content(
                    role="model",
                    parts=parts,
                )
            )
        ],
        text=text,
    )


def make_tool_call():
    return types.FunctionCall(
        name="calculate_air_density",
        args={
            "temperature_c": 30.0,
            "pressure_hpa": 1010.0,
            "relative_humidity_pct": 70.0,
        },
    )


def test_rejected_result_cannot_produce_verified_report(monkeypatch):
    tool_response = make_response(
        [types.Part(function_call=make_tool_call())]
    )

    final_response = make_response(
        [types.Part(text="This is a verified engineering report.")],
        text="This is a verified engineering report.",
    )

    responses = iter([tool_response, final_response])

    monkeypatch.setattr(
        agent.client.models,
        "generate_content",
        lambda **kwargs: next(responses),
    )

    monkeypatch.setattr(
        agent,
        "execute_tool",
        lambda name, arguments: {
            "status": "SUCCESS",
            "moist_air_density_kg_m3": 1.25,
        },
    )

    monkeypatch.setattr(
        agent,
        "validate_engineering_result",
        lambda name, arguments, result: {
            "validation_status": "REJECTED",
            "errors": ["Deliberately corrupted test result."],
        },
    )

    result = agent.run_agent(
        "Calculate and report moist-air density.",
        max_steps=3,
    )

    assert result["status"] == "VALIDATION_REJECTED"
    assert len(result["rejected_validations"]) == 1
    assert result["answer"] != "This is a verified engineering report."
    assert "could not issue a verified" in result["answer"].lower()


def test_successfully_validated_result_can_complete(monkeypatch):
    tool_response = make_response(
        [types.Part(function_call=make_tool_call())]
    )

    final_response = make_response(
        [types.Part(text="Calculation completed and validated.")],
        text="Calculation completed and validated.",
    )

    responses = iter([tool_response, final_response])

    monkeypatch.setattr(
        agent.client.models,
        "generate_content",
        lambda **kwargs: next(responses),
    )

    monkeypatch.setattr(
        agent,
        "execute_tool",
        lambda name, arguments: {
            "status": "SUCCESS",
            "moist_air_density_kg_m3": 1.1486,
        },
    )

    monkeypatch.setattr(
        agent,
        "validate_engineering_result",
        lambda name, arguments, result: {
            "validation_status": "PASSED",
            "errors": [],
        },
    )

    result = agent.run_agent(
        "Calculate moist-air density.",
        max_steps=3,
    )

    assert result["status"] == "COMPLETED"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["validation_status"] == "PASSED"
