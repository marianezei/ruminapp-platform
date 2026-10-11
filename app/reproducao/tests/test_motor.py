from datetime import date, timedelta
from types import SimpleNamespace

from reproducao.api import Configuracao
from reproducao.motor import calcular

HOJE = date(2026, 9, 10)
CFG = Configuracao()


def e(tipo, dias_atras, resultado="", id_=0):
    return SimpleNamespace(tipo=tipo, data=HOJE - timedelta(days=dias_atras), resultado=resultado,
                           touro_id=None, id=id_)


def status(eventos, raca="HOL", nasc=date(2021, 1, 1)):
    return calcular(eventos, raca=raca, data_nascimento=nasc, config=CFG, hoje=HOJE)


def test_recem_parida_nao_esta_liberada():
    s = status([e("PARTO", 20)])
    assert s.categoria == "LACTACAO"
    assert s.del_dias == 20
    assert not s.apta_ia
    assert s.liberacao_ia == HOJE + timedelta(days=30)


def test_vazia_apos_pve_com_cio_preve_proximo():
    s = status([e("PARTO", 80), e("CIO", 20)])
    assert s.apta_ia
    assert s.proximo_cio == HOJE + timedelta(days=1)
    assert not s.cio_estimado


def test_cio_antigo_e_projetado_em_ciclos():
    s = status([e("PARTO", 120), e("CIO", 60)])
    assert s.proximo_cio == HOJE + timedelta(days=3)
    assert s.cio_estimado


def test_inseminada_gera_janelas():
    s = status([e("PARTO", 90), e("IA", 20)])
    assert s.situacao == "INSEMINADA"
    assert s.retorno_inicio == HOJE - timedelta(days=2)
    assert s.data_diagnostico == HOJE + timedelta(days=10)


def test_cio_apos_ia_volta_para_vazia():
    s = status([e("PARTO", 100), e("IA", 25), e("CIO", 4)])
    assert s.situacao == "VAZIA"
    assert s.proximo_cio == HOJE + timedelta(days=17)


def test_prenhe_calcula_parto_secagem_e_pre_parto():
    s = status([e("PARTO", 200), e("IA", 100), e("DG", 65, "POS")], raca="HOL")
    concepcao = HOJE - timedelta(days=100)
    assert s.situacao == "PRENHE"
    assert s.previsao_parto == concepcao + timedelta(days=280)
    assert s.data_secar == s.previsao_parto - timedelta(days=60)
    assert s.data_pre_parto == s.previsao_parto - timedelta(days=21)
    assert s.ias_por_concepcao == [1]


def test_gestacao_varia_com_a_raca():
    eventos = [e("PARTO", 200), e("IA", 100), e("DG", 65, "POS")]
    diferenca = status(eventos, raca="GIR").previsao_parto - status(eventos, raca="HOL").previsao_parto
    assert diferenca.days == 10


def test_secagem_muda_categoria():
    s = status([e("PARTO", 300), e("IA", 230), e("DG", 195, "POS"), e("SECAGEM", 10)])
    assert s.categoria == "SECA"
    assert s.del_dias is None


def test_novo_parto_reinicia_ciclo():
    s = status([e("PARTO", 400), e("IA", 290), e("DG", 255, "POS"), e("SECAGEM", 70), e("PARTO", 5)])
    assert (s.categoria, s.situacao, s.n_partos, s.ias_no_ciclo) == ("LACTACAO", "VAZIA", 2, 0)


def test_alerta_sem_cio():
    s = status([e("PARTO", 100)])
    assert s.codigos_alerta == ["sem_cio"]
    assert "Nenhum cio" in s.alertas[0]


def test_alerta_repetidora():
    s = status([e("PARTO", 150), e("IA", 50), e("IA", 29), e("IA", 8)])
    assert "repetidora" in s.codigos_alerta


def test_novilha_liberada_pela_idade():
    nova = status([], nasc=HOJE - timedelta(days=13 * 30))
    velha = status([], nasc=HOJE - timedelta(days=15 * 31))
    assert nova.categoria == "NOVILHA"
    assert not nova.apta_ia
    assert velha.apta_ia


def test_bezerra():
    assert status([], nasc=HOJE - timedelta(days=100)).categoria == "BEZERRA"


def test_prenhe_conta_desde_a_concepcao():
    assert status([e("PARTO", 200), e("IA", 100), e("DG", 65, "POS")]).dias_situacao == 100


def test_inseminada_conta_desde_a_ia():
    assert status([e("PARTO", 90), e("IA", 20)]).dias_situacao == 20


def test_vazia_conta_dias_em_aberto_desde_o_parto():
    assert status([e("PARTO", 495), e("IA", 37), e("DG", 7, "NEG")]).dias_situacao == 495


def test_seca_conta_desde_a_secagem():
    s = status([e("PARTO", 300), e("IA", 218), e("DG", 180, "POS"), e("SECAGEM", 14)])
    assert s.dias_situacao == 14


def test_novilha_conta_a_idade():
    assert status([], nasc=HOJE - timedelta(days=288)).dias_situacao == 288
