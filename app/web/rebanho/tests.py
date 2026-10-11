from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from fastapi.testclient import TestClient

from reproducao.api import app as servico_reproducao

from . import colunas, reproducao, tema
from .models import Animal, ConfiguracaoReprodutiva, Evento, Pesagem, PreferenciasVisuais
from .reproducao import CAMPOS_CONFIG, ReproducaoIndisponivel, Status, gerar_listas

HOJE = date(2026, 9, 10)
CFG = ConfiguracaoReprodutiva()
SERVICO = TestClient(servico_reproducao)


class SessaoDeTeste:
    """Encaminha as chamadas do cliente HTTP para o serviço reproducao em processo."""

    def post(self, url, json, timeout):
        return SERVICO.post(url, json=json)


def setUpModule():
    reproducao._sessao_http = SessaoDeTeste()


def e(tipo, dias_atras, resultado=""):
    return {"tipo": tipo, "data": (HOJE - timedelta(days=dias_atras)).isoformat(), "resultado": resultado}


def status(eventos, raca="HOL", nasc=date(2021, 1, 1)):
    r = SERVICO.post("/v1/status", json={
        "hoje": HOJE.isoformat(),
        "config": {c: getattr(CFG, c) for c in CAMPOS_CONFIG},
        "animais": [{"id": 1, "raca": raca, "data_nascimento": nasc.isoformat(), "eventos": eventos}],
    })
    return Status.do_json(r.json()["status"][0], {})


class ListasTest(TestCase):
    def test_listas_do_dia(self):
        def animal(brinco, eventos):
            a = SimpleNamespace(brinco=brinco)
            a.status = status(eventos)
            return a

        animais = [
            animal("1", [e("PARTO", 80), e("CIO", 20)]),                    # observar cio
            animal("2", [e("PARTO", 90), e("IA", 20)]),                     # retorno ao cio
            animal("3", [e("PARTO", 90), e("IA", 35)]),                     # diagnóstico
            animal("4", [e("PARTO", 300), e("IA", 218), e("DG", 180, "POS")]),  # secar
        ]
        listas = {l.chave: [i.animal.brinco for i in l.itens] for l in gerar_listas(animais, CFG, HOJE)}
        self.assertEqual(listas["cio"], ["1"])
        self.assertEqual(listas["retorno"], ["2"])
        self.assertEqual(listas["dg"], ["3"])
        self.assertEqual(listas["secar"], ["4"])


class TelasTest(TestCase):
    def setUp(self):
        User.objects.create_user("teste", password="x")
        self.client.login(username="teste", password="x")
        self.vaca = Animal.objects.create(brinco="101", nome="Mimosa")
        Evento.objects.create(animal=self.vaca, tipo="PARTO", data=date.today() - timedelta(days=80))

    def test_paginas_abrem(self):
        for url in ["/", "/animais/", f"/animais/{self.vaca.pk}/", "/eventos/novo/", "/parametros/",
                    "/animais/novo/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_nao_deixa_diagnosticar_sem_ia(self):
        r = self.client.post("/eventos/novo/", {
            "animal": self.vaca.pk, "tipo": "DG", "data": date.today().isoformat(), "resultado": "POS"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Evento.objects.filter(tipo="DG").exists())

    def test_venda_baixa_o_animal(self):
        self.client.post("/eventos/novo/", {
            "animal": self.vaca.pk, "tipo": "VENDA", "data": date.today().isoformat()})
        self.vaca.refresh_from_db()
        self.assertFalse(self.vaca.ativo)


class TemaTest(TestCase):
    def test_texto_do_brinco_tem_contraste(self):
        for _, _, cor in tema.CORES_BRINCO:
            v = tema.variaveis_brinco(cor)
            self.assertGreaterEqual(tema.contraste(v["--brinco"], v["--brinco-texto"]), 4.5, cor)

    def test_todos_os_temas_prontos_sao_legiveis(self):
        for chave, (_, p, b, f) in tema.TEMAS.items():
            v = tema.variaveis(p, b, f)
            self.assertGreaterEqual(tema.contraste(v["--tinta"], v["--superficie"]), 7, chave)
            self.assertGreaterEqual(tema.contraste(v["--link"], v["--superficie"]), 4.5, chave)
            self.assertGreaterEqual(tema.contraste(v["--pasto"], v["--texto-principal"]), 4.5, chave)
            self.assertGreaterEqual(tema.contraste(v["--problema"], v["--superficie"]), 4.5, chave)

    def test_fundo_escuro_ativa_modo_noturno(self):
        v = tema.variaveis("#2F7A48", "#F2C230", "#161B18")
        self.assertEqual(v["color-scheme"], "dark")
        self.assertGreater(tema.luminancia(v["--tinta"]), tema.luminancia(v["--superficie"]))

    def test_cor_principal_muito_clara_ainda_gera_link_legivel(self):
        v = tema.variaveis("#FFE8A0", "#F2C230", "#FFFFFF")
        self.assertGreaterEqual(tema.contraste(v["--link"], v["--superficie"]), 4.5)
        self.assertEqual(v["--texto-principal"], "#1C2620")

    def test_rejeita_cor_invalida(self):
        with self.assertRaises(ValueError):
            tema.css_tema("red; } body { display:none", "#F2C230", "#FFFFFF")


class AparenciaTelaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="x")
        self.client.login(username="ana", password="x")

    def test_salva_tema_do_usuario_e_aplica_no_css(self):
        r = self.client.post("/aparencia/", {"cor_principal": "#1f5f8b", "cor_brinco": "#7CC242",
                                             "cor_fundo": "#EEF3F7"})
        self.assertEqual(r.status_code, 302)
        prefs = PreferenciasVisuais.objects.get(usuario=self.user)
        self.assertEqual(prefs.tema, "acude")
        self.assertEqual(prefs.cor_principal, "#1F5F8B")
        self.assertContains(self.client.get("/"), "--pasto: #1F5F8B")

    def test_tema_personalizado(self):
        self.client.post("/aparencia/", {"cor_principal": "#123456", "cor_brinco": "#F2C230",
                                         "cor_fundo": "#FFFFFF"})
        self.assertEqual(PreferenciasVisuais.objects.get(usuario=self.user).tema, "personalizado")

    def test_cada_usuario_tem_seu_tema(self):
        self.client.post("/aparencia/", {"cor_principal": "#123456", "cor_brinco": "#F2C230",
                                         "cor_fundo": "#FFFFFF"})
        User.objects.create_user("beto", password="x")
        self.client.login(username="beto", password="x")
        self.assertNotContains(self.client.get("/"), "--pasto: #123456")

    def test_restaurar_padrao(self):
        self.client.post("/aparencia/", {"cor_principal": "#123456", "cor_brinco": "#F2C230",
                                         "cor_fundo": "#FFFFFF"})
        self.client.post("/aparencia/", {"restaurar": "1"})
        self.assertFalse(PreferenciasVisuais.objects.filter(usuario=self.user).exists())

    def test_cor_invalida_nao_salva(self):
        r = self.client.post("/aparencia/", {"cor_principal": "verde", "cor_brinco": "#F2C230",
                                             "cor_fundo": "#FFFFFF"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(PreferenciasVisuais.objects.exists())

    def test_previa(self):
        r = self.client.get("/aparencia/previa.css", {"principal": "#000000", "brinco": "#FFD400",
                                                      "fundo": "#FFFFFF"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("--brinco: #FFD400", r.content.decode())
        self.assertEqual(self.client.get("/aparencia/previa.css", {"principal": "x"}).status_code, 400)

    def test_cor_do_brinco_por_animal(self):
        vaca = Animal.objects.create(brinco="7", cor_brinco="laranja")
        self.assertContains(self.client.get(f"/animais/{vaca.pk}/"), "brinco grande cor-laranja")
        self.assertContains(self.client.get("/animais/?cor=laranja"), ">7</a>")
        self.assertNotContains(self.client.get("/animais/?cor=padrao"), ">7</a>")


CABECALHO = ("Nome;Brinco;N°;Nome do Lote;Data de nascimento;Idade (A,M);Pai;Mãe;Brinco da Mãe;"
             "# Lac.;Data Últ.Parto;DEL;Nº Lact.;Estado;Dias estado;# Ins.;Nome do touro;"
             "Data da secagem;Secagem (Prev.);Interv. parto;Int. Par. Prev.;"
             "Dias desde a última inseminação")


def linha(**campos):
    valores = dict.fromkeys(CABECALHO.split(";"), "")
    valores.update(campos)
    return ";".join(valores[c] for c in CABECALHO.split(";"))


class RotuloDiasTest(TestCase):
    def test_prenhe(self):
        s = status([e("PARTO", 200), e("IA", 100), e("DG", 65, "POS")])
        self.assertEqual((s.dias_situacao, s.rotulo_dias), (100, "Prenhe há"))

    def test_seca(self):
        s = status([e("PARTO", 300), e("IA", 218), e("DG", 180, "POS"), e("SECAGEM", 14)])
        self.assertEqual((s.dias_situacao, s.rotulo_dias), (14, "Seca há"))

    def test_novilha(self):
        s = status([], nasc=HOJE - timedelta(days=288))
        self.assertEqual((s.dias_situacao, s.rotulo_dias), (288, "Idade"))

    def test_datas_viram_date(self):
        s = status([e("PARTO", 90), e("IA", 20)])
        self.assertIsInstance(s.data_diagnostico, date)
        self.assertEqual(s.partos, [HOJE - timedelta(days=90)])


class IndisponibilidadeTest(TestCase):
    def setUp(self):
        User.objects.create_user("teste", password="x")
        self.client.login(username="teste", password="x")
        Animal.objects.create(brinco="1")

    def test_painel_responde_503_quando_o_servico_cai(self):
        with mock.patch.object(reproducao, "calcular_lote", side_effect=ReproducaoIndisponivel("x")), \
                mock.patch("rebanho.views.calcular_lote", side_effect=ReproducaoIndisponivel("x")):
            r = self.client.get("/")
        self.assertEqual(r.status_code, 503)
        self.assertContains(r, "indisponíveis", status_code=503)

    def test_health_nao_exige_login(self):
        self.client.logout()
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/readyz").status_code, 200)


class OrdenacaoTest(TestCase):
    def setUp(self):
        self.a = Animal.objects.create(brinco="2", nome="ZEBU")
        self.b = Animal.objects.create(brinco="10", nome="ABELHA")
        self.c = Animal.objects.create(brinco="3")          # sem nome
        for animal, dias in ((self.a, 300), (self.b, 10)):
            Evento.objects.create(animal=animal, tipo="PARTO",
                                  data=date.today() - timedelta(days=dias))
        Pesagem.objects.create(animal=self.b, data=date.today(), peso=420)

    def lista(self, **get):
        from .views import carregar_animais
        animais, _ = carregar_animais()
        ordenados, chave, sentido = colunas.ordenar(animais, get.get("ordem"), get.get("dir"))
        return [a.brinco for a in ordenados], chave, sentido

    def test_brinco_ordena_como_numero(self):
        self.assertEqual(self.lista(ordem="brinco")[0], ["2", "3", "10"])

    def test_nome_comeca_em_ordem_alfabetica(self):
        brincos, _, sentido = self.lista(ordem="nome")
        self.assertEqual(sentido, "asc")
        self.assertEqual(brincos[:2], ["10", "2"])

    def test_dias_comeca_do_maior_para_o_menor(self):
        brincos, _, sentido = self.lista(ordem="dias")
        self.assertEqual(sentido, "desc")
        self.assertEqual(brincos[0], "2")

    def test_sem_valor_fica_no_fim_nos_dois_sentidos(self):
        self.assertEqual(self.lista(ordem="nome", dir="asc")[0][-1], "3")
        self.assertEqual(self.lista(ordem="nome", dir="desc")[0][-1], "3")
        self.assertEqual(self.lista(ordem="peso", dir="asc")[0][0], "10")

    def test_coluna_desconhecida_cai_no_padrao(self):
        self.assertEqual(self.lista(ordem="inventada")[1], colunas.PADRAO)

    def test_cabecalho_inverte_a_coluna_ativa(self):
        cab = {c["chave"]: c for c in colunas.cabecalhos("dias", "desc")}
        self.assertEqual(cab["dias"]["proximo"], "asc")      # clicar de novo inverte
        self.assertEqual(cab["nome"]["proximo"], "asc")      # sentido natural do nome
        self.assertEqual(cab["del"]["proximo"], "desc")      # sentido natural dos dias


class ListaFiltrosTest(TestCase):
    def setUp(self):
        User.objects.create_user("ana", password="x")
        self.client.login(username="ana", password="x")
        for brinco, dias in (("1", 30), ("2", 120), ("3", 300)):
            a = Animal.objects.create(brinco=brinco)
            Evento.objects.create(animal=a, tipo="PARTO", data=date.today() - timedelta(days=dias))

    def brincos(self, **get):
        r = self.client.get("/animais/", get)
        return [a.brinco for a in r.context["animais"]]

    def test_filtra_por_dias_minimo_e_maximo(self):
        self.assertEqual(self.brincos(dias_min="100"), ["2", "3"])
        self.assertEqual(self.brincos(dias_max="100"), ["1"])
        self.assertEqual(self.brincos(dias_min="100", dias_max="200"), ["2"])

    def test_filtro_invalido_e_ignorado(self):
        self.assertEqual(len(self.brincos(dias_min="abc")), 3)

    def test_ordenar_nao_conta_como_filtro_ativo(self):
        self.assertFalse(self.client.get("/animais/", {"ordem": "dias"}).context["filtros_ativos"])
        self.assertTrue(self.client.get("/animais/", {"dias_min": "1"}).context["filtros_ativos"])

    def test_ordenacao_preserva_os_filtros(self):
        r = self.client.get("/animais/", {"dias_min": "100", "ordem": "nome"})
        self.assertIn("dias_min=100", r.context["querystring"])


class PesagemTest(TestCase):
    def setUp(self):
        User.objects.create_user("ana", password="x")
        self.client.login(username="ana", password="x")
        self.bezerra = Animal.objects.create(brinco="0005",
                                             data_nascimento=date.today() - timedelta(days=100))

    def registrar(self, **dados):
        dados.setdefault("animal", self.bezerra.pk)
        dados.setdefault("data", date.today().isoformat())
        return self.client.post("/pesagens/nova/", dados)

    def test_registra_e_mostra_o_peso(self):
        self.registrar(peso="78.5")
        self.assertEqual(float(self.bezerra.peso_atual.peso), 78.5)
        self.assertContains(self.client.get(f"/animais/{self.bezerra.pk}/"), "78,5 kg")

    def test_calcula_o_ganho_diario(self):
        Pesagem.objects.create(animal=self.bezerra, data=date.today() - timedelta(days=30), peso=50)
        Pesagem.objects.create(animal=self.bezerra, data=date.today(), peso=74)
        self.assertEqual(self.bezerra.ganho_diario, 0.8)

    def test_recusa_peso_fora_da_faixa(self):
        self.registrar(peso="0")
        self.assertFalse(Pesagem.objects.exists())

    def test_recusa_data_no_futuro(self):
        self.registrar(peso="80", data=(date.today() + timedelta(days=1)).isoformat())
        self.assertFalse(Pesagem.objects.exists())

    def test_recusa_pesagem_anterior_ao_nascimento(self):
        self.registrar(peso="80", data=(date.today() - timedelta(days=200)).isoformat())
        self.assertFalse(Pesagem.objects.exists())

    def test_recusa_duas_pesagens_no_mesmo_dia(self):
        self.registrar(peso="80")
        self.registrar(peso="81")
        self.assertEqual(Pesagem.objects.count(), 1)

    def test_excluir_pesagem(self):
        self.registrar(peso="80")
        pesagem = Pesagem.objects.get()
        self.client.post(f"/pesagens/{pesagem.pk}/excluir/")
        self.assertFalse(Pesagem.objects.exists())
