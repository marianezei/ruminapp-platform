import json
import logging
import os
import sys
from datetime import datetime, timezone

from opentelemetry import trace
from prometheus_client import (CollectorRegistry, GCCollector, PlatformCollector, ProcessCollector,
                               start_http_server)

SERVICO = os.environ.get("OTEL_SERVICE_NAME", "reproducao")

REGISTRO = CollectorRegistry()
ProcessCollector(registry=REGISTRO)
PlatformCollector(registry=REGISTRO)
GCCollector(registry=REGISTRO)


class FormatoJson(logging.Formatter):
    def format(self, record):
        registro = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
            "service": SERVICO,
        }
        contexto = trace.get_current_span().get_span_context()
        if contexto.is_valid:
            registro["trace_id"] = format(contexto.trace_id, "032x")
            registro["span_id"] = format(contexto.span_id, "016x")
        registro.update(getattr(record, "campos", {}))
        if record.exc_info:
            registro["exception"] = self.formatException(record.exc_info)
        return json.dumps(registro, ensure_ascii=False, default=str)


def configurar_logs():
    saida = logging.StreamHandler(sys.stdout)
    saida.setFormatter(FormatoJson())
    raiz = logging.getLogger()
    raiz.handlers = [saida]
    raiz.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    for nome in ("uvicorn", "uvicorn.error"):
        logging.getLogger(nome).handlers = []
        logging.getLogger(nome).propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def configurar_traces(app):
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provedor = TracerProvider(resource=Resource.create())
    provedor.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provedor)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz")


def iniciar_metricas():
    porta = int(os.environ.get("METRICS_PORT", "9464"))
    if porta:
        start_http_server(porta, registry=REGISTRO)


def trace_id_atual():
    contexto = trace.get_current_span().get_span_context()
    return format(contexto.trace_id, "032x") if contexto.is_valid and contexto.trace_flags.sampled else None
