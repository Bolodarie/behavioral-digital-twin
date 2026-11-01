"""Testes de `scripts.estatistica` (correlação de Spearman)."""
import pytest

from scripts.estatistica import spearman


def test_correlacao_perfeita_positiva():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)


def test_correlacao_perfeita_negativa():
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_empates_usam_postos_medios():
    assert spearman([1, 2, 2, 3], [1, 3, 2, 4]) == pytest.approx(0.9487, abs=1e-3)


def test_tamanhos_diferentes_levantam_erro():
    with pytest.raises(ValueError):
        spearman([1, 2, 3], [1, 2])


def test_menos_de_dois_pontos_levanta_erro():
    with pytest.raises(ValueError):
        spearman([1], [1])


def test_serie_constante_nao_tem_correlacao_definida():
    with pytest.raises(ValueError):
        spearman([1, 1, 1], [1, 2, 3])
