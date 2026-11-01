"""Recomendação: função pura, sem banco e sem relógio."""
from datetime import datetime, timezone

import pytest

from catalogo import ExercicioCatalogo
from gemeo.elo import expectativa, rating_do_exercicio
from modelos import EstadoTopico
from recomendacao.escolher import (
    ALVO_PADRAO,
    ALVO_RECUPERACAO,
    LIMIAR_EVASAO,
    escolher,
)

AGORA = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)


def _ex(topico: str, dificuldade: int, id: str | None = None) -> ExercicioCatalogo:
    return ExercicioCatalogo(
        id=id or f"{topico}-{dificuldade}",
        topico_id=topico,
        enunciado=f"Enunciado {topico}-{dificuldade}",
        dificuldade=dificuldade,
    )


CATALOGO = [_ex("a", 1), _ex("a", 2), _ex("a", 4), _ex("b", 2), _ex("b", 4), _ex("b", 5)]
TOPICOS = ["a", "b"]


def _estado(topico: str, rating: float) -> EstadoTopico:
    return EstadoTopico(
        student_id="s1",
        topic_id=topico,
        rating_elo=rating,
        tentativas=3,
        acertos=1,
        atualizado_em=AGORA,
    )


def _escolher(estados, resolvidos=frozenset(), evasao=0.0, catalogo=CATALOGO, topicos=TOPICOS):
    return escolher(
        "s1",
        estados,
        set(resolvidos),
        evasao,
        topicos_catalogo=topicos,
        exercicios_catalogo=catalogo,
    )


# Aluno com `b` como tópico mais fraco (1200 < 1300), dificuldades 2, 4 e 5.
ESTADOS_B_FRACO = [_estado("a", 1300.0), _estado("b", 1200.0)]


def test_constantes_do_design():
    assert (ALVO_PADRAO, ALVO_RECUPERACAO, LIMIAR_EVASAO) == (0.70, 0.85, 0.60)


def test_escolhe_o_topico_de_menor_rating():
    r = _escolher([_estado("a", 1100.0), _estado("b", 900.0)])
    assert r.topico == "b"
    assert "tópico mais fraco" in r.motivo


def test_topico_nao_tentado_conta_como_1000():
    r = _escolher([_estado("a", 1100.0)])
    assert r.topico == "b"
    assert "ainda não tentado" in r.motivo


def test_empate_de_topico_vai_para_a_ordem_do_catalogo():
    estados = [_estado("a", 1000.0), _estado("b", 1000.0)]
    assert _escolher(estados).topico == "a"
    assert _escolher(estados, topicos=["b", "a"]).topico == "b"


def test_exercicio_mais_perto_de_70_por_cento():
    r = _escolher(ESTADOS_B_FRACO)
    assert r.topico == "b"
    assert r.exercicio is not None
    assert r.exercicio.dificuldade == 4
    assert r.exercicio.id == "b-4"
    assert r.exercicio.enunciado == "Enunciado b-4"
    assert r.expectativa_acerto == pytest.approx(0.64006, abs=1e-4)
    assert r.expectativa_acerto == pytest.approx(
        expectativa(1200.0, rating_do_exercicio(4))
    )
    assert "cerca de 70% de chance de acerto" in r.motivo


def test_evasao_alta_sobe_o_alvo_para_85():
    r = _escolher(ESTADOS_B_FRACO, evasao=0.7)
    assert r.exercicio is not None
    assert r.exercicio.dificuldade == 2
    assert r.expectativa_acerto == pytest.approx(0.8490, abs=1e-3)
    assert r.probabilidade_evasao == 0.7
    assert "risco de evasão alto" in r.motivo
    assert "cerca de 85% de chance de acerto" in r.motivo


def test_limiar_e_estrito():
    r = _escolher(ESTADOS_B_FRACO, evasao=0.60)
    assert r.exercicio is not None
    assert r.exercicio.dificuldade == 4
    assert "risco de evasão alto" not in r.motivo


def test_exercicios_resolvidos_sao_excluidos():
    r = _escolher(ESTADOS_B_FRACO, resolvidos={"b-4"})
    assert r.exercicio is not None
    # entre d2 (0.849) e d5 (0.5), o mais perto de 0.70 é d2 (|0.149| < |0.200|)
    assert r.exercicio.id == "b-2"


def test_topico_todo_resolvido_e_pulado():
    r = _escolher(ESTADOS_B_FRACO, resolvidos={"b-2", "b-4", "b-5"})
    assert r.topico == "a"
    assert r.exercicio is not None
    assert r.exercicio.id.startswith("a-")


def test_tudo_resolvido_devolve_none():
    r = _escolher(ESTADOS_B_FRACO, resolvidos={e.id for e in CATALOGO}, evasao=0.3)
    assert r.topico is None
    assert r.exercicio is None
    assert r.expectativa_acerto is None
    assert r.probabilidade_evasao == 0.3
    assert "todos" in r.motivo


def test_empate_de_exercicio_vai_para_o_menor_id():
    catalogo = [_ex("x", 3, id="x2"), _ex("x", 3, id="x1")]
    r = _escolher([], catalogo=catalogo, topicos=["x"])
    assert r.exercicio is not None
    assert r.exercicio.id == "x1"


def test_deterministica():
    a = _escolher(ESTADOS_B_FRACO, resolvidos={"a-1"}, evasao=0.7)
    b = _escolher(list(reversed(ESTADOS_B_FRACO)), resolvidos={"a-1"}, evasao=0.7)
    assert a == b


def test_aluno_sem_nenhum_estado():
    r = escolher("novo", [], set(), 0.0)
    assert r.student_id == "novo"
    assert r.topico == "funcoes"
    assert r.exercicio is not None
    assert r.exercicio.id.startswith("funcoes-")
    assert "ainda não tentado" in r.motivo


@pytest.mark.parametrize("evasao", [0.0, 0.7])
def test_motivo_nao_vazio(evasao):
    assert _escolher(ESTADOS_B_FRACO, evasao=evasao).motivo.strip()
    todos = _escolher(ESTADOS_B_FRACO, resolvidos={e.id for e in CATALOGO}, evasao=evasao)
    assert todos.motivo.strip()
