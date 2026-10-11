import logging
import time

from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from prometheus_client import Histogram

from rebanho.reproducao import ReproducaoIndisponivel

from . import telemetria

log = logging.getLogger("ruminapp.http")

DURACAO = Histogram(
    "http_server_request_duration_seconds",
    "Duração das requisições HTTP atendidas.",
    ["http_route", "http_request_method", "http_response_status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)


class SaudeMiddleware:
    """Responde às sondas do kubelet antes da validação de host e da autenticação."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            return HttpResponse("ok", content_type="text/plain")
        if request.path == "/readyz":
            try:
                connection.ensure_connection()
            except Exception as erro:
                return JsonResponse({"status": "erro", "banco": str(erro)}, status=503)
            return JsonResponse({"status": "ok"})
        return self.get_response(request)


class MetricasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inicio = time.perf_counter()
        resposta = self.get_response(request)
        if request.path.startswith("/static/"):
            return resposta
        duracao = time.perf_counter() - inicio
        rota = request.resolver_match.view_name if request.resolver_match else "nao_encontrada"
        trace_id = telemetria.trace_id_atual()
        DURACAO.labels(rota, request.method, str(resposta.status_code)).observe(
            duracao, exemplar={"trace_id": trace_id} if trace_id else None)
        nivel = logging.ERROR if resposta.status_code >= 500 else logging.INFO
        log.log(nivel, "requisição atendida", extra={"campos": {
            "method": request.method, "route": rota, "path": request.path,
            "status": resposta.status_code, "duration_ms": round(duracao * 1000, 1),
            "user": getattr(getattr(request, "user", None), "username", None) or None,
        }})
        return resposta

    def process_exception(self, request, exception):
        if isinstance(exception, ReproducaoIndisponivel):
            return render(request, "rebanho/indisponivel.html", status=503)
        return None
