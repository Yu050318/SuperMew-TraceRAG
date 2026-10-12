from types import SimpleNamespace

import pytest
import httpx
from openai import BadRequestError
from pydantic import BaseModel, ValidationError

from backend.agent.models import ModelRegistry
from backend.core.settings import ModelSettings
from backend.model_control import (
    ModelRole,
    ModelRuntimeSpec,
    build_model_catalog_snapshot,
)


class Decision(BaseModel):
    ok: bool


PROFILE_ID = "model_" + "1" * 32


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline test must never access network")

    monkeypatch.setattr(httpx.Client, "send", forbidden)


def registry_and_snapshot(role, *, selected=True, version=1):
    settings = SimpleNamespace(
        models=ModelSettings(
            _env_file=None,
            ARK_API_KEY="offline-key",
            MODEL="unrelated-model",
            MODEL_STRUCTURED_OUTPUT_POLICIES=(
                {PROFILE_ID + ":1": "deepseek_function_calling"} if selected else {}
            ),
        )
    )
    snapshot = build_model_catalog_snapshot(
        {
            role: ModelRuntimeSpec(
                profile_id=PROFILE_ID,
                profile_version=version,
                display_name="explicit profile",
                model_name="not-name-detected",
                timeout_seconds=30,
                supports_stream=True,
                supports_structured_output=True,
            )
        }
    )
    return ModelRegistry(settings=settings), snapshot


class Completions:
    def __init__(self, arguments='{"ok": true}', error=None, no_tool=False):
        self.requests = []
        self.arguments = arguments
        self.error = error
        self.no_tool = no_tool
        self.with_raw_response = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        message = {"role": "assistant", "content": "OK"}
        if "tools" in kwargs and not self.no_tool:
            message["tool_calls"] = [
                {
                    "id": "call_test",
                    "type": "function",
                    "function": {
                        "name": "Decision",
                        "arguments": self.arguments,
                    },
                }
            ]
        response = {
            "id": "offline",
            "model": "offline",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": message,
                }
            ],
        }
        return SimpleNamespace(parse=lambda: response, headers={})


@pytest.mark.parametrize(
    "role", [ModelRole.FAST, ModelRole.GRADER, ModelRole.EVALUATOR]
)
def test_selected_profile_uses_function_calling_and_validates_schema(role):
    registry, snapshot = registry_and_snapshot(role)
    model = registry.get(role, snapshot=snapshot)
    completions = Completions()
    model.client = completions
    result = model.with_structured_output(Decision).invoke("Decide")
    assert isinstance(result, Decision) and result.ok is True
    request = completions.requests[0]
    assert request["tools"][0]["function"]["parameters"]["required"] == ["ok"]
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "response_format" not in request
    assert model.extra_body is None
    assert model.root_client.max_retries == 0


def test_plain_call_keeps_thinking_behavior_after_structured_call():
    registry, snapshot = registry_and_snapshot(ModelRole.FAST)
    model = registry.get(ModelRole.FAST, snapshot=snapshot)
    completions = Completions()
    model.client = completions
    model.with_structured_output(Decision).invoke("Decide")
    assert model.invoke("Chat").content == "OK"
    assert "extra_body" not in completions.requests[-1]
    assert "tools" not in completions.requests[-1]


@pytest.mark.parametrize("selected,version", [(False, 1), (True, 2)])
def test_unselected_or_new_profile_version_keeps_native_json_schema(selected, version):
    registry, snapshot = registry_and_snapshot(
        ModelRole.GRADER, selected=selected, version=version
    )
    model = registry.get(ModelRole.GRADER, snapshot=snapshot)
    runnable = model.with_structured_output(Decision)
    bound = runnable.steps[0]
    assert bound.kwargs["response_format"] is Decision
    assert "extra_body" not in bound.kwargs
    assert type(model).__name__ == "ChatOpenAI"


@pytest.mark.parametrize("arguments", ['{"ok": "not-a-bool"}', "{}"])
def test_invalid_schema_is_not_replaced_by_default(arguments):
    registry, snapshot = registry_and_snapshot(ModelRole.EVALUATOR)
    model = registry.get(ModelRole.EVALUATOR, snapshot=snapshot)
    model.client = Completions(arguments=arguments)
    with pytest.raises(ValidationError):
        model.with_structured_output(Decision).invoke("Decide")


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("offline provider failure"),
        BadRequestError(
            "offline provider failure",
            response=httpx.Response(
                400, request=httpx.Request("POST", "https://offline.test")
            ),
            body=None,
        ),
    ],
)
def test_provider_exception_propagates_without_retry_or_default(error):
    registry, snapshot = registry_and_snapshot(ModelRole.FAST)
    model = registry.get(ModelRole.FAST, snapshot=snapshot)
    completions = Completions(error=error)
    model.client = completions
    with pytest.raises(type(error), match="offline provider failure"):
        model.with_structured_output(Decision).invoke("Decide")
    assert len(completions.requests) == 1


def test_missing_tool_result_fails_closed():
    registry, snapshot = registry_and_snapshot(ModelRole.GRADER)
    model = registry.get(ModelRole.GRADER, snapshot=snapshot)
    model.client = Completions(no_tool=True)
    with pytest.raises(ValueError, match="structured output"):
        model.with_structured_output(Decision).invoke("Decide")


def test_policy_rejects_model_name_and_unversioned_identity():
    for key in ("deepseek-flash", PROFILE_ID, PROFILE_ID + ":0"):
        with pytest.raises(ValidationError):
            ModelSettings(
                _env_file=None,
                MODEL_STRUCTURED_OUTPUT_POLICIES={key: "deepseek_function_calling"},
            )


def test_include_raw_does_not_silently_suppress_invalid_schema():
    registry, snapshot = registry_and_snapshot(ModelRole.GRADER)
    model = registry.get(ModelRole.GRADER, snapshot=snapshot)
    model.client = Completions(arguments="{}")
    with pytest.raises(ValidationError):
        model.with_structured_output(Decision, include_raw=True).invoke("Decide")
