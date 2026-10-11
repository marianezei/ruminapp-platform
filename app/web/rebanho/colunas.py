"""
Colunas da lista de animais.

Cada coluna sabe como se ordenar e qual é o seu sentido natural: nome vai de A a Z,
dias vai do maior para o menor, data de parto vai do mais recente para o mais antigo,
e a próxima data importante vai da mais próxima para a mais distante.

Ordenar acontece em Python, e não no banco, porque a maior parte destas colunas é
calculada a partir dos eventos (situação, dias no estado, previsão de parto).
"""
from dataclasses import dataclass
from datetime import date
from typing import Callable

MAIOR = date.max
MENOR = date.min

# Ordem em que as categorias e situações fazem sentido, do começo ao fim do ciclo.
ORDEM_CATEGORIA = {"BEZERRA": 0, "NOVILHA": 1, "LACTACAO": 2, "SECA": 3, "BAIXA": 4}
ORDEM_SITUACAO = {"VAZIA": 0, "INSEMINADA": 1, "PRENHE": 2}


def chave_brinco(animal):
    """Ordena 1, 2, 10 (e não 1, 10, 2), mas aceita brincos que são nomes."""
    b = animal.brinco.strip()
    return (0, int(b), "") if b.isdigit() else (1, 0, b.upper())


def proxima_data(animal):
    s = animal.status
    return s.previsao_parto or s.data_diagnostico or s.proximo_cio or s.liberacao_ia or MAIOR


@dataclass(frozen=True)
class Coluna:
    chave: str
    titulo: str
    ordenar: Callable            # devolve o valor de ordenação de um animal
    desc: bool = False           # True = o primeiro clique ordena do maior para o menor
    numerica: bool = False       # alinha à direita
    curta: bool = False          # não aparece no cartão do celular
    prioridade: int = 5          # 1 = nunca sai; quanto maior, mais cedo sai se faltar espaço
    vazio: Callable | None = None  # True quando o animal não tem valor nesta coluna

    @property
    def dica(self):
        return "maior para o menor" if self.desc else "do começo ao fim"


COLUNAS = [
    Coluna("brinco", "Brinco", chave_brinco, prioridade=1),
    Coluna("nome", "Nome", lambda a: (a.nome or "").upper(), vazio=lambda a: not a.nome, prioridade=1),
    Coluna("raca", "Raça", lambda a: a.get_raca_display(), curta=True, prioridade=9),
    Coluna("lote", "Lote", lambda a: (a.lote.nome if a.lote else ""),
           vazio=lambda a: a.lote is None, prioridade=6),
    Coluna("categoria", "Categoria", lambda a: ORDEM_CATEGORIA[a.status.categoria], prioridade=4),
    Coluna("situacao", "Situação", lambda a: ORDEM_SITUACAO.get(a.status.situacao, 9), prioridade=1),
    Coluna("dias", "Dias", lambda a: a.status.dias_situacao if a.status.dias_situacao is not None else -1,
           desc=True, numerica=True, vazio=lambda a: a.status.dias_situacao is None, prioridade=1),
    Coluna("peso", "Peso", lambda a: float(a.peso_atual.peso) if a.peso_atual else -1,
           desc=True, numerica=True, vazio=lambda a: a.peso_atual is None, prioridade=7),
    Coluna("partos", "Partos", lambda a: a.status.n_partos, desc=True, numerica=True, curta=True,
           prioridade=8),
    Coluna("del", "DEL", lambda a: a.status.del_dias if a.status.del_dias is not None else -1,
           desc=True, numerica=True, curta=True, vazio=lambda a: a.status.del_dias is None, prioridade=8),
    Coluna("parto", "Último parto", lambda a: a.status.ultimo_parto or MENOR, desc=True,
           vazio=lambda a: a.status.ultimo_parto is None, prioridade=5),
    Coluna("proxima", "Próxima data importante", proxima_data,
           vazio=lambda a: proxima_data(a) is MAIOR, prioridade=2),
]

POR_CHAVE = {c.chave: c for c in COLUNAS}
PADRAO = "brinco"


def ordenar(animais, chave, sentido=None):
    """`sentido` é 'asc', 'desc' ou None (usa o sentido natural da coluna)."""
    coluna = POR_CHAVE.get(chave) or POR_CHAVE[PADRAO]
    desc = coluna.desc if sentido not in ("asc", "desc") else (sentido == "desc")
    # Desempate sempre pelo brinco, para a lista não "dançar" entre recarregamentos.
    animais = sorted(animais, key=chave_brinco)
    animais = sorted(animais, key=coluna.ordenar, reverse=desc)

    # Animais sem valor nesta coluna vão para o fim nos dois sentidos: inverter a ordem
    # não deveria jogar as linhas vazias para o topo.
    if coluna.vazio:
        com = [a for a in animais if not coluna.vazio(a)]
        sem = [a for a in animais if coluna.vazio(a)]
        animais = com + sem
    return animais, coluna.chave, ("desc" if desc else "asc")


def cabecalhos(chave_atual, sentido_atual):
    """Dados que o template usa para montar os links de ordenação."""
    linha = []
    for c in COLUNAS:
        ativa = c.chave == chave_atual
        # Clicar de novo na coluna ativa inverte; numa coluna nova, usa o sentido natural dela.
        proximo = ("asc" if sentido_atual == "desc" else "desc") if ativa else ("desc" if c.desc else "asc")
        linha.append({
            "chave": c.chave, "titulo": c.titulo, "numerica": c.numerica, "curta": c.curta,
            "prioridade": c.prioridade,
            "ativa": ativa, "sentido": sentido_atual if ativa else "",
            "proximo": proximo,
            "seta": ("↓" if sentido_atual == "desc" else "↑") if ativa else "",
        })
    return linha
