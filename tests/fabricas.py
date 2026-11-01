"""Fábricas de dados para os testes."""
from typing import Any


def evento_dict(
    event_id: str = "e1",
    student_id: str = "aluno-1",
    exercise_id: str = "funcoes-3",
    topic: str = "funcoes",
    event_type: str = "exercicio_respondido",
    occurred_at: str = "2026-03-02T12:00:00Z",
    payload: dict[str, Any] | None = None,
    **sobrescrever: Any,
) -> dict[str, Any]:
    """Monta um evento como o produtor externo o emitiria (dict cru)."""
    if payload is None:
        payload = (
            {"acertou": True, "tempo_gasto_s": 100}
            if event_type == "exercicio_respondido"
            else {}
        )
    evento: dict[str, Any] = {
        "event_id": event_id,
        "student_id": student_id,
        "exercise_id": exercise_id,
        "topic": topic,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "payload": payload,
    }
    evento.update(sobrescrever)
    return evento
