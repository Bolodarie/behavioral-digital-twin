"""Consumo dos eventos pendentes: aplica cada um ao gêmeo, com atomicidade.

Um evento = uma transação (`BEGIN IMMEDIATE` ... `COMMIT`): o estado do gêmeo e
o status do evento mudam juntos ou nenhum dos dois muda.

- `EventoInvalido` (erro de domínio, ex.: exercício fora do catálogo): desfaz a
  transação, marca o evento `rejeitado` com o motivo e o lote segue.
- Evento atrasado (chave `(occurred_at, event_id)` menor que a do aluno):
  `processar_evento` levanta `EventoAtrasado` (o evento continua `pendente`);
  `processar_pendentes` o trata reconstruindo o gêmeo daquele aluno com todos os
  eventos dele em ordem cronológica. Assim a ordem de chegada nunca muda o
  resultado: o gêmeo é sempre o do processamento em ordem `(occurred_at, event_id)`.
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


def _agora_texto(agora: Callable[[], datetime] | None) -> str:
    momento = agora() if agora else datetime.now(timezone.utc)
    return momento.astimezone(timezone.utc).strftime(_FORMATO_TEMPO)


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
    agora_texto = _agora_texto(agora)
    try:
        with _transacao(conn):
            return _processar_na_transacao(conn, event_id, agora_texto)
    except EventoInvalido as erro:
        with _transacao(conn):
            fila.marcar_rejeitado(conn, event_id, str(erro))
        return "rejeitado"


def _reconstruir_na_transacao(
    conn: sqlite3.Connection, student_id: str, agora_texto: str
) -> tuple[int, int, int]:
    """Refaz o gêmeo do aluno; devolve `(aplicados, pendentes_processados,
    pendentes_rejeitados)`. Quem chama abre e fecha a transação."""
    pendentes = fila.ids_pendentes_do_aluno(conn, student_id)
    repositorio.apagar_aluno(conn, student_id)
    aplicados = 0
    for evento in fila.eventos_do_aluno(conn, student_id):
        try:
            _aplicar_e_salvar(conn, evento)
        except EventoInvalido as erro:
            fila.rejeitar_na_reconstrucao(conn, evento.event_id, str(erro))
            continue
        fila.remarcar_processado(conn, evento.event_id, agora_texto)
        aplicados += 1
    estados = [fila.status_de(conn, event_id) for event_id in pendentes]
    return aplicados, estados.count("processado"), estados.count("rejeitado")


def _reconstruir(
    conn: sqlite3.Connection,
    student_id: str,
    agora: Callable[[], datetime] | None,
) -> tuple[int, int, int]:
    with _transacao(conn):
        return _reconstruir_na_transacao(conn, student_id, _agora_texto(agora))


def reconstruir_aluno(
    conn: sqlite3.Connection,
    student_id: str,
    *,
    agora: Callable[[], datetime] | None = None,
) -> int:
    """Apaga o gêmeo do aluno e reaplica todos os eventos dele, em ordem.

    Uma transação só: ou o gêmeo e os status mudam juntos, ou nada muda.
    Eventos rejeitados ficam de fora; um `EventoInvalido` durante a
    reconstrução rejeita o evento de forma permanente e a reconstrução segue.
    Todos os aplicados ficam `processado` (com `processado_em` renovado).
    Devolve quantos eventos foram aplicados. Não toca em outros alunos.
    """
    return _reconstruir(conn, student_id, agora)[0]


def processar_pendentes(
    conn: sqlite3.Connection,
    *,
    agora: Callable[[], datetime] | None = None,
) -> ResumoProcessamento:
    """Processa todos os pendentes em ordem `(occurred_at, event_id)`.

    Um evento atrasado faz o gêmeo do aluno ser reconstruído (contado uma vez
    por aluno em `alunos_reconstruidos`); os demais pendentes dele já saem
    processados da reconstrução e são pulados pela checagem de status. Uma
    exceção inesperada interrompe o lote; o que já foi processado continua
    processado e o resto continua pendente.
    """
    resumo = ResumoProcessamento(processados=0, rejeitados=0)
    reconstruidos: set[str] = set()
    for evento in fila.listar_pendentes(conn):
        try:
            resultado = processar_evento(conn, evento.event_id, agora=agora)
        except EventoAtrasado as atraso:
            _, processados, rejeitados = _reconstruir(conn, atraso.student_id, agora)
            resumo.processados += processados
            resumo.rejeitados += rejeitados
            if atraso.student_id not in reconstruidos:
                reconstruidos.add(atraso.student_id)
                resumo.alunos_reconstruidos += 1
            continue
        if resultado == "processado":
            resumo.processados += 1
        elif resultado == "rejeitado":
            resumo.rejeitados += 1
    return resumo


def reprocessar_tudo(
    conn: sqlite3.Connection,
    *,
    agora: Callable[[], datetime] | None = None,
) -> ResumoProcessamento:
    """Apaga todo o gêmeo, devolve os não rejeitados a `pendente` e reprocessa.

    O reinício (apagar o gêmeo e devolver os eventos a `pendente`) é uma
    transação só, para nunca ficar gêmeo vazio com eventos "processados". O
    reprocessamento em si roda evento a evento, como `processar_pendentes`: se
    for interrompido, o gêmeo é um prefixo consistente e uma nova execução de
    `processar_pendentes` continua de onde parou.
    """
    with _transacao(conn):
        repositorio.apagar_tudo(conn)
        fila.devolver_todos_a_pendente(conn)
    return processar_pendentes(conn, agora=agora)
