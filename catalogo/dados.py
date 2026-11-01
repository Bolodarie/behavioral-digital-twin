"""Catálogo de álgebra: 4 tópicos × 4 exercícios (dificuldades 1, 2, 3 e 5).

Os ids são `f"{topico}-{n}"`, com `n` de 1 a 4. Outros módulos e testes
dependem dessa convenção.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Topico:
    id: str
    nome: str


@dataclass(frozen=True)
class ExercicioCatalogo:
    id: str
    topico_id: str
    enunciado: str
    dificuldade: int


DIFICULDADES = (1, 2, 3, 5)

_ENUNCIADOS: dict[str, tuple[str, str, str, str]] = {
    "funcoes": (
        "Dada f(x) = 2x + 1, calcule f(3).",
        "Dada f(x) = x² − 4x + 3, calcule f(5).",
        "Dadas f(x) = 3x − 2 e g(x) = x² + 1, determine f(g(2)).",
        "Determine a função inversa de f(x) = (2x + 3) / (x − 1), para x ≠ 1.",
    ),
    "equacao_1_grau": (
        "Resolva 2x + 3 = 11.",
        "Resolva 5x − 7 = 3x + 9.",
        "Resolva (x + 1) / 2 + (x − 3) / 3 = 4.",
        "Determine o valor de k para que a equação kx + 6 = 3x − k tenha solução x = 2.",
    ),
    "equacao_2_grau": (
        "Resolva x² − 9 = 0.",
        "Resolva x² − 5x + 6 = 0.",
        "Resolva 2x² + 3x − 5 = 0 usando a fórmula de Bhaskara.",
        "Determine os valores de m para que x² − 4x + m = 0 tenha duas raízes reais e distintas.",
    ),
    "sistemas_lineares": (
        "Resolva o sistema x + y = 5 e x − y = 1.",
        "Resolva o sistema 2x + y = 7 e x + 3y = 11.",
        "Resolva o sistema x + y + z = 6, x − y + z = 2 e 2x + y − z = 1.",
        "Encontre o valor de a para que o sistema x + ay = 3 e 2x + 4y = 5 não tenha solução.",
    ),
}

_NOMES = {
    "funcoes": "Funções",
    "equacao_1_grau": "Equação do 1º grau",
    "equacao_2_grau": "Equação do 2º grau",
    "sistemas_lineares": "Sistemas lineares",
}

TOPICOS: tuple[Topico, ...] = tuple(Topico(id=i, nome=n) for i, n in _NOMES.items())
TOPICO_IDS: tuple[str, ...] = tuple(t.id for t in TOPICOS)

EXERCICIOS: tuple[ExercicioCatalogo, ...] = tuple(
    ExercicioCatalogo(
        id=f"{topico}-{n}",
        topico_id=topico,
        enunciado=enunciado,
        dificuldade=dificuldade,
    )
    for topico, enunciados in _ENUNCIADOS.items()
    for n, (enunciado, dificuldade) in enumerate(zip(enunciados, DIFICULDADES), start=1)
)

_POR_ID = {e.id: e for e in EXERCICIOS}


def exercicio_por_id(exercise_id: str) -> ExercicioCatalogo | None:
    """Devolve o exercício do catálogo ou `None` se o id não existe."""
    return _POR_ID.get(exercise_id)


def exercicios_do_topico(topico_id: str) -> tuple[ExercicioCatalogo, ...]:
    """Exercícios do tópico, na ordem do catálogo (vazio se o tópico não existe)."""
    return tuple(e for e in EXERCICIOS if e.topico_id == topico_id)
