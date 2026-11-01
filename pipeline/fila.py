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


def _evento_reconstruivel(linha: sqlite3.Row) -> Evento:
    """Como `_evento`, mas recusa linhas cujo texto de data não é o canônico.

    Garante que a ordem do SQL (texto) e a do Python (datas) coincidam.
    """
    evento = _evento(linha)
    if evento.occurred_at_texto != linha["occurred_at"]:
        raise ValueError(f"occurred_at fora do formato canonico: {linha['occurred_at']!r}")
    return evento


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


def rejeitar_na_reconstrucao(
    conn: sqlite3.Connection, event_id: str, motivo: str
) -> None:
    """Rejeita de forma permanente um evento não rejeitado (pendente ou processado)."""
    conn.execute(
        "UPDATE eventos_brutos SET status = 'rejeitado', motivo_rejeicao = ?, "
        "processado_em = NULL WHERE event_id = ? AND status != 'rejeitado'",
        (motivo[:MAX_MOTIVO], event_id),
    )


def eventos_do_aluno(conn: sqlite3.Connection, student_id: str) -> list[Evento]:
    """Eventos não rejeitados do aluno (pendentes e processados), em ordem
    `(occurred_at, event_id)`.

    Uma linha que não vira `Evento` (JSON corrompido, campo inválido) é marcada
    `rejeitado`, com o motivo, e fica de fora; não derruba a chamada. A marcação
    acontece na transação de quem chama.
    """
    linhas = conn.execute(
        "SELECT * FROM eventos_brutos WHERE student_id = ? AND status != 'rejeitado' "
        "ORDER BY occurred_at, event_id",
        (student_id,),
    ).fetchall()
    eventos = []
    for linha in linhas:
        try:
            eventos.append(_evento_reconstruivel(linha))
        except (ValueError, TypeError) as erro:  # inclui ValidationError e JSONDecodeError
            rejeitar_na_reconstrucao(
                conn, linha["event_id"], f"linha irreconstruivel na fila: {erro}"
            )
    return eventos


def ids_pendentes_do_aluno(conn: sqlite3.Connection, student_id: str) -> list[str]:
    """`event_id` dos pendentes do aluno."""
    linhas = conn.execute(
        "SELECT event_id FROM eventos_brutos WHERE student_id = ? AND status = 'pendente'",
        (student_id,),
    ).fetchall()
    return [linha["event_id"] for linha in linhas]


def remarcar_processado(
    conn: sqlite3.Connection, event_id: str, agora_texto: str
) -> None:
    """Marca como `processado` um evento não rejeitado, qualquer que fosse o status."""
    conn.execute(
        "UPDATE eventos_brutos SET status = 'processado', processado_em = ? "
        "WHERE event_id = ? AND status != 'rejeitado'",
        (agora_texto, event_id),
    )


def devolver_todos_a_pendente(conn: sqlite3.Connection) -> None:
    """Volta a `pendente` os eventos processados; os rejeitados não mudam."""
    conn.execute(
        "UPDATE eventos_brutos SET status = 'pendente', processado_em = NULL "
        "WHERE status = 'processado'"
    )
