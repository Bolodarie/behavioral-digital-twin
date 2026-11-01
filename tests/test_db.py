"""Banco SQLite: schema, catálogo semeado, WAL e modo somente leitura."""
import sqlite3
from pathlib import Path

import pytest

import db
from catalogo import EXERCICIOS, TOPICOS

TABELAS = {
    "topicos",
    "exercicios",
    "eventos_brutos",
    "gemeo_topico",
    "gemeo_exercicio",
    "gemeo_aluno",
}


@pytest.fixture
def caminho(tmp_path) -> Path:
    return tmp_path / "pasta_nova" / "teste.db"


@pytest.fixture
def conn(caminho):
    c = db.abrir(caminho)
    yield c
    c.close()


def _inserir_evento(conn, event_id, status="pendente"):
    conn.execute(
        "INSERT INTO eventos_brutos (event_id, student_id, bruto_json, recebido_em, status) "
        "VALUES (?, 'a1', '{}', '2026-01-01T00:00:00Z', ?)",
        (event_id, status),
    )


def test_abrir_cria_as_seis_tabelas(conn):
    nomes = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert nomes == TABELAS


def test_abrir_cria_a_pasta_e_popula_o_catalogo(conn):
    assert conn.execute("SELECT COUNT(*) FROM topicos").fetchone()[0] == len(TOPICOS)
    assert conn.execute("SELECT COUNT(*) FROM exercicios").fetchone()[0] == len(EXERCICIOS)
    linha = conn.execute(
        "SELECT topico_id, dificuldade FROM exercicios WHERE id = 'funcoes-3'"
    ).fetchone()
    assert (linha["topico_id"], linha["dificuldade"]) == ("funcoes", 3)


def test_abrir_e_idempotente(caminho):
    c1 = db.abrir(caminho)
    c1.close()
    c2 = db.abrir(caminho)
    try:
        assert c2.execute("SELECT COUNT(*) FROM topicos").fetchone()[0] == len(TOPICOS)
        assert c2.execute("SELECT COUNT(*) FROM exercicios").fetchone()[0] == len(EXERCICIOS)
    finally:
        c2.close()


def test_conexao_em_autocommit_com_chaves_estrangeiras(conn):
    assert conn.isolation_level is None
    assert not conn.in_transaction
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO exercicios VALUES ('x-1', 'topico_fantasma', 'Resolva.', 1)")


def test_modo_wal(conn):
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_somente_leitura_recusa_escrita(caminho):
    db.abrir(caminho).close()
    ro = db.abrir_somente_leitura(caminho)
    try:
        assert ro.execute("SELECT COUNT(*) FROM topicos").fetchone()[0] == len(TOPICOS)
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("INSERT INTO topicos VALUES ('x', 'X')")
    finally:
        ro.close()


def test_somente_leitura_arquivo_inexistente(tmp_path):
    with pytest.raises(db.BancoIndisponivel):
        db.abrir_somente_leitura(tmp_path / "nao_existe.db")


def test_status_invalido_recusado(conn):
    _inserir_evento(conn, "e1", status="pendente")
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_evento(conn, "e2", status="qualquer")


def test_dificuldade_fora_da_faixa_recusada(conn):
    for d in (0, 6):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO exercicios VALUES (?, 'funcoes', 'Resolva.', ?)", (f"novo-{d}", d)
            )


def test_event_id_unico_e_varios_nulos(conn):
    _inserir_evento(conn, "e1")
    with pytest.raises(sqlite3.IntegrityError):
        _inserir_evento(conn, "e1")
    _inserir_evento(conn, None)
    _inserir_evento(conn, None)
    assert conn.execute("SELECT COUNT(*) FROM eventos_brutos").fetchone()[0] == 3


def test_indices_de_eventos_brutos(conn):
    colunas = {}
    for idx in conn.execute("PRAGMA index_list(eventos_brutos)"):
        if idx["origin"] == "c":  # criados com CREATE INDEX
            colunas[idx["name"]] = [
                r["name"] for r in conn.execute(f"PRAGMA index_info({idx['name']})")
            ]
    assert ["status", "occurred_at", "event_id"] in colunas.values()
    assert ["student_id", "occurred_at", "event_id"] in colunas.values()


def test_gemeo_aluno_tem_ultimo_evento_id(conn):
    colunas = {r["name"] for r in conn.execute("PRAGMA table_info(gemeo_aluno)")}
    assert {"ultimo_evento_em", "ultimo_evento_id", "atualizado_em"} <= colunas


def test_default_db_path_ancorado_na_pasta_do_projeto():
    raiz = Path(db.__file__).resolve().parent
    assert db.DEFAULT_DB_PATH == raiz / "data" / "gemeo.db"
    assert db.DEFAULT_DB_PATH.is_absolute()
