"""
Cria um rebanho fictício com histórico coerente, relativo à data de hoje,
para você testar o painel e as listas. Uso:

    python manage.py popular_exemplo            # ~120 animais
    python manage.py popular_exemplo --limpar   # apaga tudo antes
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from rebanho.models import Animal, Evento, Lote, Touro

GESTACAO_POR_RACA = {"HOL": 280, "JER": 279, "PS": 290, "GIROL": 285, "GIR": 290, "OUT": 283}

NOMES = [
    "Mimosa", "Estrela", "Pintada", "Boneca", "Princesa", "Malhada", "Flor", "Jóia", "Serena",
    "Morena", "Branquinha", "Cigana", "Faceira", "Graúna", "Lua", "Bonita", "Açucena", "Fumaça",
    "Brisa", "Canela", "Pérola", "Safira", "Rosinha", "Tulipa", "Garoa", "Aurora", "Vitória",
    "Ventania", "Dama", "Baronesa", "Caju", "Pipoca", "Jabuticaba", "Sereia", "Chuvisco",
]


# Exemplo de convenção comum: uma cor de brinco por ano de nascimento.
# Animais de anos fora da tabela ficam com a cor padrão do tema.
_hoje = date.today()
COR_POR_ANO = {_hoje.year: "azul", _hoje.year - 1: "verde", _hoje.year - 2: "laranja"}


class Command(BaseCommand):
    help = "Popula o banco com um rebanho de exemplo"

    def add_arguments(self, parser):
        parser.add_argument("--limpar", action="store_true", help="Apaga todos os animais antes")
        parser.add_argument("--semente", type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(opts["semente"])
        hoje = date.today()
        if opts["limpar"]:
            Evento.objects.all().delete()
            Animal.objects.all().delete()

        lotes = {n: Lote.objects.get_or_create(nome=n)[0] for n in
                 ["Alta produção", "Baixa produção", "Secas", "Pré-parto", "Novilhas", "Bezerras"]}
        touros = [Touro.objects.get_or_create(nome=n, defaults={"codigo": c, "raca": r})[0] for n, c, r in [
            ("Radar", "GIROL-1021", "Girolando 3/4"), ("Imperador", "GIR-3380", "Gir Leiteiro"),
            ("Titan", "HOL-7715", "Holandês"), ("Faraó", "GIROL-0442", "Girolando 5/8"),
        ]]
        inseminadores = ["João", "Severino", "Técnico da cooperativa"]
        numero = [1000 + Animal.objects.count()]
        eventos = []

        def novo_brinco():
            numero[0] += 1
            return str(numero[0])

        def ev(animal, tipo, data, **kw):
            if data <= hoje:
                eventos.append(Evento(animal=animal, tipo=tipo, data=data, **kw))

        def ia(animal, data):
            ev(animal, "IA", data, touro=rnd.choice(touros), inseminador=rnd.choice(inseminadores))

        def ciclo_ate_concepcao(animal, concepcao, n_ias):
            """IAs a cada ~21 dias terminando na concepção, e diagnóstico positivo."""
            for i in range(n_ias - 1, 0, -1):
                data_ia = concepcao - timedelta(days=21 * i + rnd.randint(-2, 2))
                ia(animal, data_ia)
            ia(animal, concepcao)
            ev(animal, "DG", concepcao + timedelta(days=rnd.randint(30, 40)), resultado="POS")

        def historico_partos(animal, ultimo_parto, n_partos, gest):
            """Partos anteriores com o ciclo completo entre eles."""
            datas = [ultimo_parto]
            for _ in range(n_partos - 1):
                datas.insert(0, datas[0] - timedelta(days=rnd.randint(370, 450)))
            for i, p in enumerate(datas):
                ev(animal, "PARTO", p)
                if i + 1 < len(datas):
                    prox = datas[i + 1]
                    concepcao = prox - timedelta(days=gest + rnd.randint(-3, 3))
                    ciclo_ate_concepcao(animal, concepcao, rnd.choice([1, 1, 2, 2, 3]))
                    ev(animal, "SECAGEM", prox - timedelta(days=rnd.randint(55, 65)))
            return datas[0]

        cenarios = (
            ["recem_parida"] * 14 + ["vazia_com_cio"] * 16 + ["cio_proximo"] * 8 + ["sem_cio"] * 4
            + ["inseminada"] * 14 + ["repetidora"] * 3 + ["prenhe"] * 22 + ["a_secar"] * 5
            + ["seca"] * 12 + ["novilha_nova"] * 6 + ["novilha_apta"] * 6 + ["novilha_prenhe"] * 6
            + ["bezerra"] * 8
        )
        rnd.shuffle(cenarios)

        for cen in cenarios:
            raca = rnd.choice(["GIROL"] * 6 + ["HOL"] * 2 + ["GIR"])
            gest = GESTACAO_POR_RACA[raca]
            eh_novilha = cen.startswith("novilha") or cen == "bezerra"
            if cen == "bezerra":
                nasc = hoje - timedelta(days=rnd.randint(30, 330))
            elif eh_novilha:
                nasc = hoje - timedelta(days=rnd.randint(14 * 30, 26 * 30) if cen != "novilha_nova" else rnd.randint(12 * 30, 13 * 30))
            else:
                nasc = hoje - timedelta(days=rnd.randint(3 * 365, 8 * 365))

            if cen == "bezerra":
                lote = lotes["Bezerras"]
            elif eh_novilha:
                lote = lotes["Novilhas"]
            elif cen == "seca":
                lote = lotes["Secas"]
            else:
                lote = rnd.choice([lotes["Alta produção"], lotes["Baixa produção"]])

            a = Animal.objects.create(
                brinco=novo_brinco(), nome=rnd.choice(NOMES), raca=raca, data_nascimento=nasc,
                lote=lote, pai=rnd.choice(touros), cor_brinco=COR_POR_ANO.get(nasc.year, ""),
            )
            n_partos = rnd.randint(1, 4)

            if cen == "recem_parida":
                historico_partos(a, hoje - timedelta(days=rnd.randint(3, 45)), n_partos, gest)
            elif cen in ("vazia_com_cio", "cio_proximo"):
                p = hoje - timedelta(days=rnd.randint(55, 110))
                historico_partos(a, p, n_partos, gest)
                if cen == "cio_proximo":
                    ultimo_cio = hoje - timedelta(days=21 + rnd.randint(-3, 2))
                else:
                    ultimo_cio = p + timedelta(days=rnd.randint(25, 45))
                ev(a, "CIO", max(ultimo_cio, p + timedelta(days=20)))
            elif cen == "sem_cio":
                historico_partos(a, hoje - timedelta(days=rnd.randint(95, 150)), n_partos, gest)
            elif cen == "inseminada":
                data_ia = hoje - timedelta(days=rnd.randint(3, 45))
                historico_partos(a, data_ia - timedelta(days=rnd.randint(55, 110)), n_partos, gest)
                ia(a, data_ia)
            elif cen == "repetidora":
                ultima = hoje - timedelta(days=rnd.randint(5, 15))
                historico_partos(a, ultima - timedelta(days=42 + rnd.randint(55, 90)), n_partos, gest)
                for d in (42, 21, 0):
                    ia(a, ultima - timedelta(days=d))
            elif cen in ("prenhe", "a_secar", "seca"):
                if cen == "prenhe":
                    concepcao = hoje - timedelta(days=rnd.randint(40, gest - 75))
                elif cen == "a_secar":
                    concepcao = hoje - timedelta(days=gest - 60 - rnd.randint(-3, 6))
                else:
                    concepcao = hoje - timedelta(days=rnd.randint(gest - 58, gest - 5))
                historico_partos(a, concepcao - timedelta(days=rnd.randint(60, 140)), n_partos, gest)
                ciclo_ate_concepcao(a, concepcao, rnd.choice([1, 1, 2, 3]))
                if cen == "seca":
                    ev(a, "SECAGEM", concepcao + timedelta(days=gest - rnd.randint(58, 62)))
            elif cen == "novilha_apta":
                if rnd.random() < 0.6:
                    ev(a, "CIO", hoje - timedelta(days=rnd.randint(5, 30)))
            elif cen == "novilha_prenhe":
                concepcao = hoje - timedelta(days=rnd.randint(40, gest - 10))
                nasc_min = concepcao - timedelta(days=15 * 30)
                if a.data_nascimento > nasc_min:
                    a.data_nascimento = nasc_min
                    a.save()
                ciclo_ate_concepcao(a, concepcao, rnd.choice([1, 1, 2]))

        Evento.objects.bulk_create(eventos)
        self.stdout.write(self.style.SUCCESS(
            f"Criados {len(cenarios)} animais e {len(eventos)} eventos."))
