"""
Motor de regras reprodutivas.

Nada aqui é gravado: o status de cada vaca é recalculado a partir da sequência de
eventos (parto, cio, IA, diagnóstico...). Se um evento for corrigido ou apagado,
todas as previsões se ajustam sozinhas.
"""
from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

# Duração média da gestação por raça (dias).
GESTACAO_POR_RACA = {
    "HOL": 280,
    "JER": 279,
    "PS": 290,
    "GIROL": 285,
    "GIR": 290,
    "OUT": 283,
}
GESTACAO_PADRAO = 283

# Quantos dias de atraso ainda mostramos um cio previsto como "para observar".
MARGEM_CIO = 3


def somar_meses(d: date, meses: int) -> date:
    mes = d.month - 1 + meses
    ano = d.year + mes // 12
    mes = mes % 12 + 1
    dia = min(d.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


@dataclass
class Status:
    categoria: str = "NOVILHA"          # BEZERRA, NOVILHA, LACTACAO, SECA, BAIXA
    situacao: str = "VAZIA"             # VAZIA, INSEMINADA, PRENHE
    n_partos: int = 0
    partos: list = field(default_factory=list)
    ultimo_parto: date | None = None
    ultimo_cio: date | None = None
    ultima_ia: date | None = None
    touro_ultima_ia: int | None = None
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
    codigos_alerta: list = field(default_factory=list)

    def alertar(self, codigo: str, mensagem: str):
        self.codigos_alerta.append(codigo)
        self.alertas.append(mensagem)


def _aplicar_eventos(status: Status, eventos) -> Status:
    for ev in sorted(eventos, key=lambda e: (e.data, e.id or 0)):
        t = ev.tipo
        if t == "PARTO":
            status.n_partos += 1
            status.partos.append(ev.data)
            status.ultimo_parto = ev.data
            status.situacao = "VAZIA"
            status.ultimo_cio = None
            status.ultima_ia = None
            status.touro_ultima_ia = None
            status.ias_no_ciclo = 0
            status.data_concepcao = None
            status.data_secagem_real = None
        elif t == "CIO":
            status.ultimo_cio = ev.data
            # Cio depois de uma IA = a vaca retornou, não emprenhou
            if status.situacao == "INSEMINADA":
                status.situacao = "VAZIA"
        elif t == "IA":
            status.ultima_ia = ev.data
            status.ultimo_cio = ev.data
            status.touro_ultima_ia = getattr(ev, "touro_id", None)
            status.ias_no_ciclo += 1
            status.situacao = "INSEMINADA"
        elif t == "DG":
            if ev.resultado == "POS":
                status.situacao = "PRENHE"
                status.data_concepcao = status.ultima_ia
                if status.ias_no_ciclo:
                    status.ias_por_concepcao.append(status.ias_no_ciclo)
            else:
                status.situacao = "VAZIA"
        elif t == "ABORTO":
            status.situacao = "VAZIA"
            status.data_concepcao = None
        elif t == "SECAGEM":
            status.data_secagem_real = ev.data
        elif t in ("VENDA", "MORTE"):
            status.data_baixa = ev.data
            status.motivo_baixa = "Vendida" if t == "VENDA" else "Morta"
    return status


def calcular(eventos, *, raca: str, data_nascimento: date | None, config, hoje: date,
             partos_anteriores: int = 0) -> Status:
    """`partos_anteriores` são lactações que aconteceram antes de o animal entrar no sistema.
    Contam para o número da lactação, mas não geram eventos."""
    s = _aplicar_eventos(Status(), eventos)
    s.n_partos += partos_anteriores

    if data_nascimento:
        s.idade_meses = (hoje.year - data_nascimento.year) * 12 + (hoje.month - data_nascimento.month)
        if hoje.day < data_nascimento.day:
            s.idade_meses -= 1

    if s.data_baixa:
        s.categoria = "BAIXA"
        return s
    if s.ultimo_parto is None:
        if s.idade_meses is not None and s.idade_meses < 12:
            s.categoria = "BEZERRA"
        else:
            s.categoria = "NOVILHA"
    elif s.data_secagem_real:
        s.categoria = "SECA"
    else:
        s.categoria = "LACTACAO"
        s.del_dias = (hoje - s.ultimo_parto).days

    if s.ultimo_parto:
        s.liberacao_ia = s.ultimo_parto + timedelta(days=config.periodo_voluntario_espera)
    elif data_nascimento:
        s.liberacao_ia = somar_meses(data_nascimento, config.idade_minima_novilha)

    if s.situacao == "VAZIA":
        if s.categoria in ("LACTACAO", "NOVILHA"):
            s.apta_ia = s.liberacao_ia is None or hoje >= s.liberacao_ia
        if s.ultimo_cio:
            ciclo = config.duracao_ciclo
            atraso = (hoje - timedelta(days=MARGEM_CIO) - s.ultimo_cio).days
            k = max(1, math.ceil(atraso / ciclo)) if atraso > 0 else 1
            s.proximo_cio = s.ultimo_cio + timedelta(days=k * ciclo)
            s.cio_estimado = k > 1

    elif s.situacao == "INSEMINADA":
        s.retorno_inicio = s.ultima_ia + timedelta(days=config.retorno_cio_inicio)
        s.retorno_fim = s.ultima_ia + timedelta(days=config.retorno_cio_fim)
        s.data_diagnostico = s.ultima_ia + timedelta(days=config.dias_diagnostico)

    elif s.situacao == "PRENHE" and s.data_concepcao:
        gestacao = config.dias_gestacao or GESTACAO_POR_RACA.get(raca, GESTACAO_PADRAO)
        s.dias_gestacao = (hoje - s.data_concepcao).days
        s.previsao_parto = s.data_concepcao + timedelta(days=gestacao)
        s.data_secar = s.previsao_parto - timedelta(days=config.dias_secagem)
        s.data_pre_parto = s.previsao_parto - timedelta(days=config.dias_pre_parto)

    # Dias no estado atual: é o que a coluna "Dias" mostra na lista de animais.
    if s.categoria == "SECA":
        inicio = s.data_secagem_real
    elif s.situacao == "PRENHE":
        inicio = s.data_concepcao
    elif s.situacao == "INSEMINADA":
        inicio = s.ultima_ia
    else:
        # Vaca vazia: dias em aberto desde o parto. Novilha que nunca pariu: idade.
        inicio = s.ultimo_parto or data_nascimento
    if inicio:
        s.dias_situacao = (hoje - inicio).days
        s.inicio_situacao = inicio

    if s.categoria == "LACTACAO" and s.situacao == "VAZIA" and s.ultimo_cio is None \
            and s.del_dias > config.alerta_sem_cio:
        s.alertar("sem_cio", f"Nenhum cio registrado em {s.del_dias} dias pós-parto")
    if s.situacao != "PRENHE" and s.ias_no_ciclo >= config.alerta_repetidora:
        s.alertar("repetidora", f"Repetidora: {s.ias_no_ciclo} inseminações sem prenhez confirmada")
    if s.categoria == "SECA" and s.situacao != "PRENHE":
        s.alertar("seca_vazia", "Seca e sem prenhez confirmada")
    if s.previsao_parto and s.previsao_parto < hoje - timedelta(days=10):
        s.alertar("parto_atrasado", "Parto previsto já passou; registre o parto ou revise o diagnóstico")
    if s.situacao == "INSEMINADA" and hoje > s.data_diagnostico + timedelta(days=30):
        s.alertar("diagnostico_atrasado", "Diagnóstico de gestação atrasado")
    return s
