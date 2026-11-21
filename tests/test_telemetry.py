from types import SimpleNamespace

from app.core import telemetry


def test_setup_tracing_uses_phoenix_http_endpoint_and_is_idempotent(monkeypatch):
    calls = {"set": 0, "exporter": None, "processor": 0}

    class FakeProvider:
        def __init__(self, resource):
            self.resource = resource

        def add_span_processor(self, processor):
            calls["processor"] += 1

    class FakeExporter:
        def __init__(self, **kwargs):
            calls["exporter"] = kwargs

    class FakeProcessor:
        def __init__(self, exporter, **kwargs):
            self.exporter = exporter

    monkeypatch.setattr(telemetry, "_tracer_provider", None)
    monkeypatch.setattr(telemetry.trace, "get_tracer_provider", lambda: object())
    monkeypatch.setattr(
        telemetry.trace,
        "set_tracer_provider",
        lambda provider: calls.__setitem__("set", calls["set"] + 1),
    )
    monkeypatch.setattr(telemetry, "TracerProvider", FakeProvider)
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", FakeExporter)
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", FakeProcessor)
    monkeypatch.setattr(
        telemetry.Resource,
        "create",
        lambda attributes: attributes,
    )
    monkeypatch.setattr(
        telemetry,
        "get_settings",
        lambda: SimpleNamespace(
            phoenix_endpoint="https://collector.example", phoenix_api_key="test-token"
        ),
    )

    first = telemetry.setup_tracing()
    second = telemetry.setup_tracing()

    assert first is second
    assert calls["set"] == 1
    assert calls["processor"] == 1
    assert calls["exporter"]["endpoint"] == ("https://collector.example/v1/traces")
    assert calls["exporter"]["headers"] == {"authorization": "Bearer test-token"}


def test_tracing_setup_survives_exporter_construction_failure(monkeypatch):
    installed = []

    class FakeProvider:
        def __init__(self, resource):
            pass

        def add_span_processor(self, processor):
            raise AssertionError("No processor should be added after failure")

    def fail_exporter(**kwargs):
        raise RuntimeError("collector unavailable")

    monkeypatch.setattr(telemetry, "_tracer_provider", None)
    monkeypatch.setattr(telemetry.trace, "get_tracer_provider", lambda: object())
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", installed.append)
    monkeypatch.setattr(telemetry, "TracerProvider", FakeProvider)
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", fail_exporter)
    monkeypatch.setattr(telemetry.Resource, "create", lambda attributes: attributes)
    monkeypatch.setattr(
        telemetry,
        "get_settings",
        lambda: SimpleNamespace(
            phoenix_endpoint="https://collector.example", phoenix_api_key=""
        ),
    )

    provider = telemetry.setup_tracing()

    assert provider is installed[0]
