"""Recebe um evento cru, valida e grava em `eventos_brutos` (design §4 e §5).

Cada chamada é uma transação própria. Duplicado (mesmo `event_id`, qualquer
status) é ignorado; inválido vira linha `rejeitado` com o motivo; o resto
entra como `pendente` para o pipeline processar.
"""
import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from catalogo import exercicio_por_id
from modelos import Evento, ResultadoIngestao

MAX_MOTIVO = 500
_FORMATO_TEMPO = "%Y-%m-%dT%H:%M:%SZ"


def _texto_utc(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).strftime(_FORMATO_TEMPO)


def _event_id_de(dado: Any) -> str | None:
    if isinstance(dado, dict):
        valor = dado.get("event_id")
        if isinstance(valor, str) and valor:
            return valor
    return None


def _bruto_json(dado: Any) -> str:
    try:
        return json.dumps(dado, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # p.ex. chaves de tipos misturados, que `sort_keys` não consegue ordenar
        return json.dumps(repr(dado), ensure_ascii=False)


def _motivo_da_validacao(erro: ValidationError) -> str:
    partes = []
    for e in erro.errors():
        campo = ".".join(str(p) for p in e["loc"]) or "evento"
        partes.append(f"{campo}: {e['msg']}")
    return "; ".join(partes)


def _motivo_do_catalogo(evento: Evento) -> str | None:
    exercicio = exercicio_por_id(evento.exercise_id)
    if exercicio is None:
        return f"exercicio inexistente no catalogo: {evento.exercise_id}"
    if exercicio.topico_id != evento.topic:
        return (
            f"topic diverge do catalogo: exercicio {evento.exercise_id} "
            f"e do topico {exercicio.topico_id}, nao {evento.topic}"
        )
    return None


def _validar(dado: Any) -> tuple[Evento | None, str | None]:
    """Devolve `(evento, None)` se válido ou `(None, motivo)`."""
    if not isinstance(dado, dict):
        return None, "dado nao e um objeto"
    try:
        evento = Evento.model_validate(dado)
    except ValidationError as erro:
        return None, _motivo_da_validacao(erro)
    motivo = _motivo_do_catalogo(evento)
    if motivo is not None:
        return None, motivo
    return evento, None


def receber(
    conn: sqlite3.Connection,
    dado: Any,
    *,
    agora: Callable[[], datetime] | None = None,
) -> ResultadoIngestao:
    """Valida e grava um evento cru; devolve `aceito`, `duplicado` ou `rejeitado`."""
    event_id = _event_id_de(dado)
    evento, motivo = _validar(dado)
    recebido_em = _texto_utc(agora() if agora else datetime.now(timezone.utc))
    bruto = _bruto_json(dado)

    conn.execute("BEGIN IMMEDIATE")
    try:
        if event_id is not None and conn.execute(
            "SELECT 1 FROM eventos_brutos WHERE event_id = ?", (event_id,)
        ).fetchone():
            conn.execute("COMMIT")
            return ResultadoIngestao(status="duplicado", event_id=event_id)

        if evento is None:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO eventos_brutos "
                "(event_id, bruto_json, recebido_em, status, motivo_rejeicao) "
                "VALUES (?, ?, ?, 'rejeitado', ?)",
                (event_id, bruto, recebido_em, motivo[:MAX_MOTIVO]),
            )
        else:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO eventos_brutos "
                "(event_id, student_id, exercise_id, topic, event_type, occurred_at, "
                "payload_json, bruto_json, recebido_em, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente')",
                (
                    evento.event_id,
                    evento.student_id,
                    evento.exercise_id,
                    evento.topic,
                    evento.event_type.value,
                    evento.occurred_at_texto,
                    json.dumps(evento.payload, ensure_ascii=False, sort_keys=True),
                    bruto,
                    recebido_em,
                ),
            )
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise

    if cursor.rowcount == 0:  # outra chamada gravou o mesmo event_id antes
        return ResultadoIngestao(status="duplicado", event_id=event_id)
    if evento is None:
        return ResultadoIngestao(
            status="rejeitado", event_id=event_id, motivo=motivo[:MAX_MOTIVO]
        )
    return ResultadoIngestao(status="aceito", event_id=evento.event_id)
