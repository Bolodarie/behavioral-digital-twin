"""Proficiência por aluno×tópico no sistema Elo (design, seção 7).

Função pura: só floats e ints, sem banco e sem relógio. O tempo gasto não
entra na proficiência.
"""

RATING_INICIAL = 1000.0
K = 32.0
ESCALA = 400.0


def rating_do_exercicio(dificuldade: int) -> float:
    """Converte a dificuldade 1..5 do exercício no rating 800..1200 (fixo)."""
    if not 1 <= dificuldade <= 5:
        raise ValueError(f"dificuldade fora de 1..5: {dificuldade}")
    return 800.0 + 100.0 * (dificuldade - 1)


def expectativa(rating_aluno: float, rating_exercicio: float) -> float:
    """Probabilidade esperada de acerto do aluno neste exercício."""
    return 1.0 / (1.0 + 10 ** ((rating_exercicio - rating_aluno) / ESCALA))


def novo_rating(rating_aluno: float, rating_exercicio: float, acertou: bool) -> float:
    """Rating do aluno depois de uma resposta."""
    resultado = 1.0 if acertou else 0.0
    return rating_aluno + K * (resultado - expectativa(rating_aluno, rating_exercicio))
