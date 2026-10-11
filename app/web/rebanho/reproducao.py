"""
Cliente do serviço de reprodução.

As regras ficam no serviço `reproducao`. Aqui o status calculado vira um objeto com os
rótulos usados nas telas, e são montadas as listas de ação do dia e os indicadores.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from datetime import date, timedelta

import requests
from django.conf import settings
from prometheus_client import Counter
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

FALHAS = Counter("ruminapp_reproducao_falhas_total", "Chamadas ao serviço de reprodução que falharam.")

MARGEM_CIO = 3

CAMPOS_CONFIG = (
    "periodo_voluntario_espera", "duracao_ciclo", "retorno_cio_inicio", "retorno_cio_fim",
    "dias_diagnostico", "dias_gestacao", "dias_secagem", "dias_pre_parto", "idade_minima_novilha",
    "alerta_sem_cio", "alerta_repetidora", "antecedencia_alertas",
)


class ReproducaoIndisponivel(Exception):
    pass


@dataclass
class Status:
    categoria: str = "NOVILHA"
    situacao: str = "VAZIA"
    n_partos: int = 0
    partos: list = field(default_factory=list)
    ultimo_parto: date | None = None
    ultimo_cio: date | None = None
    ultima_ia: date | None = None
    touro_ultima_ia: object = None
    ias_no_ciclo: int = 0
    data_concepcao: date | None = None
    data_secagem_real: date | None = None
    data_baixa: date | None = None
    motivo_baixa: str = ""
    ias_por_concepcao: list = field(default_factory=list)
    dias_situacao: int | None = None
    inicio_situacao: date | None = None
    del_dias: int | None = None
    idade_meses: int | None = None
    dias_gestacao: int | None = None
    apta_ia: bool = False
    liberacao_ia: date | None = None
    proximo_cio: date | None = None
    cio_estimado: bool = False
    retorno_inicio: date | None = None
    retorno_fim: date | None = None
    data_diagnostico: date | None = None
    previsao_parto: date | None = None
    data_secar: date | None = None
    data_pre_parto: date | None = None
    alertas: list = field(default_factory=list)

    @classmethod
    def do_json(cls, dados: dict, touros: dict) -> "Status":
        valores = {}
        for f in fields(cls):
            valor = dados.get(f.name)
            if isinstance(valor, str) and f.type == "date | None":
                valor = date.fromisoformat(valor)
            valores[f.name] = valor
        valores["partos"] = [date.fromisoformat(d) for d in dados.get("partos", [])]
        valores["ias_por_concepcao"] = dados.get("ias_por_concepcao", [])
        valores["alertas"] = dados.get("alertas", [])
        valores["touro_ultima_ia"] = touros.get(dados.get("touro_ultima_ia"))
        return cls(**valores)

    @property
    def categoria_label(self):
        return {
            "BEZERRA": "Bezerra", "NOVILHA": "Novilha", "LACTACAO": "Em lactação",
            "SECA": "Seca", "BAIXA": "Baixada",
        }[self.categoria]

    @property
    def rotulo_dias(self):
        """O que a contagem de dias significa para este animal."""
        if self.categoria == "SECA":
            return "Seca há"
        if self.situacao == "PRENHE":
            return "Prenhe há"
        if self.situacao == "INSEMINADA":
            return "Inseminada há"
        if self.ultimo_parto:
            return "Vazia há"
        return "Idade"

    @property
    def situacao_label(self):
        return {"VAZIA": "Vazia", "INSEMINADA": "Inseminada", "PRENHE": "Prenhe"}[self.situacao]


_sessao_http = None


def _sessao():
    global _sessao_http
    if _sessao_http is None:
        _sessao_http = requests.Session()
        tentativas = Retry(total=2, backoff_factor=0.1, status_forcelist=(502, 503, 504),
                           allowed_methods=None)
        _sessao_http.mount("http://", HTTPAdapter(max_retries=tentativas))
    return _sessao_http


def _evento_json(e):
    return {"id": e.id, "tipo": e.tipo, "data": e.data.isoformat(), "resultado": e.resultado or "",
            "touro_id": e.touro_id}


def calcular_lote(animais, *, config, hoje: date, ate: date | None = None) -> dict:
    """Calcula o status de vários animais numa única chamada. Devolve {animal.pk: Status}."""
    touros = {}
    corpo = []
    for a in animais:
        eventos = list(a.eventos.all())
        if ate:
            eventos = [e for e in eventos if e.data <= ate]
        for e in eventos:
            if e.touro_id:
                touros[e.touro_id] = e.touro
        corpo.append({
            "id": a.pk or 0, "raca": a.raca, "lactacoes_anteriores": a.lactacoes_anteriores,
            "data_nascimento": a.data_nascimento.isoformat() if a.data_nascimento else None,
            "eventos": [_evento_json(e) for e in eventos],
        })
    if not corpo:
        return {}
    pedido = {
        "hoje": hoje.isoformat(),
        "config": {c: getattr(config, c) for c in CAMPOS_CONFIG},
        "animais": corpo,
    }
    try:
        resposta = _sessao().post(f"{settings.REPRODUCAO_URL}/v1/status", json=pedido,
                                  timeout=settings.REPRODUCAO_TIMEOUT)
        resposta.raise_for_status()
    except Exception as erro:
        FALHAS.inc()
        log.error("serviço de reprodução indisponível", extra={"campos": {"erro": str(erro)}})
        raise ReproducaoIndisponivel(str(erro)) from erro
    return {d["id"]: Status.do_json(d, touros) for d in resposta.json()["status"]}


def calcular_status(animal, *, config=None, hoje: date | None = None, ate: date | None = None) -> Status:
    """Status de um Animal do banco. `ate` limita aos eventos até essa data (inclusive)."""
    from .models import ConfiguracaoReprodutiva

    config = config or ConfiguracaoReprodutiva.atual()
    hoje = hoje or date.today()
    return calcular_lote([animal], config=config, hoje=hoje, ate=ate)[animal.pk or 0]


# --------------------------------------------------------------------------
# Listas de ação do dia
# --------------------------------------------------------------------------

@dataclass
class ItemLista:
    animal: object
    status: Status
    data: date | None
    detalhe: str


@dataclass
class ListaAcao:
    chave: str
    titulo: str
    descricao: str
    tom: str                  # "acao", "atencao", "info", "problema"
    itens: list = field(default_factory=list)


def _fmt(d: date) -> str:
    return d.strftime("%d/%m")


def gerar_listas(animais, config, hoje: date) -> list[ListaAcao]:
    """`animais` precisa ter o status já calculado (animal.status)."""
    ant = timedelta(days=config.antecedencia_alertas)

    observar_cio = ListaAcao(
        "cio", "Observar cio",
        f"Cio previsto entre {_fmt(hoje - timedelta(days=MARGEM_CIO))} e {_fmt(hoje + timedelta(days=3))}, "
        "com base no último cio ou IA.", "acao")
    retorno = ListaAcao(
        "retorno", "Observar retorno ao cio",
        f"Inseminadas há {config.retorno_cio_inicio} a {config.retorno_cio_fim} dias. "
        "Se entrarem em cio, não emprenharam.", "acao")
    diagnostico = ListaAcao(
        "dg", "Fazer diagnóstico de gestação",
        f"Inseminadas há {config.dias_diagnostico} dias ou mais, sem diagnóstico.", "acao")
    aptas = ListaAcao(
        "aptas", "Vazias liberadas para inseminar",
        f"Já passaram do período de espera ({config.periodo_voluntario_espera} dias pós-parto) "
        "ou novilhas com idade mínima.", "info")
    secar = ListaAcao(
        "secar", "Secar",
        f"Secagem prevista até {_fmt(hoje + ant)} ({config.dias_secagem} dias antes do parto).", "atencao")
    pre_parto = ListaAcao(
        "preparto", "Levar para o pré-parto",
        f"Entram no pré-parto até {_fmt(hoje + ant)} ({config.dias_pre_parto} dias antes do parto).", "atencao")
    partos = ListaAcao(
        "partos", "Partos previstos (30 dias)", "Vacas e novilhas prenhes com parto nos próximos 30 dias.", "info")
    problemas = ListaAcao(
        "problemas", "Problemas reprodutivos",
        "Vacas sem cio, repetidoras, diagnósticos atrasados e outras pendências.", "problema")

    for a in animais:
        s = a.status
        if s.categoria == "BAIXA":
            continue

        if s.situacao == "VAZIA" and s.apta_ia:
            detalhe = f"{s.del_dias} DEL" if s.del_dias is not None else f"{s.idade_meses or '?'} meses"
            if s.ias_no_ciclo:
                detalhe += f" · {s.ias_no_ciclo} IA(s)"
            aptas.itens.append(ItemLista(a, s, s.proximo_cio, detalhe))
            if s.proximo_cio and hoje - timedelta(days=MARGEM_CIO) <= s.proximo_cio <= hoje + timedelta(days=3):
                d = "estimado" if s.cio_estimado else f"último cio {_fmt(s.ultimo_cio)}"
                observar_cio.itens.append(ItemLista(a, s, s.proximo_cio, d))

        if s.situacao == "INSEMINADA":
            if s.retorno_inicio <= hoje <= s.retorno_fim:
                dias = (hoje - s.ultima_ia).days
                retorno.itens.append(ItemLista(a, s, s.retorno_fim, f"IA há {dias} dias"))
            if hoje >= s.data_diagnostico:
                dias = (hoje - s.ultima_ia).days
                diagnostico.itens.append(ItemLista(a, s, s.data_diagnostico, f"IA há {dias} dias"))

        if s.situacao == "PRENHE" and s.previsao_parto:
            if s.categoria == "LACTACAO" and s.data_secar <= hoje + ant:
                secar.itens.append(ItemLista(a, s, s.data_secar, f"parto {_fmt(s.previsao_parto)}"))
            if s.data_pre_parto <= hoje + ant and s.previsao_parto >= hoje - timedelta(days=10):
                pre_parto.itens.append(ItemLista(a, s, s.data_pre_parto, f"parto {_fmt(s.previsao_parto)}"))
            if s.previsao_parto <= hoje + timedelta(days=30):
                partos.itens.append(ItemLista(a, s, s.previsao_parto, f"{s.dias_gestacao} dias de gestação"))

        for alerta in s.alertas:
            problemas.itens.append(ItemLista(a, s, None, alerta))

    listas = [observar_cio, retorno, diagnostico, secar, pre_parto, partos, aptas, problemas]
    for lista in listas:
        lista.itens.sort(key=lambda i: (i.data or date.max, i.animal.brinco))
    return listas


# --------------------------------------------------------------------------
# Indicadores do rebanho
# --------------------------------------------------------------------------

def indicadores(animais, hoje: date) -> dict:
    ativos = [a for a in animais if a.status.categoria != "BAIXA"]
    lact = [a for a in ativos if a.status.categoria == "LACTACAO"]
    secas = [a for a in ativos if a.status.categoria == "SECA"]
    vacas = lact + secas
    prenhes = [a for a in vacas if a.status.situacao == "PRENHE"]

    intervalos = []
    ias_conc = []
    for a in animais:
        p = a.status.partos
        intervalos += [(p[i] - p[i - 1]).days for i in range(1, len(p))]
        ias_conc += a.status.ias_por_concepcao

    def media(v):
        return round(sum(v) / len(v), 1) if v else None

    return {
        "ativos": len(ativos),
        "lactacao": len(lact),
        "secas": len(secas),
        "novilhas": sum(1 for a in ativos if a.status.categoria == "NOVILHA"),
        "bezerras": sum(1 for a in ativos if a.status.categoria == "BEZERRA"),
        "pct_prenhes": round(100 * len(prenhes) / len(vacas)) if vacas else None,
        "del_medio": media([a.status.del_dias for a in lact]),
        "iep_medio_meses": round(media(intervalos) / 30.4, 1) if intervalos else None,
        "servicos_por_concepcao": media(ias_conc),
        "concepcao_1a_ia": round(100 * sum(1 for n in ias_conc if n == 1) / len(ias_conc)) if ias_conc else None,
    }
