from fastapi.testclient import TestClient

from reproducao.api import app

cliente = TestClient(app)


def test_calcula_um_lote():
    r = cliente.post("/v1/status", json={
        "hoje": "2026-09-10",
        "animais": [
            {"id": 1, "raca": "HOL", "data_nascimento": "2021-01-01",
             "eventos": [{"id": 1, "tipo": "PARTO", "data": "2026-06-22"},
                         {"id": 2, "tipo": "IA", "data": "2026-08-21", "touro_id": 7}]},
            {"id": 2, "raca": "GIR", "data_nascimento": "2026-06-02"},
        ],
    })
    assert r.status_code == 200
    por_id = {s["id"]: s for s in r.json()["status"]}
    assert por_id[1]["situacao"] == "INSEMINADA"
    assert por_id[1]["touro_ultima_ia"] == 7
    assert por_id[1]["data_diagnostico"] == "2026-09-20"
    assert por_id[2]["categoria"] == "BEZERRA"


def test_respeita_a_configuracao_enviada():
    r = cliente.post("/v1/status", json={
        "hoje": "2026-09-10",
        "config": {"periodo_voluntario_espera": 10},
        "animais": [{"id": 1, "raca": "HOL", "eventos": [{"tipo": "PARTO", "data": "2026-08-30"}]}],
    })
    assert r.json()["status"][0]["apta_ia"] is True


def test_rejeita_pedido_invalido():
    assert cliente.post("/v1/status", json={"animais": "x"}).status_code == 422


def test_health():
    assert cliente.get("/healthz").json() == {"status": "ok"}
