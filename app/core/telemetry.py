from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from app.core.config import get_settings


def setup_tracing():

    # Create the tracing provider
    resource = Resource.create(
        {
            "service.name": "taskflow",
            "openinference.project.name": "taskflow",
        }
    )

    provider = TracerProvider(resource=resource)

    endpoint = get_settings().phoenix_endpoint.strip()
    if endpoint:
        trace_endpoint = (
            endpoint
            if endpoint.endswith("/v1/traces")
            else f"{endpoint.rstrip('/')}/v1/traces"
        )
        provider.add_span_processor(
            SimpleSpanProcessor(OTLPSpanExporter(endpoint=trace_endpoint))
        )

    # Activate the provider globally
    trace.set_tracer_provider(provider)
