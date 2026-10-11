"""
Geração do tema visual.

O usuário escolhe só três cores (principal, brinco e fundo). Todo o resto
(texto, bordas, superfícies, cores de alerta) é derivado aqui, garantindo
contraste legível. Se o fundo for escuro, o sistema entra em modo noturno.
"""
from __future__ import annotations

import re

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

BRANCO = "#FFFFFF"
PRETO = "#000000"

# Temas prontos: (nome, principal, brinco, fundo)
TEMAS = {
    "pasto": ("Pasto", "#2F5D3A", "#F2C230", "#F3F5F1"),
    "cerrado": ("Cerrado", "#7A4A22", "#E8772E", "#F2EEE6"),
    "acude": ("Açude", "#1F5F8B", "#7CC242", "#EEF3F7"),
    "curral": ("Curral", "#8E2F2A", "#F2C230", "#F5F2F0"),
    "noite": ("Noite", "#2F7A48", "#F2C230", "#161B18"),
    "contraste": ("Alto contraste", "#000000", "#FFD400", "#FFFFFF"),
}
TEMA_PADRAO = "pasto"

# Cores reais de brinco para a opção por animal (código, rótulo, hex)
CORES_BRINCO = [
    ("amarelo", "Amarelo", "#F2C230"),
    ("laranja", "Laranja", "#E8772E"),
    ("vermelho", "Vermelho", "#C8352B"),
    ("rosa", "Rosa", "#E77FB3"),
    ("roxo", "Roxo", "#7A4FA3"),
    ("azul", "Azul", "#2F6FB5"),
    ("verde", "Verde", "#2E8540"),
    ("branco", "Branco", "#F4F4F0"),
    ("preto", "Preto", "#2B2B2B"),
]

# Cores base dos avisos, ajustadas ao fundo escolhido
ATENCAO, PROBLEMA, INFO = "#9A6700", "#A8322A", "#2D5D8A"


def hex_para_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_para_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def misturar(a: str, b: str, t: float) -> str:
    """Mistura a cor `a` com `b`. t=0 devolve a, t=1 devolve b."""
    ra, rb = hex_para_rgb(a), hex_para_rgb(b)
    return rgb_para_hex(x + (y - x) * t for x, y in zip(ra, rb))


def luminancia(h: str) -> float:
    """Luminância relativa (WCAG 2.x)."""
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in hex_para_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def texto_para(fundo: str, escuro="#1C2620", claro=BRANCO, alvo: float = 4.5) -> str:
    """Escolhe entre texto escuro ou claro, o que tiver mais contraste.
    Em cores de tom médio, onde nenhum dos dois chega ao alvo, usa preto ou branco puros."""
    melhor = max((escuro, claro), key=lambda t: contraste(fundo, t))
    if contraste(fundo, melhor) >= alvo:
        return melhor
    return max((PRETO, BRANCO), key=lambda t: contraste(fundo, t))


def ajustar(cor: str, fundo: str, alvo: float = 4.5) -> str:
    """Clareia ou escurece `cor` até ter o contraste `alvo` sobre `fundo`."""
    if contraste(cor, fundo) >= alvo:
        return cor
    direcao = BRANCO if luminancia(fundo) < 0.5 else PRETO
    for passo in range(1, 21):
        nova = misturar(cor, direcao, passo / 20)
        if contraste(nova, fundo) >= alvo:
            return nova
    return direcao


def eh_escuro(fundo: str) -> bool:
    return luminancia(fundo) < 0.2


def variaveis(principal: str, brinco: str, fundo: str) -> dict[str, str]:
    """Todas as variáveis CSS do sistema a partir das três cores escolhidas."""
    if eh_escuro(fundo):
        superficie = misturar(fundo, BRANCO, 0.06)
        tinta = misturar(fundo, BRANCO, 0.90)
        linha = misturar(fundo, BRANCO, 0.16)
    else:
        superficie = misturar(fundo, BRANCO, 0.75)
        tinta = misturar(fundo, PRETO, 0.88)
        linha = misturar(fundo, tinta, 0.13)

    return {
        "--pasto": principal,
        "--pasto-escuro": misturar(principal, PRETO, 0.22),
        "--texto-principal": texto_para(principal),
        "--papel": fundo,
        "--superficie": superficie,
        "--tinta": tinta,
        "--tinta-suave": ajustar(misturar(tinta, fundo, 0.35), superficie, 4.5),
        "--linha": linha,
        "--link": ajustar(principal, superficie, 4.5),
        **variaveis_brinco(brinco),
        "--atencao": ajustar(ATENCAO, superficie, 4.5),
        "--problema": ajustar(PROBLEMA, superficie, 4.5),
        "--info": ajustar(INFO, superficie, 4.5),
        "color-scheme": "dark" if eh_escuro(fundo) else "light",
    }


def variaveis_brinco(cor: str) -> dict[str, str]:
    return {
        "--brinco": cor,
        "--brinco-borda": misturar(cor, PRETO, 0.2),
        "--brinco-texto": texto_para(cor),
    }


def css_tema(principal: str, brinco: str, fundo: str) -> str:
    """Bloco CSS com o tema do usuário e as classes das cores de brinco."""
    for c in (principal, brinco, fundo):
        if not HEX_RE.match(c or ""):
            raise ValueError(f"Cor inválida: {c!r}")
    raiz = "; ".join(f"{k}: {v}" for k, v in variaveis(principal, brinco, fundo).items())
    linhas = [f":root {{ {raiz}; }}"]
    for codigo, _, hexa in CORES_BRINCO:
        regras = "; ".join(f"{k}: {v}" for k, v in variaveis_brinco(hexa).items())
        linhas.append(f".brinco.cor-{codigo} {{ {regras}; }}")
    return "\n".join(linhas)


def css_padrao() -> str:
    _, p, b, f = TEMAS[TEMA_PADRAO]
    return css_tema(p, b, f)
