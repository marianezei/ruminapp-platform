import asyncio
import logging
import os
import random
import time
from collections import Counter as Contagem
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, Field

from . import motor, telemetria

telemetria.configurar_logs()
log = logging.getLogger("reproducao")

DURACAO = Histogram(
    "http_server_request_duration_seconds",
    "Duração das requisições HTTP atendidas.",
    ["http_route", "http_request_method", "http_response_status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
    registry=telemetria.REGISTRO,
)
ANIMAIS = Counter("reproducao_animais_calculados_total", "Animais com status calculado.",
                  registry=telemetria.REGISTRO)
LOTE = Histogram("reproducao_lote_animais", "Animais por requisição de cálculo.",
                 buckets=(1, 5, 10, 25, 50, 100, 250, 500), registry=telemetria.REGISTRO)
ALERTAS = Counter("reproducao_alertas_total", "Alertas reprodutivos emitidos.", ["codigo"],
                  registry=telemetria.REGISTRO)
CATEGORIAS = Counter("reproducao_categorias_total", "Animais calculados por categoria.", ["categoria"],
                     registry=telemetria.REGISTRO)

TAXA_ERRO = float(os.environ.get("CHAOS_ERROR_RATE", "0"))
LATENCIA_EXTRA = float(os.environ.get("CHAOS_LATENCY_MS", "0")) / 1000


class Configuracao(BaseModel):
    periodo_voluntario_espera: int = 50
    duracao_ciclo: int = 21
    retorno_cio_inicio: int = 18
    retorno_cio_fim: int = 24
    dias_diagnostico: int = 30
    dias_gestacao: int = 0
    dias_secagem: int = 60
    dias_pre_parto: int = 21
    idade_minima_novilha: int = 14
    alerta_sem_cio: int = 90
    alerta_repetidora: int = 3
    antecedencia_alertas: int = 7


class Evento(BaseModel):
    id: int | None = None
    tipo: str
    data: date
    resultado: str = ""
    touro_id: int | None = None


class Animal(BaseModel):
    id: int
    raca: str
    data_nascimento: date | None = None
    lactacoes_anteriores: int = 0
    eventos: list[Evento] = Field(default_factory=list)


class Pedido(BaseModel):
    hoje: date
    config: Configuracao = Field(default_factory=Configuracao)
    animais: list[Animal]


@asynccontextmanager
async def ciclo_de_vida(_app):
    telemetria.iniciar_metricas()
    log.info("reproducao pronto", extra={"campos": {"chaos_error_rate": TAXA_ERRO,
                                                     "chaos_latency_ms": LATENCIA_EXTRA * 1000}})
    yield


app = FastAPI(title="reproducao", docs_url=None, redoc_url=None, lifespan=ciclo_de_vida)


@app.middleware("http")
async def medir(request: Request, call_next):
    inicio = time.perf_counter()
    status = 500
    try:
        resposta = await call_next(request)
        status = resposta.status_code
        return resposta
    finally:
        rota = getattr(request.scope.get("route"), "path", "desconhecida")
        if rota not in ("/healthz", "/readyz"):
            duracao = time.perf_counter() - inicio
            trace_id = telemetria.trace_id_atual()
            DURACAO.labels(rota, request.method, str(status)).observe(
                duracao, exemplar={"trace_id": trace_id} if trace_id else None)
            nivel = logging.ERROR if status >= 500 else logging.INFO
            log.log(nivel, "requisição atendida", extra={"campos": {
                "method": request.method, "route": rota, "status": status,
                "duration_ms": round(duracao * 1000, 1)}})


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ok"}


@app.post("/v1/status")
async def calcular_status(pedido: Pedido):
    if LATENCIA_EXTRA:
        await asyncio.sleep(random.uniform(0.5, 1.5) * LATENCIA_EXTRA)
    if TAXA_ERRO and random.random() < TAXA_ERRO:
        log.error("falha injetada", extra={"campos": {"animais": len(pedido.animais)}})
        return JSONResponse({"erro": "falha injetada"}, status_code=503)

    resultado = []
    alertas = Contagem()
    for animal in pedido.animais:
        s = motor.calcular(
            animal.eventos, raca=animal.raca, data_nascimento=animal.data_nascimento,
            config=pedido.config, hoje=pedido.hoje, partos_anteriores=animal.lactacoes_anteriores,
        )
        alertas.update(s.codigos_alerta)
        CATEGORIAS.labels(s.categoria).inc()
        resultado.append({"id": animal.id, **s.__dict__})

    ANIMAIS.inc(len(pedido.animais))
    LOTE.observe(len(pedido.animais))
    for codigo, n in alertas.items():
        ALERTAS.labels(codigo).inc(n)
    return {"status": resultado}


# Instrumentar depois de registrar o middleware acima deixa o OpenTelemetry como camada
# mais externa; assim o span da requisição já está ativo quando métricas e logs são gerados.
telemetria.configurar_traces(app)
