"""Recomendação do próximo exercício (design, seção 8).

Função pura: recebe os estados já lidos e o catálogo; não tem banco nem relógio.
"""
from collections.abc import Sequence

import catalogo
from catalogo import ExercicioCatalogo
from gemeo.elo import RATING_INICIAL, expectativa, rating_do_exercicio
from modelos import EstadoTopico, ExercicioRecomendado, Recomendacao

ALVO_PADRAO = 0.70
ALVO_RECUPERACAO = 0.85
LIMIAR_EVASAO = 0.60

_MOTIVO_TOPICO_FRACO = "tópico mais fraco"
_MOTIVO_TOPICO_NOVO = "tópico ainda não tentado"
_MOTIVO_ALVO_PADRAO = "exercício com cerca de 70% de chance de acerto"
_MOTIVO_ALVO_RECUPERACAO = (
    "risco de evasão alto, exercício mais fácil (cerca de 85% de chance de acerto)"
)
_MOTIVO_TUDO_RESOLVIDO = "todos os exercícios do catálogo já foram resolvidos"


def escolher(
    student_id: str,
    topicos: Sequence[EstadoTopico],
    resolvidos: set[str],
    probabilidade_evasao: float,
    *,
    topicos_catalogo: Sequence[str] | None = None,
    exercicios_catalogo: Sequence[ExercicioCatalogo] | None = None,
) -> Recomendacao:
    """Escolhe o tópico mais fraco e, nele, o exercício mais perto do alvo de acerto."""
    ordem_topicos = catalogo.TOPICO_IDS if topicos_catalogo is None else topicos_catalogo
    exercicios = catalogo.EXERCICIOS if exercicios_catalogo is None else exercicios_catalogo

    ratings = {t.topic_id: t.rating_elo for t in topicos}
    pendentes: dict[str, list[ExercicioCatalogo]] = {}
    for ex in exercicios:
        if ex.id not in resolvidos:
            pendentes.setdefault(ex.topico_id, []).append(ex)

    # `min` devolve o primeiro mínimo: o empate fica com a ordem do catálogo.
    candidatos = [t for t in ordem_topicos if t in pendentes]
    if not candidatos:
        return Recomendacao(
            student_id=student_id,
            topico=None,
            exercicio=None,
            expectativa_acerto=None,
            probabilidade_evasao=probabilidade_evasao,
            motivo=_MOTIVO_TUDO_RESOLVIDO,
        )
    topico = min(candidatos, key=lambda t: ratings.get(t, RATING_INICIAL))
    rating = ratings.get(topico, RATING_INICIAL)

    if probabilidade_evasao > LIMIAR_EVASAO:
        alvo, motivo_alvo = ALVO_RECUPERACAO, _MOTIVO_ALVO_RECUPERACAO
    else:
        alvo, motivo_alvo = ALVO_PADRAO, _MOTIVO_ALVO_PADRAO

    def chance(ex: ExercicioCatalogo) -> float:
        return expectativa(rating, rating_do_exercicio(ex.dificuldade))

    escolhido = min(pendentes[topico], key=lambda ex: (abs(chance(ex) - alvo), ex.id))
    motivo_topico = _MOTIVO_TOPICO_FRACO if topico in ratings else _MOTIVO_TOPICO_NOVO
    return Recomendacao(
        student_id=student_id,
        topico=topico,
        exercicio=ExercicioRecomendado(
            id=escolhido.id,
            enunciado=escolhido.enunciado,
            dificuldade=escolhido.dificuldade,
        ),
        expectativa_acerto=chance(escolhido),
        probabilidade_evasao=probabilidade_evasao,
        motivo=f"{motivo_topico}; {motivo_alvo}",
    )
