"""Requesty HTTP contract tests using an injected transport, not live inference."""

import json
from urllib.error import HTTPError, URLError

import pytest

from application.extraction.contracts import ExtractionError, OutcomeUnknown, ProviderRejected
from apps.api.requesty_extraction import ENDPOINT, RequestyProvider, _NoRedirect

MODEL = "test-provider/configured-model"


def response(**overrides):
    return {
        "model": MODEL,
        "choices": [{"finish_reason": "stop", "message": {"content": '{"atoms":[]}'}}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 5, "cost": "0.0002"},
        **overrides,
    }


def install(monkeypatch, body=None, error=None):
    captured = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return body[:limit]

    class Opener:
        def open(self, req, timeout):
            captured.append((req, timeout))
            if error:
                raise error
            return Reply()

    monkeypatch.setattr("apps.api.requesty_extraction.build_opener", lambda *args: Opener())
    return captured


def call(provider):
    return provider.complete("Extract proposals", "Synthetic source", request_id="a" * 64, max_tokens=50)


def test_requesty_only_http_contract_and_real_telemetry(monkeypatch):
    captured = install(monkeypatch, body=json.dumps(response()).encode())
    provider = RequestyProvider(api_key="synthetic-not-a-real-key", model=MODEL)
    reply = call(provider)
    assert reply.provider == provider.identity and reply.model == MODEL
    assert (reply.input_tokens, reply.output_tokens, reply.cost) == (4, 5, "0.0002")
    req, timeout = captured[0]
    assert req.full_url == ENDPOINT and timeout == 60
    assert req.get_header("Authorization") == "Bearer synthetic-not-a-real-key"
    payload = json.loads(req.data)
    assert payload["model"] == MODEL and "tools" not in payload and not payload["stream"]
    assert "fallback" not in payload and len(captured) == 1
    assert "synthetic-not-a-real-key" not in repr(provider)


@pytest.mark.parametrize(
    "model", ["", "policy/automatic", "vertex/disallowed", "http://host", "bare", "a/b\nsecret"]
)
def test_unsupported_provider_route_configuration(model):
    with pytest.raises(ExtractionError):
        RequestyProvider(api_key="synthetic", model=model)


@pytest.mark.parametrize(
    "status,exception",
    [
        (400, ProviderRejected),
        (401, ProviderRejected),
        (429, ProviderRejected),
        (500, OutcomeUnknown),
        (503, OutcomeUnknown),
    ],
)
def test_http_error_no_retry_and_no_raw_error_leak(monkeypatch, status, exception):
    captured = install(monkeypatch, error=HTTPError(ENDPOINT, status, "secret raw provider detail", {}, None))
    with pytest.raises(exception) as error:
        call(RequestyProvider(api_key="synthetic", model=MODEL))
    assert len(captured) == 1 and "secret raw" not in str(error.value)


@pytest.mark.parametrize("error", [TimeoutError("private"), URLError("private"), OSError("private")])
def test_uncertain_transport_is_not_blindly_retried(monkeypatch, error):
    captured = install(monkeypatch, error=error)
    with pytest.raises(OutcomeUnknown):
        call(RequestyProvider(api_key="synthetic", model=MODEL))
    assert len(captured) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        response(model="unexpected/model"),
        response(choices=[{"finish_reason": "length", "message": {"content": "{}"}}]),
        response(
            choices=[{"finish_reason": "stop", "message": {"content": "{}", "tool_calls": [{"id": "x"}]}}]
        ),
        response(usage={"completion_tokens": 100}),
        response(usage={"prompt_tokens": True}),
        response(usage={"cost": "NaN"}),
        response(usage={"cost": "-1"}),
        response(usage={"cost": "not-a-decimal"}),
    ],
)
def test_bad_provider_envelope_is_not_accepted(monkeypatch, body):
    install(monkeypatch, body=json.dumps(body).encode())
    with pytest.raises(ExtractionError):
        call(RequestyProvider(api_key="synthetic", model=MODEL))


def test_no_redirect_can_forward_credentials():
    with pytest.raises(ProviderRejected, match="redirect"):
        _NoRedirect().redirect_request(None, None, 307, "redirect", {}, "https://attacker.invalid")


def test_explicit_requesty_environment_reuses_key_and_paid_model(monkeypatch):
    monkeypatch.delenv("CASEPROOF_REQUESTY_API_KEY", raising=False)
    monkeypatch.delenv("CASEPROOF_EXTRACTION_MODEL", raising=False)
    monkeypatch.setenv("REQUESTY_API_KEY", "synthetic")
    monkeypatch.setenv("REQUESTY_MODEL_PAID", MODEL)
    assert RequestyProvider.from_environment().model == MODEL


def test_no_implicit_model_default(monkeypatch):
    for key in (
        "CASEPROOF_REQUESTY_API_KEY",
        "CASEPROOF_EXTRACTION_MODEL",
        "REQUESTY_API_KEY",
        "REQUESTY_MODEL_PAID",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ExtractionError):
        RequestyProvider.from_environment()
