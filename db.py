"""Banco SQLite: schema (design §5), catálogo semeado e abertura de conexões.

Conexões em autocommit (`isolation_level=None`): transações são explícitas
(`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`). A API usa a conexão somente leitura.
"""
import sqlite3
import time
from pathlib import Path

from catalogo import EXERCICIOS, TOPICOS

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "gemeo.db"


class BancoIndisponivel(Exception):
    """O arquivo do banco não existe ou não pôde ser aberto."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS topicos (
    id   TEXT PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exercicios (
    id          TEXT PRIMARY KEY,
    topico_id   TEXT NOT NULL REFERENCES topicos(id),
    enunciado   TEXT NOT NULL,
    dificuldade INTEGER NOT NULL CHECK (dificuldade BETWEEN 1 AND 5)
);

CREATE TABLE IF NOT EXISTS eventos_brutos (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id         TEXT UNIQUE,
    student_id       TEXT,
    exercise_id      TEXT,
    topic            TEXT,
    event_type       TEXT,
    occurred_at      TEXT,
    payload_json     TEXT,
    bruto_json       TEXT NOT NULL,
    recebido_em      TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pendente'
                     CHECK (status IN ('pendente', 'processado', 'rejeitado')),
    motivo_rejeicao  TEXT,
    processado_em    TEXT
);

CREATE INDEX IF NOT EXISTS idx_eventos_status
    ON eventos_brutos (status, occurred_at, event_id);
CREATE INDEX IF NOT EXISTS idx_eventos_aluno
    ON eventos_brutos (student_id, occurred_at, event_id);

CREATE TABLE IF NOT EXISTS gemeo_topico (
    student_id    TEXT NOT NULL,
    topic_id      TEXT NOT NULL REFERENCES topicos(id),
    rating_elo    REAL NOT NULL,
    tentativas    INTEGER NOT NULL,
    acertos       INTEGER NOT NULL,
    atualizado_em TEXT NOT NULL,
    PRIMARY KEY (student_id, topic_id)
);

CREATE TABLE IF NOT EXISTS gemeo_exercicio (
    student_id         TEXT NOT NULL,
    exercise_id        TEXT NOT NULL REFERENCES exercicios(id),
    tentativas         INTEGER NOT NULL,
    acertou_alguma_vez INTEGER NOT NULL,
    PRIMARY KEY (student_id, exercise_id)
);

CREATE TABLE IF NOT EXISTS gemeo_aluno (
    student_id          TEXT PRIMARY KEY,
    velocidade_media_s  REAL,
    taxa_abandono       REAL NOT NULL,
    erros_seguidos      INTEGER NOT NULL,
    desempenho_relativo REAL NOT NULL,
    respostas           INTEGER NOT NULL,
    ultimo_evento_em    TEXT NOT NULL,
    ultimo_evento_id    TEXT,
    atualizado_em       TEXT NOT NULL
);
"""


def _criar_schema_e_catalogo(conn: sqlite3.Connection) -> None:
    """Cria tabelas e popula o catálogo de forma idempotente, numa transação."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        for comando in SCHEMA.split(";"):
            if comando.strip():
                conn.execute(comando)
        conn.executemany(
            "INSERT OR IGNORE INTO topicos (id, nome) VALUES (?, ?)",
            [(t.id, t.nome) for t in TOPICOS],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO exercicios (id, topico_id, enunciado, dificuldade) "
            "VALUES (?, ?, ?, ?)",
            [(e.id, e.topico_id, e.enunciado, e.dificuldade) for e in EXERCICIOS],
        )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


ESPERA_MAXIMA_S = 10.0


def _ativar_wal(conn: sqlite3.Connection) -> None:
    """Liga o modo WAL, tentando de novo se outro processo segura o bloqueio.

    A troca para WAL precisa de bloqueio exclusivo e o `timeout` da conexão não
    a repete de forma confiável; na primeira execução vários processos podem
    abrir o banco ao mesmo tempo.
    """
    limite = time.monotonic() + ESPERA_MAXIMA_S
    espera = 0.005
    while True:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as exc:
            ocupado = "locked" in str(exc) or "busy" in str(exc)
            if not ocupado or time.monotonic() >= limite:
                raise
            time.sleep(espera)
            espera = min(espera * 2, 0.1)


def abrir(caminho: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Abre (criando, se preciso) o banco de escrita, com schema e catálogo prontos.

    Qualquer falha do SQLite na abertura (arquivo corrompido, bloqueio que não
    se resolve) vira `BancoIndisponivel`.
    """
    caminho = Path(caminho)
    conn: sqlite3.Connection | None = None
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(caminho, isolation_level=None, timeout=ESPERA_MAXIMA_S)
        conn.row_factory = sqlite3.Row
        _ativar_wal(conn)
        conn.execute("PRAGMA foreign_keys=ON")
        _criar_schema_e_catalogo(conn)
    except (OSError, sqlite3.Error) as exc:
        if conn is not None:
            conn.close()
        raise BancoIndisponivel(f"não foi possível abrir o banco {caminho}: {exc}") from exc
    except BaseException:
        if conn is not None:
            conn.close()
        raise
    return conn


def abrir_somente_leitura(caminho: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Abre um banco já existente em modo somente leitura (usado pela API)."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise BancoIndisponivel(f"banco não encontrado: {caminho}")
    try:
        conn = sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
    except sqlite3.Error as exc:
        raise BancoIndisponivel(f"não foi possível abrir o banco {caminho}: {exc}") from exc
    return conn
