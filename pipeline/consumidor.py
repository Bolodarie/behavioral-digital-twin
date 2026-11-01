"""Consumo dos eventos pendentes: aplica cada um ao gêmeo, com atomicidade.

Um evento = uma transação (`BEGIN IMMEDIATE` ... `COMMIT`): o estado do gêmeo e
o status do evento mudam juntos ou nenhum dos dois muda.

- `EventoInvalido` (erro de domínio, ex.: exercício fora do catálogo): desfaz a
  transação, marca o evento `rejeitado` com o motivo e o lote segue.
- Evento atrasado (chave `(occurred_at, event_id)` menor que a do aluno):
  levanta `EventoAtrasado` e o evento continua `pendente`. Contrato provisório:
  a US12 troca isso por reconstrução do gêmeo do aluno.
- Qualquer outra exceção (inclusive `ValueError` de `aplicar_evento`, que indica
  bug de programação): desfaz, o evento continua `pendente` e a exceção sobe.

O relógio (`agora`) só carimba `processado_em`; os valores do gêmeo vêm todos do
horário dos eventos.
"""
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

from catalogo import exercicio_por_id
from gemeo import repositorio
from gemeo.atualizacao import aplicar_evento
from modelos import Evento
from pipeline import fila

_FORMATO_TEMPO = "%Y-%m-%dT%H:%M:%SZ"


class EventoInvalido(Exception):
    """O evento não pode ser aplicado (erro de domínio); ele será rejeitado."""


class EventoAtrasado(Exception):
    """O evento é anterior ao último já aplicado ao aluno."""

    def __init__(self, student_id: str, mensagem: str = "") -> None:
        super().__init__(mensagem or f"evento atrasado para o aluno {student_id}")
        self.student_id = student_id


@dataclass
class ResumoProcessamento:
    processados: int
    rejeitados: int
    alunos_reconstruidos: int = 0


@contextmanager
def _transacao(conn: sqlite3.Connection) -> Iterator[None]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def _dificuldade(evento: Evento) -> int:
    exercicio = exercicio_por_id(evento.exercise_id)
    if exercicio is None:
        raise EventoInvalido(f"exercicio inexistente no catalogo: {evento.exercise_id}")
    if exercicio.topico_id != evento.topic:
        raise EventoInvalido(
            f"topic diverge do catalogo: exercicio {evento.exercise_id} "
            f"e do topico {exercicio.topico_id}, nao {evento.topic}"
        )
    return exercicio.dificuldade


def _aplicar_e_salvar(conn: sqlite3.Connection, evento: Evento) -> None:
    dificuldade = _dificuldade(evento)
    aluno = repositorio.ler_aluno(conn, evento.student_id)
    if aluno is not None and (evento.occurred_at, evento.event_id) < (
        aluno.ultimo_evento_em,
        aluno.ultimo_evento_id or "",
    ):
        raise EventoAtrasado(evento.student_id)
    topico = repositorio.ler_topico(conn, evento.student_id, evento.topic)
    exercicio = repositorio.ler_exercicio(conn, evento.student_id, evento.exercise_id)
    repositorio.salvar(
        conn, aplicar_evento(evento, dificuldade, aluno, topico, exercicio)
    )


def _processar_na_transacao(
    conn: sqlite3.Connection, event_id: str, agora_texto: str
) -> str:
    status = fila.status_de(conn, event_id)
    if status is None:
        raise KeyError(event_id)
    if status != "pendente":
        return "ignorado"
    # `buscar` só devolve `None` para linhas sem evento, que nunca estão pendentes
    evento, _ = fila.buscar(conn, event_id)
    _aplicar_e_salvar(conn, evento)
    fila.marcar_processado(conn, event_id, agora_texto)
    return "processado"


def processar_evento(
    conn: sqlite3.Connection,
    event_id: str,
    *,
    agora: Callable[[], datetime] | None = None,
) -> str:
    """Processa um evento: `"processado"`, `"rejeitado"` ou `"ignorado"`.

    `"ignorado"` quando ele já estava processado ou rejeitado. `event_id`
    desconhecido levanta `KeyError`.
    """
    momento = agora() if agora else datetime.now(timezone.utc)
    agora_texto = momento.astimezone(timezone.utc).strftime(_FORMATO_TEMPO)
    try:
        with _transacao(conn):
            return _processar_na_transacao(conn, event_id, agora_texto)
    except EventoInvalido as erro:
        with _transacao(conn):
            fila.marcar_rejeitado(conn, event_id, str(erro))
        return "rejeitado"


def processar_pendentes(
    conn: sqlite3.Connection,
    *,
    agora: Callable[[], datetime] | None = None,
) -> ResumoProcessamento:
    """Processa todos os pendentes em ordem `(occurred_at, event_id)`.

    Uma exceção inesperada ou `EventoAtrasado` interrompe o lote; o que já foi
    processado continua processado e o resto continua pendente.
    """
    resumo = ResumoProcessamento(processados=0, rejeitados=0)
    for evento in fila.listar_pendentes(conn):
        resultado = processar_evento(conn, evento.event_id, agora=agora)
        if resultado == "processado":
            resumo.processados += 1
        elif resultado == "rejeitado":
            resumo.rejeitados += 1
    return resumo
