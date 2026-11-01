"""Fila de eventos: SQL sobre `eventos_brutos` (design §5 e §6).

Só lê e marca linhas; não decide nada do domínio e não abre transação (quem
chama é dono da fronteira). Datas ficam como `YYYY-MM-DDTHH:MM:SSZ`.
"""
import json
import sqlite3

from modelos import Evento

MAX_MOTIVO = 500


def _evento(linha: sqlite3.Row) -> Evento:
    return Evento(
        event_id=linha["event_id"],
        student_id=linha["student_id"],
        exercise_id=linha["exercise_id"],
        topic=linha["topic"],
        event_type=linha["event_type"],
        occurred_at=linha["occurred_at"],
        payload=json.loads(linha["payload_json"]),
    )


def listar_pendentes(conn: sqlite3.Connection) -> list[Evento]:
    """Eventos pendentes na ordem `(occurred_at, event_id)`."""
    linhas = conn.execute(
        "SELECT * FROM eventos_brutos WHERE status = 'pendente' "
        "ORDER BY occurred_at, event_id"
    ).fetchall()
    return [_evento(linha) for linha in linhas]


def status_de(conn: sqlite3.Connection, event_id: str) -> str | None:
    """Status da linha, ou `None` se o `event_id` não existe."""
    linha = conn.execute(
        "SELECT status FROM eventos_brutos WHERE event_id = ?", (event_id,)
    ).fetchone()
    return linha["status"] if linha else None


def buscar(conn: sqlite3.Connection, event_id: str) -> tuple[Evento, str] | None:
    """`(evento, status)` ou `None` se não há linha com evento utilizável.

    Linhas rejeitadas já na ingestão não guardam os campos do evento e também
    devolvem `None`; para distingui-las de um id desconhecido use `status_de`.
    """
    linha = conn.execute(
        "SELECT * FROM eventos_brutos WHERE event_id = ?", (event_id,)
    ).fetchone()
    if linha is None or linha["student_id"] is None:
        return None
    return _evento(linha), linha["status"]


def marcar_processado(
    conn: sqlite3.Connection, event_id: str, agora_texto: str
) -> None:
    conn.execute(
        "UPDATE eventos_brutos SET status = 'processado', processado_em = ? "
        "WHERE event_id = ? AND status = 'pendente'",
        (agora_texto, event_id),
    )


def marcar_rejeitado(conn: sqlite3.Connection, event_id: str, motivo: str) -> None:
    conn.execute(
        "UPDATE eventos_brutos SET status = 'rejeitado', motivo_rejeicao = ? "
        "WHERE event_id = ? AND status = 'pendente'",
        (motivo[:MAX_MOTIVO], event_id),
    )
