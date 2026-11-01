"""Testes do Elo (design, seção 7). Função pura: sem banco, sem relógio."""
import pytest

from gemeo.elo import (
    ESCALA,
    K,
    RATING_INICIAL,
    expectativa,
    novo_rating,
    rating_do_exercicio,
)


def test_constantes():
    assert RATING_INICIAL == 1000.0
    assert K == 32.0
    assert ESCALA == 400.0


def test_rating_do_exercicio():
    assert rating_do_exercicio(1) == 800.0
    assert rating_do_exercicio(3) == 1000.0
    assert rating_do_exercicio(5) == 1200.0


@pytest.mark.parametrize("dificuldade", [0, 6])
def test_rating_do_exercicio_fora_da_faixa(dificuldade):
    with pytest.raises(ValueError):
        rating_do_exercicio(dificuldade)


def test_expectativa_valores():
    assert expectativa(1000, 1000) == pytest.approx(0.5)
    assert expectativa(1000, 1200) == pytest.approx(0.24025, abs=1e-4)
    assert expectativa(1200, 1000) == pytest.approx(0.75975, abs=1e-4)


def test_expectativa_simetrica():
    assert expectativa(950, 1150) + expectativa(1150, 950) == pytest.approx(1.0)


def test_novo_rating_acerto_e_erro_iguais():
    assert novo_rating(1000, 1000, True) == pytest.approx(1016.0)
    assert novo_rating(1000, 1000, False) == pytest.approx(984.0)


def test_acerto_dificil_sobe_mais_que_facil():
    ganho_dificil = novo_rating(1000, 1200, True) - 1000
    ganho_facil = novo_rating(1000, 800, True) - 1000
    assert novo_rating(1000, 1200, True) == pytest.approx(1024.312, abs=1e-3)
    assert ganho_dificil > ganho_facil


def test_erro_facil_desce_mais_que_dificil():
    queda_facil = 1000 - novo_rating(1000, 800, False)
    queda_dificil = 1000 - novo_rating(1000, 1200, False)
    assert queda_facil > queda_dificil
