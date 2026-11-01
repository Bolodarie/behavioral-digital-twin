"""Catálogo de exercícios: estrutura fixa que os outros módulos e testes assumem."""
import dataclasses

import pytest

from catalogo import (
    EXERCICIOS,
    TOPICO_IDS,
    TOPICOS,
    ExercicioCatalogo,
    Topico,
    exercicio_por_id,
    exercicios_do_topico,
)


def test_quatro_topicos_na_ordem():
    assert TOPICO_IDS == (
        "funcoes",
        "equacao_1_grau",
        "equacao_2_grau",
        "sistemas_lineares",
    )
    assert tuple(t.id for t in TOPICOS) == TOPICO_IDS


def test_cada_topico_tem_quatro_exercicios_com_dificuldades_1_2_3_5():
    for topico in TOPICO_IDS:
        exercicios = exercicios_do_topico(topico)
        assert [e.id for e in exercicios] == [f"{topico}-{n}" for n in range(1, 5)]
        assert [e.dificuldade for e in exercicios] == [1, 2, 3, 5]
        assert all(e.topico_id == topico for e in exercicios)


def test_ids_unicos_e_dificuldade_entre_1_e_5():
    ids = [e.id for e in EXERCICIOS]
    assert len(ids) == len(set(ids)) == 16
    assert all(1 <= e.dificuldade <= 5 for e in EXERCICIOS)


def test_exercicio_por_id():
    ex = exercicio_por_id("funcoes-3")
    assert ex is not None
    assert ex.topico_id == "funcoes"
    assert ex.dificuldade == 3
    assert exercicio_por_id("nao-existe") is None


def test_exercicios_de_topico_inexistente_devolve_vazio():
    assert exercicios_do_topico("geometria") == ()


def test_enunciados_em_portugues_nao_vazios():
    assert all(e.enunciado.strip() for e in EXERCICIOS)
    assert all(t.nome.strip() for t in TOPICOS)
    # nenhum enunciado repetido
    assert len({e.enunciado for e in EXERCICIOS}) == len(EXERCICIOS)
    # ao menos um marcador de português por enunciado
    marcadores = ("Resolva", "Determine", "Calcule", "Encontre", "Dada", "Dado", "Qual")
    assert all(any(m in e.enunciado for m in marcadores) for e in EXERCICIOS)


def test_dataclasses_congeladas():
    assert isinstance(TOPICOS[0], Topico)
    assert isinstance(EXERCICIOS[0], ExercicioCatalogo)
    with pytest.raises(dataclasses.FrozenInstanceError):
        TOPICOS[0].nome = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        EXERCICIOS[0].dificuldade = 4  # type: ignore[misc]
