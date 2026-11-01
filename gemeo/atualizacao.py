"""Atualização do gêmeo por evento (design, seção 7).

Função pura: sem banco, sem relógio e sem alterar os argumentos. Os mesmos
eventos na mesma ordem dão exatamente os mesmos floats, por isso a média móvel
é sempre calculada na forma `x + ALFA * (alvo - x)` e nada é arredondado.
"""
from gemeo.elo import RATING_INICIAL, expectativa, novo_rating, rating_do_exercicio
from modelos import (
    EstadoAluno,
    EstadoAtualizado,
    EstadoExercicio,
    EstadoTopico,
    Evento,
    TipoEvento,
)

ALFA = 0.2


def _media_movel(atual: float, alvo: float) -> float:
    return atual + ALFA * (alvo - atual)


def _aluno_inicial(evento: Evento) -> EstadoAluno:
    return EstadoAluno(
        student_id=evento.student_id,
        velocidade_media_s=None,
        taxa_abandono=0.0,
        erros_seguidos=0,
        desempenho_relativo=0.0,
        respostas=0,
        ultimo_evento_em=evento.occurred_at,
        ultimo_evento_id=evento.event_id,
        atualizado_em=evento.occurred_at,
    )


def _avancar_ultimo_evento(aluno: EstadoAluno, evento: Evento) -> EstadoAluno:
    """Só avança se a chave (horário, id) do evento for maior que a registrada."""
    chave_evento = (evento.occurred_at, evento.event_id)
    if chave_evento > (aluno.ultimo_evento_em, aluno.ultimo_evento_id):
        return aluno.model_copy(
            update={
                "ultimo_evento_em": evento.occurred_at,
                "ultimo_evento_id": evento.event_id,
            }
        )
    return aluno


def _validar_entradas(
    evento: Evento,
    dificuldade: int,
    aluno: EstadoAluno | None,
    topico: EstadoTopico | None,
    exercicio: EstadoExercicio | None,
) -> None:
    """Recusa dificuldade inválida e estados que não pertencem ao evento."""
    if isinstance(dificuldade, bool) or not isinstance(dificuldade, int):
        raise ValueError(f"dificuldade deve ser um inteiro de 1 a 5: {dificuldade!r}")
    rating_do_exercicio(dificuldade)  # levanta ValueError fora de 1..5
    if aluno is not None and aluno.student_id != evento.student_id:
        raise ValueError(
            f"estado do aluno {aluno.student_id!r} não pertence ao evento "
            f"do aluno {evento.student_id!r}"
        )
    if topico is not None:
        if topico.student_id != evento.student_id:
            raise ValueError(
                f"estado do tópico do aluno {topico.student_id!r} não pertence "
                f"ao evento do aluno {evento.student_id!r}"
            )
        if topico.topic_id != evento.topic:
            raise ValueError(
                f"estado do tópico {topico.topic_id!r} não corresponde ao "
                f"tópico do evento {evento.topic!r}"
            )
    if exercicio is not None:
        if exercicio.student_id != evento.student_id:
            raise ValueError(
                f"estado do exercício do aluno {exercicio.student_id!r} não "
                f"pertence ao evento do aluno {evento.student_id!r}"
            )
        if exercicio.exercise_id != evento.exercise_id:
            raise ValueError(
                f"estado do exercício {exercicio.exercise_id!r} não corresponde "
                f"ao exercício do evento {evento.exercise_id!r}"
            )


def aplicar_evento(
    evento: Evento,
    dificuldade: int,
    aluno: EstadoAluno | None,
    topico: EstadoTopico | None,
    exercicio: EstadoExercicio | None,
) -> EstadoAtualizado:
    """Aplica um evento ao estado atual e devolve o novo estado.

    `topico` e `exercicio` do resultado só vêm preenchidos quando o evento os
    altera (apenas `exercicio_respondido`). Levanta `ValueError` se a dificuldade
    não for um inteiro de 1 a 5 (em qualquer tipo de evento) ou se algum estado
    recebido não for do aluno/tópico/exercício do evento.
    """
    _validar_entradas(evento, dificuldade, aluno, topico, exercicio)
    aluno = _avancar_ultimo_evento(
        aluno if aluno is not None else _aluno_inicial(evento), evento
    )

    if evento.event_type is TipoEvento.EXERCICIO_ABANDONADO:
        aluno = aluno.model_copy(
            update={"taxa_abandono": _media_movel(aluno.taxa_abandono, 1.0)}
        )
        return EstadoAtualizado(aluno=_fechar(aluno))

    if evento.event_type is not TipoEvento.EXERCICIO_RESPONDIDO:
        return EstadoAtualizado(aluno=_fechar(aluno))

    acertou = bool(evento.acertou)
    tempo = float(evento.tempo_gasto_s)
    resultado = 1.0 if acertou else 0.0

    if topico is None:
        topico = EstadoTopico(
            student_id=evento.student_id,
            topic_id=evento.topic,
            rating_elo=RATING_INICIAL,
            tentativas=0,
            acertos=0,
            atualizado_em=evento.occurred_at,
        )
    rating_ex = rating_do_exercicio(dificuldade)
    # a expectativa usa o rating de antes da atualização
    esperado = expectativa(topico.rating_elo, rating_ex)
    novo_topico = topico.model_copy(
        update={
            "rating_elo": novo_rating(topico.rating_elo, rating_ex, acertou),
            "tentativas": topico.tentativas + 1,
            "acertos": topico.acertos + (1 if acertou else 0),
            "atualizado_em": evento.occurred_at,
        }
    )

    if exercicio is None:
        novo_exercicio = EstadoExercicio(
            student_id=evento.student_id,
            exercise_id=evento.exercise_id,
            tentativas=1,
            acertou_alguma_vez=acertou,
        )
    else:
        novo_exercicio = exercicio.model_copy(
            update={
                "tentativas": exercicio.tentativas + 1,
                "acertou_alguma_vez": exercicio.acertou_alguma_vez or acertou,
            }
        )

    velocidade = (
        tempo
        if aluno.velocidade_media_s is None
        else _media_movel(aluno.velocidade_media_s, tempo)
    )
    aluno = aluno.model_copy(
        update={
            "velocidade_media_s": velocidade,
            "taxa_abandono": _media_movel(aluno.taxa_abandono, 0.0),
            "erros_seguidos": 0 if acertou else aluno.erros_seguidos + 1,
            "desempenho_relativo": _media_movel(
                aluno.desempenho_relativo, resultado - esperado
            ),
            "respostas": aluno.respostas + 1,
        }
    )
    return EstadoAtualizado(
        aluno=_fechar(aluno), topico=novo_topico, exercicio=novo_exercicio
    )


def _fechar(aluno: EstadoAluno) -> EstadoAluno:
    """`atualizado_em` acompanha o horário do último evento, nunca o relógio real."""
    return aluno.model_copy(update={"atualizado_em": aluno.ultimo_evento_em})
