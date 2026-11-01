"""Consumo de eventos pendentes: ordem, idempotência, atomicidade e erros."""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

import db
import pipeline.consumidor as consumidor
from gemeo import repositorio
from ingestao.receber import receber
from pipeline.consumidor import (
    EventoAtrasado,
    EventoInvalido,
    ResumoProcessamento,
    processar_evento,
    processar_pendentes,
)
from tests.fabricas import evento_dict

AGORA = datetime(2026, 3, 5, 8, 30, 0, tzinfo=timezone.utc)


def relogio():
    return AGORA


@pytest.fixture
def conn(tmp_path):
    c = db.abrir(tmp_path / "t.db")
    yield c
    c.close()


def tres_eventos(student_id="aluno-1", prefixo=""):
    return [
        evento_dict(
            event_id=f"{prefixo}e1",
            student_id=student_id,
            event_type="exercicio_iniciado",
            occurred_at="2026-03-02T12:00:00Z",
        ),
        evento_dict(
            event_id=f"{prefixo}e2",
            student_id=student_id,
            occurred_at="2026-03-02T12:01:00Z",
            payload={"acertou": True, "tempo_gasto_s": 100},
        ),
        evento_dict(
            event_id=f"{prefixo}e3",
            student_id=student_id,
            occurred_at="2026-03-02T12:02:00Z",
            payload={"acertou": False, "tempo_gasto_s": 50},
        ),
    ]


def receber_todos(conn, eventos):
    for dado in eventos:
        assert receber(conn, dado, agora=relogio).status == "aceito"


def status_de(conn):
    return {
        l["event_id"]: l["status"]
        for l in conn.execute("SELECT event_id, status FROM eventos_brutos")
    }


def estado_do_gemeo(conn, student_id="aluno-1"):
    return (
        repositorio.ler_aluno(conn, student_id),
        repositorio.ler_topicos(conn, student_id),
        repositorio.ler_exercicio(conn, student_id, "funcoes-3"),
    )


def inserir_pendente_direto(conn, **campos):
    """Grava uma linha pendente sem passar pela ingestão (dado que ela barraria)."""
    dado = evento_dict(**campos)
    conn.execute(
        "INSERT INTO eventos_brutos (event_id, student_id, exercise_id, topic, "
        "event_type, occurred_at, payload_json, bruto_json, recebido_em, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente')",
        (
            dado["event_id"],
            dado["student_id"],
            dado["exercise_id"],
            dado["topic"],
            dado["event_type"],
            dado["occurred_at"],
            json.dumps(dado["payload"]),
            json.dumps(dado),
            "2026-03-05T08:00:00Z",
        ),
    )


def test_processa_pendentes_em_ordem_e_atualiza_o_gemeo(conn):
    receber_todos(conn, list(reversed(tres_eventos())))  # chegam fora de ordem

    resumo = processar_pendentes(conn, agora=relogio)

    assert resumo == ResumoProcessamento(processados=3, rejeitados=0)
    aluno, topicos, exercicio = estado_do_gemeo(conn)
    (topico,) = topicos
    assert topico.topic_id == "funcoes"
    assert topico.rating_elo == pytest.approx(999.263, abs=1e-3)
    assert (topico.tentativas, topico.acertos) == (2, 1)
    assert aluno.respostas == 2
    assert aluno.velocidade_media_s == 90.0
    assert aluno.erros_seguidos == 1
    assert aluno.ultimo_evento_id == "e3"
    assert (exercicio.tentativas, exercicio.acertou_alguma_vez) == (2, True)
    linhas = conn.execute("SELECT status, processado_em FROM eventos_brutos").fetchall()
    assert [l["status"] for l in linhas] == ["processado"] * 3
    assert {l["processado_em"] for l in linhas} == {"2026-03-05T08:30:00Z"}


def test_processar_evento_por_id_e_idempotente(conn):
    receber_todos(conn, tres_eventos())
    assert processar_evento(conn, "e1", agora=relogio) == "processado"
    assert processar_evento(conn, "e2", agora=relogio) == "processado"
    antes = estado_do_gemeo(conn)

    assert processar_evento(conn, "e2", agora=relogio) == "ignorado"

    assert estado_do_gemeo(conn) == antes
    assert status_de(conn) == {"e1": "processado", "e2": "processado", "e3": "pendente"}


def test_evento_desconhecido_levanta_key_error(conn):
    with pytest.raises(KeyError):
        processar_evento(conn, "nao-existe", agora=relogio)
    assert not conn.in_transaction


def test_evento_rejeitado_na_ingestao_e_ignorado(conn):
    assert receber(conn, evento_dict(event_id="ruim", student_id=""), agora=relogio).status == "rejeitado"
    assert processar_evento(conn, "ruim", agora=relogio) == "ignorado"
    assert status_de(conn) == {"ruim": "rejeitado"}


def test_segunda_execucao_nao_faz_nada(conn):
    receber_todos(conn, tres_eventos())
    processar_pendentes(conn, agora=relogio)
    antes = estado_do_gemeo(conn)

    assert processar_pendentes(conn, agora=relogio) == ResumoProcessamento(0, 0)
    assert estado_do_gemeo(conn) == antes


def test_sem_pendentes_nao_da_erro(conn):
    assert processar_pendentes(conn, agora=relogio) == ResumoProcessamento(0, 0)


def test_sem_relogio_usa_agora_utc(conn):
    receber_todos(conn, tres_eventos()[:1])
    processar_pendentes(conn)
    assert conn.execute("SELECT processado_em FROM eventos_brutos").fetchone()[0].endswith("Z")


def test_erro_de_dominio_rejeita_e_o_lote_segue(conn):
    receber_todos(conn, tres_eventos())
    inserir_pendente_direto(
        conn,
        event_id="e2b",
        exercise_id="exercicio-fantasma",
        occurred_at="2026-03-02T12:01:30Z",
    )

    resumo = processar_pendentes(conn, agora=relogio)

    assert resumo.processados == 3 and resumo.rejeitados == 1
    assert status_de(conn) == {
        "e1": "processado", "e2": "processado", "e3": "processado", "e2b": "rejeitado",
    }
    linha = conn.execute(
        "SELECT motivo_rejeicao FROM eventos_brutos WHERE event_id = 'e2b'"
    ).fetchone()
    assert "exercicio-fantasma" in linha["motivo_rejeicao"]
    assert repositorio.ler_exercicio(conn, "aluno-1", "exercicio-fantasma") is None
    assert not conn.in_transaction


def test_topico_divergente_do_catalogo_e_rejeitado(conn):
    inserir_pendente_direto(conn, event_id="x1", exercise_id="funcoes-3", topic="equacao_1_grau")
    assert processar_evento(conn, "x1", agora=relogio) == "rejeitado"
    assert repositorio.ler_aluno(conn, "aluno-1") is None


def test_excecao_inesperada_desfaz_o_evento_e_sobe(conn, monkeypatch):
    receber_todos(conn, tres_eventos())
    original = consumidor.aplicar_evento
    chamadas = []

    def falha_no_segundo(*args, **kwargs):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise RuntimeError("bug inesperado")
        return original(*args, **kwargs)

    monkeypatch.setattr(consumidor, "aplicar_evento", falha_no_segundo)

    with pytest.raises(RuntimeError, match="bug inesperado"):
        processar_pendentes(conn, agora=relogio)

    assert status_de(conn) == {"e1": "processado", "e2": "pendente", "e3": "pendente"}
    aluno, topicos, exercicio = estado_do_gemeo(conn)
    assert aluno.ultimo_evento_id == "e1" and aluno.respostas == 0
    assert topicos == [] and exercicio is None
    assert not conn.in_transaction


def test_falha_no_salvar_nao_deixa_gemeo_pela_metade(conn, monkeypatch):
    receber_todos(conn, tres_eventos())
    processar_evento(conn, "e1", agora=relogio)

    salvar_original = repositorio.salvar

    def salvar_e_falhar(c, atualizado):
        salvar_original(c, atualizado.model_copy(update={"topico": None}))
        raise sqlite3.OperationalError("disco cheio")

    monkeypatch.setattr(consumidor.repositorio, "salvar", salvar_e_falhar)
    with pytest.raises(sqlite3.OperationalError):
        processar_evento(conn, "e2", agora=relogio)

    assert status_de(conn)["e2"] == "pendente"
    assert repositorio.ler_aluno(conn, "aluno-1").ultimo_evento_id == "e1"


def test_evento_atrasado_levanta_e_fica_pendente(conn):
    receber_todos(conn, tres_eventos()[1:2])  # só e2, 12:01:00
    processar_pendentes(conn, agora=relogio)
    antes = estado_do_gemeo(conn)
    receber(conn, evento_dict(event_id="e0", occurred_at="2026-03-02T12:00:30Z"), agora=relogio)

    with pytest.raises(EventoAtrasado) as info:
        processar_evento(conn, "e0", agora=relogio)

    assert info.value.student_id == "aluno-1"
    assert status_de(conn) == {"e2": "processado", "e0": "pendente"}
    assert estado_do_gemeo(conn) == antes
    assert not conn.in_transaction


def test_empate_de_horario_decide_pelo_event_id(conn):
    mesmo_horario = "2026-03-02T12:00:00Z"
    receber_todos(conn, [evento_dict(event_id="b", occurred_at=mesmo_horario)])
    processar_pendentes(conn, agora=relogio)

    receber(conn, evento_dict(event_id="a", occurred_at=mesmo_horario), agora=relogio)
    with pytest.raises(EventoAtrasado):
        processar_evento(conn, "a", agora=relogio)

    receber(conn, evento_dict(event_id="c", occurred_at=mesmo_horario), agora=relogio)
    assert processar_evento(conn, "c", agora=relogio) == "processado"


def test_alunos_diferentes_sao_independentes(conn):
    receber_todos(conn, tres_eventos("aluno-1") + tres_eventos("aluno-2", prefixo="b"))
    # o horário do aluno-2 nunca "atrasa" o aluno-1 e vice-versa
    receber(
        conn,
        evento_dict(
            event_id="z", student_id="aluno-3", occurred_at="2026-03-02T11:00:00Z"
        ),
        agora=relogio,
    )

    resumo = processar_pendentes(conn, agora=relogio)

    assert resumo.processados == 7
    a1 = estado_do_gemeo(conn, "aluno-1")
    a2 = estado_do_gemeo(conn, "aluno-2")
    assert a1[0].ultimo_evento_id == "e3" and a2[0].ultimo_evento_id == "be3"
    assert a1[1][0].rating_elo == a2[1][0].rating_elo
    assert a1[0].respostas == a2[0].respostas == 2
    assert repositorio.ler_aluno(conn, "aluno-3").respostas == 1
