import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_tracer_provider: TracerProvider | None = None


def setup_tracing() -> TracerProvider:
    global _tracer_provider
    if _tracer_provider is not None:
        return _tracer_provider

    current_provider = trace.get_tracer_provider()
    if isinstance(current_provider, TracerProvider):
        _tracer_provider = current_provider
        return current_provider

    settings = get_settings()
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "taskflow",
                "openinference.project.name": "taskflow",
            }
        )
    )

    endpoint = settings.phoenix_endpoint.strip()
    if endpoint:
        trace_endpoint = (
            endpoint
            if endpoint.endswith("/v1/traces")
            else f"{endpoint.rstrip('/')}/v1/traces"
        )
        try:
            headers = (
                {"authorization": f"Bearer {settings.phoenix_api_key}"}
                if settings.phoenix_api_key
                else None
            )
            exporter = OTLPSpanExporter(
                endpoint=trace_endpoint,
                headers=headers,
                timeout=5,
            )
            provider.add_span_processor(
                BatchSpanProcessor(
                    exporter,
                    max_queue_size=256,
                    max_export_batch_size=128,
                    schedule_delay_millis=1000,
                    export_timeout_millis=5000,
                )
            )
        except Exception as error:
            logger.warning(
                "Phoenix tracing disabled during setup: %s", type(error).__name__
            )

    try:
        trace.set_tracer_provider(provider)
        _tracer_provider = provider
    except Exception as error:
        logger.warning("OpenTelemetry provider setup failed: %s", type(error).__name__)
        current_provider = trace.get_tracer_provider()
        if isinstance(current_provider, TracerProvider):
            _tracer_provider = current_provider
            return current_provider
        return provider
    return provider
