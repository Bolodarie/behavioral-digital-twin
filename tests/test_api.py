import importlib
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import catalogo
import db
from api.main import create_app
from gemeo import atualizacao, evasao, repositorio
from modelos import Evento
from tests.fabricas import evento_dict

AGORA = datetime(2026, 3, 2, 13, 0, 0, tzinfo=timezone.utc)


def _aplicar(conn, bruto: dict) -> None:
    """Aplica um evento ao gêmeo gravado (o que o pipeline faria, sem depender dele)."""
    ev = Evento.model_validate(bruto)
    dificuldade = catalogo.exercicio_por_id(ev.exercise_id).dificuldade
    resultado = atualizacao.aplicar_evento(
        ev,
        dificuldade,
        repositorio.ler_aluno(conn, ev.student_id),
        repositorio.ler_topico(conn, ev.student_id, ev.topic),
        repositorio.ler_exercicio(conn, ev.student_id, ev.exercise_id),
    )
    conn.execute("BEGIN IMMEDIATE")
    repositorio.salvar(conn, resultado)
    conn.execute("COMMIT")


@pytest.fixture
def caminho_db(tmp_path):
    caminho = tmp_path / "gemeo.db"
    conn = db.abrir(caminho)
    _aplicar(conn, evento_dict("e1", event_type="exercicio_iniciado",
                               occurred_at="2026-03-02T12:00:00Z"))
    _aplicar(conn, evento_dict("e2", occurred_at="2026-03-02T12:01:00Z",
                               payload={"acertou": True, "tempo_gasto_s": 100}))
    _aplicar(conn, evento_dict("e3", occurred_at="2026-03-02T12:02:00Z",
                               payload={"acertou": False, "tempo_gasto_s": 50}))
    _aplicar(conn, evento_dict("e4", student_id="so-iniciou",
                               event_type="exercicio_iniciado",
                               occurred_at="2026-03-02T12:30:00Z"))
    conn.close()
    return caminho


@pytest.fixture
def client(caminho_db):
    return TestClient(create_app(caminho_db, agora=lambda: AGORA))


def _dump(caminho) -> dict[str, list]:
    conn = db.abrir_somente_leitura(caminho)
    try:
        tabelas = [
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        ]
        return {
            t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY 1, 2")]
            for t in tabelas
        }
    finally:
        conn.close()


def test_saude_ok(client):
    r = client.get("/saude")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_saude_sem_banco_da_503(tmp_path):
    c = TestClient(create_app(tmp_path / "nao_existe.db", agora=lambda: AGORA))
    assert c.get("/saude").status_code == 503
    assert c.get("/alunos/aluno-1/gemeo").status_code == 503


def test_sqlite_sem_tabelas_do_gemeo_da_503(tmp_path):
    estranho = tmp_path / "estranho.db"
    outro = sqlite3.connect(estranho)
    outro.execute("CREATE TABLE outra (x INTEGER)")
    outro.commit()
    outro.close()
    c = TestClient(create_app(estranho, agora=lambda: AGORA))
    for caminho in ("/saude", "/alunos/x/gemeo", "/alunos/x/recomendacao"):
        r = c.get(caminho)
        assert r.status_code == 503, caminho
        assert r.json() == {"detail": "banco indisponivel"}


@pytest.mark.parametrize("student_id", ["fantasma", "com espaco", "a%2Fb", "x'; DROP--", "%C3%A7"])
def test_aluno_desconhecido_404_nos_dois_endpoints(client, student_id):
    for caminho in ("gemeo", "recomendacao"):
        r = client.get(f"/alunos/{student_id}/{caminho}")
        assert r.status_code == 404
        if "%2F" not in student_id:
            assert r.json() == {"detail": "aluno nao encontrado"}


def test_gemeo_formato_e_valores(client, caminho_db):
    r = client.get("/alunos/aluno-1/gemeo")
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) == {
        "student_id", "ultimo_evento_em", "velocidade_media_s",
        "probabilidade_evasao", "topicos",
    }
    assert corpo["student_id"] == "aluno-1"
    assert datetime.fromisoformat(corpo["ultimo_evento_em"].replace("Z", "+00:00")) == (
        datetime(2026, 3, 2, 12, 2, 0, tzinfo=timezone.utc)
    )
    assert corpo["velocidade_media_s"] == pytest.approx(90.0)
    assert len(corpo["topicos"]) == 1
    topico = corpo["topicos"][0]
    assert set(topico) == {"topic_id", "rating_elo", "tentativas", "acertos"}
    assert topico["topic_id"] == "funcoes"
    assert topico["rating_elo"] == pytest.approx(999.263, abs=1e-3)
    assert (topico["tentativas"], topico["acertos"]) == (2, 1)

    conn = db.abrir_somente_leitura(caminho_db)
    try:
        estado = repositorio.ler_aluno(conn, "aluno-1")
    finally:
        conn.close()
    assert corpo["probabilidade_evasao"] == evasao.probabilidade_evasao(estado, AGORA)


def test_gemeo_topicos_ordenados(caminho_db):
    conn = db.abrir(caminho_db)
    _aplicar(conn, evento_dict("e5", exercise_id="equacao_1_grau-1", topic="equacao_1_grau",
                               occurred_at="2026-03-02T12:03:00Z"))
    conn.close()
    c = TestClient(create_app(caminho_db, agora=lambda: AGORA))
    ids = [t["topic_id"] for t in c.get("/alunos/aluno-1/gemeo").json()["topicos"]]
    assert ids == sorted(ids) == ["equacao_1_grau", "funcoes"]


def test_aluno_so_com_iniciado(client):
    g = client.get("/alunos/so-iniciou/gemeo")
    assert g.status_code == 200
    assert g.json()["topicos"] == []
    assert g.json()["velocidade_media_s"] is None

    r = client.get("/alunos/so-iniciou/recomendacao")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["topico"] == "funcoes"
    assert corpo["exercicio"] is not None


def test_recomendacao_formato(client):
    r = client.get("/alunos/aluno-1/recomendacao")
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo) == {
        "student_id", "topico", "exercicio", "expectativa_acerto",
        "probabilidade_evasao", "motivo",
    }
    assert corpo["student_id"] == "aluno-1"
    assert set(corpo["exercicio"]) == {"id", "enunciado", "dificuldade"}
    assert catalogo.exercicio_por_id(corpo["exercicio"]["id"]).enunciado == (
        corpo["exercicio"]["enunciado"]
    )
    assert 0.0 < corpo["expectativa_acerto"] < 1.0
    assert isinstance(corpo["motivo"], str) and corpo["motivo"]


@pytest.mark.parametrize("aluno", ["aluno-1", "so-iniciou"])
def test_motivo_acompanha_o_limiar_de_evasao(caminho_db, aluno):
    for dias in (0, 1, 5, 30):
        agora = AGORA + timedelta(days=dias)
        c = TestClient(create_app(caminho_db, agora=lambda: agora))
        corpo = c.get(f"/alunos/{aluno}/recomendacao").json()
        assert ("risco de evasão alto" in corpo["motivo"]) == (
            corpo["probabilidade_evasao"] > 0.60
        )


def test_evasao_cresce_com_o_tempo_sem_evento(caminho_db):
    def prob(dias: int) -> float:
        agora = AGORA + timedelta(days=dias)
        c = TestClient(create_app(caminho_db, agora=lambda: agora))
        return c.get("/alunos/aluno-1/gemeo").json()["probabilidade_evasao"]

    assert prob(30) > prob(0)


def test_api_nao_altera_o_banco(client, caminho_db):
    antes = _dump(caminho_db)
    for aluno in ("aluno-1", "so-iniciou", "fantasma"):
        client.get(f"/alunos/{aluno}/gemeo")
        client.get(f"/alunos/{aluno}/recomendacao")
    client.get("/saude")
    assert _dump(caminho_db) == antes


def test_docs_disponivel(client):
    assert client.get("/docs").status_code == 200


def test_relogio_do_ambiente(monkeypatch, caminho_db):
    import api.main as principal

    monkeypatch.setenv("GEMEO_DB", str(caminho_db))
    try:
        monkeypatch.setenv("GEMEO_AGORA", "2026-03-02T13:00:00Z")
        modulo = importlib.reload(principal)
        corpo = TestClient(modulo.app).get("/alunos/aluno-1/gemeo").json()
        conn = db.abrir_somente_leitura(caminho_db)
        try:
            esperado = evasao.probabilidade_evasao(repositorio.ler_aluno(conn, "aluno-1"), AGORA)
        finally:
            conn.close()
        assert corpo["probabilidade_evasao"] == esperado

        for invalido in ("ontem", "2026-03-02T13:00:00"):  # texto solto; sem fuso
            monkeypatch.setenv("GEMEO_AGORA", invalido)
            with pytest.raises(ValueError):
                importlib.reload(principal)
    finally:
        monkeypatch.delenv("GEMEO_AGORA", raising=False)
        monkeypatch.delenv("GEMEO_DB", raising=False)
        importlib.reload(principal)
