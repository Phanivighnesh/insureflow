"""Tests for LLM providers (FakeProvider and GroqProvider error handling)."""
import httpx
from app.ai.providers import FakeProvider, GroqProvider, ProviderError, ProviderResult


def test_fake_provider_success():
    fake = FakeProvider(response_json='{"summary": "Test summary", "key_findings": ["F1"]}')
    assert fake.is_available is True
    res = fake.generate([{"role": "user", "content": "Hello"}])
    assert isinstance(res, ProviderResult)
    assert "Test summary" in res.content
    assert len(fake.calls) == 1


def test_fake_provider_error():
    fake = FakeProvider(error=ProviderError("timeout", "Simulated timeout"))
    res = fake.generate([{"role": "user", "content": "Hello"}])
    assert isinstance(res, ProviderError)
    assert res.code == "timeout"


def test_groq_provider_error_handling_401():
    transport = httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "Invalid API key"}))
    provider = GroqProvider(api_key="bad-key", model="test-model", transport=transport)
    res = provider.generate([{"role": "user", "content": "Hello"}])
    assert isinstance(res, ProviderError)
    assert res.code == "auth"
    assert provider.is_available is False


def test_groq_provider_error_handling_timeout():
    def raise_timeout(req):
        raise httpx.TimeoutException("Timeout")

    transport = httpx.MockTransport(raise_timeout)
    provider = GroqProvider(api_key="key", model="test-model", transport=transport)
    res = provider.generate([{"role": "user", "content": "Hello"}])
    assert isinstance(res, ProviderError)
    assert res.code == "timeout"


def test_groq_provider_retries_on_500():
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(500, json={"error": "Server error"})

    transport = httpx.MockTransport(handle)
    provider = GroqProvider(api_key="key", model="test-model", transport=transport)
    res = provider.generate([{"role": "user", "content": "Hello"}])
    assert isinstance(res, ProviderError)
    assert res.code == "server_error"
    # Proves it retried once
    assert len(calls) == 2

