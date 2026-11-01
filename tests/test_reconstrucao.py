"""Evento atrasado, reconstrução por aluno e reprocessamento total.

O ponto central é a igualdade exata: a ordem de chegada dos eventos não pode
mudar nenhum valor do gêmeo.
"""
import json
import random
from datetime import datetime, timezone

import pytest

import db
import pipeline.consumidor as consumidor
from gemeo import repositorio
from ingestao.receber import receber
from ingestao.simulador import simular
from pipeline import fila
from pipeline.consumidor import (
    EventoAtrasado,
    ResumoProcessamento,
    processar_evento,
    processar_pendentes,
    reconstruir_aluno,
    reprocessar_tudo,
)
from tests.fabricas import evento_dict
from tests.utilitarios import dump_gemeo

AGORA = datetime(2026, 3, 5, 8, 30, 0, tzinfo=timezone.utc)
OUTRO_AGORA = datetime(2026, 3, 6, 9, 0, 0, tzinfo=timezone.utc)


def outro_relogio():
    return OUTRO_AGORA


def relogio():
    return AGORA


@pytest.fixture
def conn(tmp_path):
    c = db.abrir(tmp_path / "t.db")
    yield c
    c.close()


@pytest.fixture
def conn_b(tmp_path):
    c = db.abrir(tmp_path / "b.db")
    yield c
    c.close()


def receber_todos(conn, eventos):
    for dado in eventos:
        assert receber(conn, dado, agora=relogio).status == "aceito"


def status_de(conn):
    return {
        l["event_id"]: l["status"]
        for l in conn.execute("SELECT event_id, status FROM eventos_brutos")
    }


def inserir_linha(conn, status="pendente", payload_json=None, **campos):
    """Grava uma linha direto, sem a ingestão (dado que ela barraria)."""
    dado = evento_dict(**campos)
    conn.execute(
        "INSERT INTO eventos_brutos (event_id, student_id, exercise_id, topic, "
        "event_type, occurred_at, payload_json, bruto_json, recebido_em, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            dado["event_id"],
            dado["student_id"],
            dado["exercise_id"],
            dado["topic"],
            dado["event_type"],
            dado["occurred_at"],
            json.dumps(dado["payload"]) if payload_json is None else payload_json,
            json.dumps(dado),
            "2026-03-05T08:00:00Z",
            status,
        ),
    )


def sequencia(student_id="aluno-1", prefixo=""):
    """Quatro eventos em ordem cronológica, sobre o mesmo exercício."""
    acertos = [True, False, False, True]
    return [
        evento_dict(
            event_id=f"{prefixo}e{i}",
            student_id=student_id,
            occurred_at=f"2026-03-02T12:0{i}:00Z",
            payload={"acertou": acerto, "tempo_gasto_s": 40 + 30 * i},
        )
        for i, acerto in enumerate(acertos, start=1)
    ]


def test_ordem_de_chegada_nao_importa(conn, conn_b):
    inicio = datetime(2026, 1, 5, tzinfo=timezone.utc)
    eventos = simular(semente=7, n_alunos=4, inicio=inicio, dias=14).eventos

    receber_todos(conn, eventos)
    processar_pendentes(conn, agora=relogio)

    embaralhado = list(eventos)
    random.Random(0).shuffle(embaralhado)
    corte = len(embaralhado) // 3
    lotes = [embaralhado[:corte], embaralhado[corte : 2 * corte], embaralhado[2 * corte :]]
    reconstruidos = 0
    for lote in lotes:
        receber_todos(conn_b, lote)
        reconstruidos += processar_pendentes(conn_b, agora=relogio).alunos_reconstruidos

    assert reconstruidos > 0
    assert dump_gemeo(conn) != []
    assert dump_gemeo(conn) == dump_gemeo(conn_b)
    assert set(status_de(conn_b).values()) == {"processado"}


def test_empate_de_horario_desempata_por_event_id(conn, conn_b):
    mesmo_horario = "2026-03-02T12:00:00Z"
    a = evento_dict(
        event_id="a",
        occurred_at=mesmo_horario,
        payload={"acertou": True, "tempo_gasto_s": 30},
    )
    b = evento_dict(
        event_id="b",
        occurred_at=mesmo_horario,
        payload={"acertou": False, "tempo_gasto_s": 200},
    )

    receber_todos(conn_b, [a, b])
    processar_pendentes(conn_b, agora=relogio)

    receber_todos(conn, [b])
    processar_pendentes(conn, agora=relogio)
    receber_todos(conn, [a])
    resumo = processar_pendentes(conn, agora=relogio)

    assert resumo == ResumoProcessamento(processados=1, rejeitados=0, alunos_reconstruidos=1)
    assert dump_gemeo(conn) == dump_gemeo(conn_b)
    assert repositorio.ler_aluno(conn, "aluno-1").ultimo_evento_id == "b"


def test_reprocessar_tudo_reproduz_o_estado_incremental(conn):
    inicio = datetime(2026, 1, 5, tzinfo=timezone.utc)
    eventos = simular(semente=3, n_alunos=3, inicio=inicio, dias=10).eventos
    receber_todos(conn, eventos[::-1])
    processar_pendentes(conn, agora=relogio)
    antes = dump_gemeo(conn)
    assert antes != []

    resumo = reprocessar_tudo(conn, agora=relogio)

    assert resumo == ResumoProcessamento(processados=len(eventos), rejeitados=0)
    assert dump_gemeo(conn) == antes
    assert set(status_de(conn).values()) == {"processado"}
    assert not conn.in_transaction


def test_reconstruir_aluno_e_idempotente(conn):
    receber_todos(conn, sequencia())
    processar_pendentes(conn, agora=relogio)
    antes = dump_gemeo(conn)

    primeiro = reconstruir_aluno(conn, "aluno-1", agora=relogio)
    depois_1 = dump_gemeo(conn)
    segundo = reconstruir_aluno(conn, "aluno-1", agora=relogio)

    assert primeiro == segundo == 4
    assert antes == depois_1 == dump_gemeo(conn)
    assert set(status_de(conn).values()) == {"processado"}
    assert not conn.in_transaction


def test_reconstruir_aluno_sem_eventos_devolve_zero(conn):
    assert reconstruir_aluno(conn, "ninguem", agora=relogio) == 0
    assert dump_gemeo(conn) == []


def test_reconstruir_aplica_tambem_os_pendentes_do_aluno(conn, conn_b):
    receber_todos(conn, sequencia())
    processar_evento(conn, "e1", agora=relogio)

    assert reconstruir_aluno(conn, "aluno-1", agora=outro_relogio) == 4

    assert set(status_de(conn).values()) == {"processado"}
    receber_todos(conn_b, sequencia())
    processar_pendentes(conn_b, agora=relogio)
    assert dump_gemeo(conn) == dump_gemeo(conn_b)
    carimbos = {l[0] for l in conn.execute("SELECT processado_em FROM eventos_brutos")}
    assert carimbos == {"2026-03-06T09:00:00Z"}


def test_reconstruir_so_afeta_o_aluno_alvo(conn):
    receber_todos(conn, sequencia("aluno-1") + sequencia("aluno-2", prefixo="b"))
    processar_pendentes(conn, agora=relogio)
    receber_todos(conn, [evento_dict(event_id="novo", student_id="aluno-2",
                                     occurred_at="2026-03-03T10:00:00Z")])
    outro_antes = [l for l in dump_gemeo(conn) if "aluno-2" in l]
    linhas_antes = conn.execute(
        "SELECT event_id, status, processado_em FROM eventos_brutos "
        "WHERE student_id = 'aluno-2' ORDER BY event_id"
    ).fetchall()

    reconstruir_aluno(conn, "aluno-1", agora=outro_relogio)

    assert [l for l in dump_gemeo(conn) if "aluno-2" in l] == outro_antes
    linhas_depois = conn.execute(
        "SELECT event_id, status, processado_em FROM eventos_brutos "
        "WHERE student_id = 'aluno-2' ORDER BY event_id"
    ).fetchall()
    assert [tuple(l) for l in linhas_depois] == [tuple(l) for l in linhas_antes]
    assert status_de(conn)["novo"] == "pendente"
    assert repositorio.ler_aluno(conn, "aluno-1").respostas == 4


def test_rejeitado_continua_rejeitado_no_reprocessamento(conn, conn_b):
    receber_todos(conn, sequencia())
    receber_todos(conn_b, sequencia())
    inserir_linha(conn, event_id="fantasma", exercise_id="exercicio-fantasma",
                  occurred_at="2026-03-02T12:02:30Z")
    receber(conn, evento_dict(event_id="ruim", student_id=""), agora=relogio)
    assert processar_pendentes(conn, agora=relogio).rejeitados == 1
    processar_pendentes(conn_b, agora=relogio)
    assert status_de(conn)["fantasma"] == status_de(conn)["ruim"] == "rejeitado"

    resumo = reprocessar_tudo(conn, agora=relogio)

    assert resumo == ResumoProcessamento(processados=4, rejeitados=0)
    assert status_de(conn)["fantasma"] == status_de(conn)["ruim"] == "rejeitado"
    assert dump_gemeo(conn) == dump_gemeo(conn_b)  # o rejeitado não foi aplicado
    motivo = conn.execute(
        "SELECT motivo_rejeicao FROM eventos_brutos WHERE event_id = 'fantasma'"
    ).fetchone()[0]
    assert "exercicio-fantasma" in motivo


def test_reprocessar_banco_vazio(conn):
    assert reprocessar_tudo(conn, agora=relogio) == ResumoProcessamento(0, 0, 0)
    assert dump_gemeo(conn) == []
    assert not conn.in_transaction


def test_processar_pendentes_conta_o_aluno_reconstruido_uma_vez(conn):
    receber_todos(conn, sequencia("aluno-1")[2:])  # e3, e4
    processar_pendentes(conn, agora=relogio)
    # dois atrasados do mesmo aluno e um evento em dia de outro aluno
    receber_todos(conn, sequencia("aluno-1")[:2])
    receber_todos(conn, sequencia("aluno-2", prefixo="b")[:1])

    resumo = processar_pendentes(conn, agora=relogio)

    assert resumo == ResumoProcessamento(processados=3, rejeitados=0, alunos_reconstruidos=1)
    assert set(status_de(conn).values()) == {"processado"}
    assert repositorio.ler_aluno(conn, "aluno-1").respostas == 4
    assert repositorio.ler_aluno(conn, "aluno-2").respostas == 1


def test_processar_evento_isolado_continua_levantando_evento_atrasado(conn):
    receber_todos(conn, sequencia()[1:2])
    processar_pendentes(conn, agora=relogio)
    antes = dump_gemeo(conn)
    receber_todos(conn, sequencia()[:1])

    with pytest.raises(EventoAtrasado) as info:
        processar_evento(conn, "e1", agora=relogio)

    assert info.value.student_id == "aluno-1"
    assert status_de(conn)["e1"] == "pendente"
    assert dump_gemeo(conn) == antes


def test_rejeitado_durante_a_reconstrucao_segue_rejeitado_e_o_resto_aplica(conn):
    receber_todos(conn, sequencia())
    processar_pendentes(conn, agora=relogio)
    inserir_linha(conn, status="processado", event_id="fantasma",
                  exercise_id="exercicio-fantasma", occurred_at="2026-03-02T12:02:30Z")

    aplicados = reconstruir_aluno(conn, "aluno-1", agora=relogio)

    assert aplicados == 4
    assert status_de(conn)["fantasma"] == "rejeitado"
    motivo = conn.execute(
        "SELECT motivo_rejeicao FROM eventos_brutos WHERE event_id = 'fantasma'"
    ).fetchone()[0]
    assert "exercicio-fantasma" in motivo
    assert repositorio.ler_aluno(conn, "aluno-1").respostas == 4


@pytest.mark.parametrize(
    "defeito",
    [
        {"payload_json": "isto nao e json"},
        {"payload_json": "[1, 2]"},
        {"payload_json": json.dumps({"acertou": "sim", "tempo_gasto_s": 5})},
        {"event_type": "tipo_inexistente"},
        {"occurred_at": "2026-03-02 12:02:30"},
    ],
)
def test_linha_irreconstruivel_e_rejeitada_e_nao_derruba_a_reconstrucao(conn, defeito):
    receber_todos(conn, sequencia())
    processar_pendentes(conn, agora=relogio)
    inserir_linha(conn, status="processado", event_id="torto",
                  **{"occurred_at": "2026-03-02T12:02:30Z", **defeito})

    aplicados = reconstruir_aluno(conn, "aluno-1", agora=relogio)

    assert aplicados == 4
    assert status_de(conn)["torto"] == "rejeitado"
    motivo = conn.execute(
        "SELECT motivo_rejeicao FROM eventos_brutos WHERE event_id = 'torto'"
    ).fetchone()[0]
    assert motivo
    assert len(fila.eventos_do_aluno(conn, "aluno-1")) == 4
    assert not conn.in_transaction


def test_falha_no_meio_da_reconstrucao_desfaz_tudo(conn, monkeypatch):
    receber_todos(conn, sequencia())
    processar_pendentes(conn, agora=relogio)
    antes = dump_gemeo(conn)
    carimbos = conn.execute("SELECT event_id, status, processado_em FROM eventos_brutos").fetchall()
    original = consumidor.aplicar_evento
    chamadas = []

    def falha_na_terceira(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 3:
            raise RuntimeError("bug inesperado")
        return original(*args, **kwargs)

    monkeypatch.setattr(consumidor, "aplicar_evento", falha_na_terceira)

    with pytest.raises(RuntimeError, match="bug inesperado"):
        reconstruir_aluno(conn, "aluno-1", agora=outro_relogio)

    assert dump_gemeo(conn) == antes
    depois = conn.execute("SELECT event_id, status, processado_em FROM eventos_brutos").fetchall()
    assert [tuple(l) for l in depois] == [tuple(l) for l in carimbos]
    assert not conn.in_transaction


def test_eventos_do_aluno_exclui_rejeitados_e_ordena_pela_chave(conn):
    receber_todos(conn, [
        evento_dict(event_id="b", occurred_at="2026-03-02T12:00:00Z"),
        evento_dict(event_id="a", occurred_at="2026-03-02T12:00:00Z"),
        evento_dict(event_id="z", occurred_at="2026-03-02T11:00:00Z"),
        evento_dict(event_id="outro", student_id="aluno-2"),
    ])
    inserir_linha(conn, status="rejeitado", event_id="r", occurred_at="2026-03-02T10:00:00Z")
    processar_evento(conn, "b", agora=relogio)

    ids = [e.event_id for e in fila.eventos_do_aluno(conn, "aluno-1")]

    assert ids == ["z", "a", "b"]  # pendentes e processados, sem o rejeitado


def test_devolver_todos_a_pendente_so_mexe_nos_nao_rejeitados(conn):
    receber_todos(conn, sequencia())
    processar_evento(conn, "e1", agora=relogio)
    inserir_linha(conn, status="rejeitado", event_id="r", occurred_at="2026-03-02T10:00:00Z")

    fila.devolver_todos_a_pendente(conn)

    estados = status_de(conn)
    assert estados == {"e1": "pendente", "e2": "pendente", "e3": "pendente",
                       "e4": "pendente", "r": "rejeitado"}
    assert conn.execute(
        "SELECT COUNT(*) FROM eventos_brutos WHERE processado_em IS NOT NULL"
    ).fetchone()[0] == 0
