"""Ingestão: validação, duplicados e gravação em `eventos_brutos`."""
import json
from datetime import datetime, timezone

import pytest

import db
from ingestao.receber import receber
from tests.fabricas import evento_dict

AGORA = datetime(2026, 3, 5, 8, 30, 0, tzinfo=timezone.utc)


def relogio():
    return AGORA


@pytest.fixture
def conn(tmp_path):
    c = db.abrir(tmp_path / "t.db")
    yield c
    c.close()


def linhas(conn):
    return conn.execute("SELECT * FROM eventos_brutos ORDER BY seq").fetchall()


def test_aceito_grava_pendente(conn):
    dado = evento_dict(occurred_at="2026-03-02T12:00:00Z")
    r = receber(conn, dado, agora=relogio)
    assert (r.status, r.event_id, r.motivo) == ("aceito", "e1", None)
    (linha,) = linhas(conn)
    assert linha["status"] == "pendente"
    assert linha["event_id"] == "e1"
    assert linha["student_id"] == "aluno-1"
    assert linha["exercise_id"] == "funcoes-3"
    assert linha["topic"] == "funcoes"
    assert linha["event_type"] == "exercicio_respondido"
    assert linha["occurred_at"] == "2026-03-02T12:00:00Z"
    assert json.loads(linha["payload_json"]) == dado["payload"]
    assert json.loads(linha["bruto_json"]) == dado
    assert linha["recebido_em"] == "2026-03-05T08:30:00Z"
    assert linha["motivo_rejeicao"] is None
    assert linha["processado_em"] is None


def test_aceito_sem_relogio_usa_agora_utc(conn):
    receber(conn, evento_dict())
    assert linhas(conn)[0]["recebido_em"].endswith("Z")


def test_duplicado_nao_grava_de_novo(conn):
    assert receber(conn, evento_dict(), agora=relogio).status == "aceito"
    r = receber(conn, evento_dict(payload={"acertou": False, "tempo_gasto_s": 5}), agora=relogio)
    assert (r.status, r.event_id) == ("duplicado", "e1")
    (linha,) = linhas(conn)
    assert json.loads(linha["payload_json"])["tempo_gasto_s"] == 100


def test_reenvio_de_rejeitado_com_mesmo_event_id_e_duplicado(conn):
    ruim = evento_dict(event_id="x", payload={"acertou": "true", "tempo_gasto_s": 10})
    assert receber(conn, ruim, agora=relogio).status == "rejeitado"
    r = receber(conn, evento_dict(event_id="x"), agora=relogio)
    assert r.status == "duplicado"
    (linha,) = linhas(conn)
    assert linha["status"] == "rejeitado"


def test_duplicado_de_aceito_vale_mesmo_se_o_segundo_for_invalido(conn):
    receber(conn, evento_dict(), agora=relogio)
    r = receber(conn, evento_dict(student_id=""), agora=relogio)
    assert r.status == "duplicado"
    assert len(linhas(conn)) == 1


@pytest.mark.parametrize(
    "dado, trecho",
    [
        (evento_dict(occurred_at="2026-03-02T12:00:00"), "occurred_at"),
        (evento_dict(payload={"acertou": True, "tempo_gasto_s": 0}), "tempo_gasto_s"),
        (evento_dict(payload={"acertou": "true", "tempo_gasto_s": 10}), "acertou"),
        (evento_dict(payload={"acertou": True, "tempo_gasto_s": 10, "x": 1}), "x: extra inputs"),
        (evento_dict(event_type="exercicio_iniciado", payload={"a": 1}), "payload"),
        (evento_dict(student_id=""), "student_id"),
        (evento_dict(exercise_id="funcoes-99"), "exerc"),
        (evento_dict(topic="sistemas_lineares"), "topic"),
        (evento_dict(extra="oi"), "extra"),
    ],
)
def test_rejeicoes_gravam_linha_rejeitado(conn, dado, trecho):
    r = receber(conn, dado, agora=relogio)
    assert r.status == "rejeitado"
    assert r.event_id == "e1"
    assert trecho in r.motivo.lower()
    assert len(r.motivo) <= 500
    (linha,) = linhas(conn)
    assert linha["status"] == "rejeitado"
    assert linha["event_id"] == "e1"
    assert linha["motivo_rejeicao"] == r.motivo
    assert json.loads(linha["bruto_json"]) == dado
    assert linha["recebido_em"] == "2026-03-05T08:30:00Z"


def test_sem_event_id_grava_rejeitado_com_event_id_nulo(conn):
    dado = evento_dict()
    del dado["event_id"]
    for _ in range(2):
        r = receber(conn, dado, agora=relogio)
        assert r.status == "rejeitado"
        assert r.event_id is None
    rows = linhas(conn)
    assert len(rows) == 2
    assert all(l["event_id"] is None and l["status"] == "rejeitado" for l in rows)


@pytest.mark.parametrize("dado", [None, [1, 2], "texto", 42])
def test_dado_que_nao_e_objeto(conn, dado):
    r = receber(conn, dado, agora=relogio)
    assert r.status == "rejeitado"
    assert r.event_id is None
    assert r.motivo == "dado nao e um objeto"
    (linha,) = linhas(conn)
    assert linha["status"] == "rejeitado"
    assert json.loads(linha["bruto_json"]) == dado


def test_event_id_que_nao_e_texto_vira_rejeitado_sem_event_id(conn):
    r = receber(conn, evento_dict(event_id=7), agora=relogio)
    assert r.status == "rejeitado"
    assert r.event_id is None
    assert linhas(conn)[0]["event_id"] is None


def test_chaves_misturadas_nao_derrubam_a_gravacao(conn):
    r = receber(conn, {1: "a", "b": 2}, agora=relogio)
    assert r.status == "rejeitado"
    assert len(linhas(conn)) == 1


def test_motivo_longo_e_truncado(conn):
    dado = evento_dict(payload={f"k{i}": i for i in range(200)})
    r = receber(conn, dado, agora=relogio)
    assert r.status == "rejeitado"
    assert len(r.motivo) == 500
    assert linhas(conn)[0]["motivo_rejeicao"] == r.motivo


@pytest.mark.parametrize(
    "ocorrido, esperado",
    [
        ("2026-03-02T09:00:00-03:00", "2026-03-02T12:00:00Z"),
        ("2026-03-02T12:00:00.987654Z", "2026-03-02T12:00:00Z"),
    ],
)
def test_offset_nao_utc_e_normalizado_na_gravacao(conn, ocorrido, esperado):
    assert receber(conn, evento_dict(occurred_at=ocorrido), agora=relogio).status == "aceito"
    assert linhas(conn)[0]["occurred_at"] == esperado


def test_transacao_nao_fica_aberta(conn):
    receber(conn, evento_dict(), agora=relogio)
    receber(conn, evento_dict(event_id="e2", topic="x"), agora=relogio)
    assert not conn.in_transaction


def profundo_dict(n=5000):
    raiz: dict = {}
    atual = raiz
    for _ in range(n):
        atual["k"] = {}
        atual = atual["k"]
    return raiz


def profundo_lista(n=5000):
    raiz: list = []
    atual = raiz
    for _ in range(n):
        novo: list = []
        atual.append(novo)
        atual = novo
    return raiz


def bruto_valido(linha):
    """`bruto_json` sempre é JSON válido e codificável em UTF-8."""
    linha["bruto_json"].encode("utf-8")
    return json.loads(linha["bruto_json"])


@pytest.mark.parametrize(
    "dado",
    [
        evento_dict(extra=profundo_dict()),
        evento_dict(extra=profundo_lista()),
        profundo_lista(),
        profundo_dict(),
    ],
    ids=["extra-dict", "extra-lista", "lista", "dict"],
)
def test_aninhamento_profundo_vira_rejeitado(conn, dado):
    r = receber(conn, dado, agora=relogio)
    assert r.status == "rejeitado"
    (linha,) = linhas(conn)
    assert linha["status"] == "rejeitado"
    bruto_valido(linha)
    assert not conn.in_transaction


def test_surrogate_no_event_id_vira_rejeitado_sem_event_id(conn):
    r = receber(conn, evento_dict(event_id="a\ud800b"), agora=relogio)
    assert r.status == "rejeitado"
    assert r.event_id is None
    (linha,) = linhas(conn)
    assert linha["event_id"] is None
    assert linha["status"] == "rejeitado"
    assert bruto_valido(linha)["event_id"] == "a\ud800b"


def test_surrogate_no_student_id_vira_rejeitado(conn):
    r = receber(conn, evento_dict(student_id="\ud800"), agora=relogio)
    assert r.status == "rejeitado"
    assert r.event_id == "e1"
    assert "caracteres invalidos" in r.motivo
    (linha,) = linhas(conn)
    assert linha["status"] == "rejeitado"
    assert linha["student_id"] is None
    assert linha["motivo_rejeicao"] == r.motivo
    bruto_valido(linha)


@pytest.mark.parametrize(
    "dado",
    [
        evento_dict(extra="\ud800"),
        evento_dict(payload={"acertou": True, "tempo_gasto_s": 10, "x": "\ud800"}),
        evento_dict(payload={"acertou": True, "tempo_gasto_s": 10, "\ud800": 1}),
        evento_dict(exercise_id="\ud800"),
        evento_dict(topic="\ud800"),
        evento_dict(occurred_at="\ud800"),
        evento_dict(event_type="\ud800"),
        {"\ud800": 1},
    ],
)
def test_surrogate_em_outros_campos_vira_rejeitado(conn, dado):
    r = receber(conn, dado, agora=relogio)
    assert r.status == "rejeitado"
    (linha,) = linhas(conn)
    assert linha["status"] == "rejeitado"
    linha["motivo_rejeicao"].encode("utf-8")
    bruto_valido(linha)


def test_relogio_que_levanta_propaga_sem_transacao_nem_linha(conn):
    def quebrado():
        raise RuntimeError("relogio quebrado")

    with pytest.raises(RuntimeError, match="relogio quebrado"):
        receber(conn, evento_dict(), agora=quebrado)
    assert not conn.in_transaction
    assert linhas(conn) == []


def test_insert_que_falha_desfaz_a_transacao_e_propaga(conn):
    conn.execute(
        "CREATE TRIGGER falha BEFORE INSERT ON eventos_brutos "
        "BEGIN SELECT RAISE(ABORT, 'falha simulada'); END"
    )
    with pytest.raises(Exception, match="falha simulada"):
        receber(conn, evento_dict(), agora=relogio)
    assert not conn.in_transaction
    assert linhas(conn) == []

    conn.execute("DROP TRIGGER falha")
    assert receber(conn, evento_dict(), agora=relogio).status == "aceito"
    assert len(linhas(conn)) == 1
