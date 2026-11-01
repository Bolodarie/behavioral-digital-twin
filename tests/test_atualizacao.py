"""Atualização do gêmeo por evento: cada tipo de evento mexe só no que deve."""
from datetime import datetime, timedelta, timezone

import pytest

from gemeo.atualizacao import ALFA, aplicar_evento
from modelos import Evento
from tests.fabricas import evento_dict


def _evento(**campos) -> Evento:
    return Evento.model_validate(evento_dict(**campos))


def _respondido(event_id: str, acertou: bool, tempo: int, hora: str) -> Evento:
    return _evento(
        event_id=event_id,
        occurred_at=hora,
        payload={"acertou": acertou, "tempo_gasto_s": tempo},
    )


def _primeira_resposta_certa():
    ev = _respondido("e1", True, 100, "2026-03-02T12:00:00Z")
    return ev, aplicar_evento(ev, 3, None, None, None)


def test_primeiro_iniciado_cria_aluno_sem_topico():
    ev = _evento(event_type="exercicio_iniciado")
    r = aplicar_evento(ev, 3, None, None, None)
    assert r.aluno.student_id == "aluno-1"
    assert r.aluno.taxa_abandono == 0.0
    assert r.aluno.erros_seguidos == 0
    assert r.aluno.desempenho_relativo == 0.0
    assert r.aluno.respostas == 0
    assert r.aluno.velocidade_media_s is None
    assert r.aluno.ultimo_evento_id == "e1"
    assert r.aluno.ultimo_evento_em == ev.occurred_at
    assert r.topico is None
    assert r.exercicio is None


def test_primeira_resposta_certa():
    ev, r = _primeira_resposta_certa()
    assert r.topico.topic_id == "funcoes"
    assert r.topico.rating_elo == 1016.0
    assert r.topico.tentativas == 1
    assert r.topico.acertos == 1
    assert r.aluno.velocidade_media_s == 100.0
    assert r.aluno.desempenho_relativo == pytest.approx(0.1)
    assert r.aluno.respostas == 1
    assert r.aluno.erros_seguidos == 0
    assert r.exercicio.exercise_id == "funcoes-3"
    assert r.exercicio.tentativas == 1
    assert r.exercicio.acertou_alguma_vez


def test_segunda_resposta_errada():
    _, r1 = _primeira_resposta_certa()
    ev2 = _respondido("e2", False, 50, "2026-03-02T12:05:00Z")
    r2 = aplicar_evento(ev2, 3, r1.aluno, r1.topico, r1.exercicio)
    assert r2.topico.rating_elo == pytest.approx(999.263, abs=1e-3)
    assert r2.topico.tentativas == 2
    assert r2.topico.acertos == 1
    assert r2.aluno.velocidade_media_s == 90.0
    assert r2.aluno.erros_seguidos == 1
    assert r2.aluno.desempenho_relativo == pytest.approx(-0.0246, abs=1e-3)
    assert r2.aluno.respostas == 2
    assert r2.exercicio.tentativas == 2
    assert r2.exercicio.acertou_alguma_vez


def test_abandono_so_mexe_na_taxa():
    _, r1 = _primeira_resposta_certa()
    ev = _evento(
        event_id="e2",
        event_type="exercicio_abandonado",
        occurred_at="2026-03-02T12:10:00Z",
    )
    r2 = aplicar_evento(ev, 3, r1.aluno, r1.topico, r1.exercicio)
    assert r2.aluno.taxa_abandono == 0.2
    assert r2.aluno.respostas == r1.aluno.respostas
    assert r2.aluno.erros_seguidos == r1.aluno.erros_seguidos
    assert r2.aluno.velocidade_media_s == r1.aluno.velocidade_media_s
    assert r2.aluno.desempenho_relativo == r1.aluno.desempenho_relativo
    assert r2.topico is None
    assert r2.exercicio is None


def test_resposta_depois_de_abandono_puxa_taxa_para_zero():
    _, r1 = _primeira_resposta_certa()
    ab = _evento(
        event_id="e2",
        event_type="exercicio_abandonado",
        occurred_at="2026-03-02T12:10:00Z",
    )
    r2 = aplicar_evento(ab, 3, r1.aluno, r1.topico, r1.exercicio)
    ev3 = _respondido("e3", True, 80, "2026-03-02T12:20:00Z")
    r3 = aplicar_evento(ev3, 3, r2.aluno, r1.topico, r1.exercicio)
    assert r2.aluno.taxa_abandono == 0.2
    assert r3.aluno.taxa_abandono == pytest.approx(0.16)
    assert ALFA == 0.2


def test_erros_seguidos_zera_ao_acertar():
    ev1 = _respondido("e1", False, 60, "2026-03-02T12:00:00Z")
    r1 = aplicar_evento(ev1, 3, None, None, None)
    ev2 = _respondido("e2", False, 60, "2026-03-02T12:01:00Z")
    r2 = aplicar_evento(ev2, 3, r1.aluno, r1.topico, r1.exercicio)
    ev3 = _respondido("e3", True, 60, "2026-03-02T12:02:00Z")
    r3 = aplicar_evento(ev3, 3, r2.aluno, r2.topico, r2.exercicio)
    assert r2.aluno.erros_seguidos == 2
    assert r3.aluno.erros_seguidos == 0
    assert r1.exercicio.acertou_alguma_vez is False


def test_entradas_nao_sao_alteradas():
    _, r1 = _primeira_resposta_certa()
    aluno, topico, exercicio = r1.aluno, r1.topico, r1.exercicio
    copias = (aluno.model_copy(), topico.model_copy(), exercicio.model_copy())
    ev = _respondido("e2", False, 50, "2026-03-02T12:05:00Z")
    aplicar_evento(ev, 3, aluno, topico, exercicio)
    assert (aluno, topico, exercicio) == copias


def test_ultimo_evento_so_avanca():
    _, r1 = _primeira_resposta_certa()  # e1 às 12:00:00
    antigo = _respondido("e0", True, 10, "2026-03-02T11:00:00Z")
    r2 = aplicar_evento(antigo, 3, r1.aluno, r1.topico, r1.exercicio)
    assert r2.aluno.ultimo_evento_em == r1.aluno.ultimo_evento_em
    assert r2.aluno.ultimo_evento_id == "e1"

    empate_maior = _respondido("e2", True, 10, "2026-03-02T12:00:00Z")
    r3 = aplicar_evento(empate_maior, 3, r1.aluno, r1.topico, r1.exercicio)
    assert r3.aluno.ultimo_evento_id == "e2"

    empate_menor = _respondido("e0", True, 10, "2026-03-02T12:00:00Z")
    r4 = aplicar_evento(empate_menor, 3, r3.aluno, r3.topico, r3.exercicio)
    assert r4.aluno.ultimo_evento_id == "e2"
    assert r4.aluno.atualizado_em == r4.aluno.ultimo_evento_em


def test_atualizado_em_vem_do_evento():
    # horário no passado distante: nenhum relógio real pode aparecer no estado
    ev = _respondido("e1", True, 100, "2001-01-01T00:00:00Z")
    r = aplicar_evento(ev, 3, None, None, None)
    esperado = datetime(2001, 1, 1, tzinfo=timezone.utc)
    assert r.aluno.atualizado_em == esperado
    assert r.aluno.ultimo_evento_em == esperado
    assert r.topico.atualizado_em == esperado

    depois = _respondido("e2", True, 100, "2001-01-01T00:00:30Z")
    r2 = aplicar_evento(depois, 3, r.aluno, r.topico, r.exercicio)
    assert r2.aluno.atualizado_em == esperado + timedelta(seconds=30)
    assert r2.topico.atualizado_em == esperado + timedelta(seconds=30)
