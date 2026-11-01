"""Contratos Pydantic dos eventos e dos estados."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from modelos import (
    Evento,
    EstadoAluno,
    EstadoAtualizado,
    PayloadRespondido,
    ResultadoIngestao,
    TipoEvento,
)
from tests.fabricas import evento_dict


def test_evento_respondido_valido():
    ev = Evento(**evento_dict())
    assert ev.event_id == "e1"
    assert ev.student_id == "aluno-1"
    assert ev.exercise_id == "funcoes-3"
    assert ev.topic == "funcoes"
    assert ev.event_type is TipoEvento.EXERCICIO_RESPONDIDO
    assert ev.occurred_at == datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)
    assert ev.occurred_at_texto == "2026-03-02T12:00:00Z"
    assert ev.acertou is True
    assert ev.tempo_gasto_s == 100


@pytest.mark.parametrize("tipo", ["exercicio_iniciado", "exercicio_abandonado"])
def test_evento_iniciado_e_abandonado_com_payload_vazio(tipo):
    ev = Evento(**evento_dict(event_type=tipo))
    assert ev.payload == {}
    assert ev.acertou is None
    assert ev.tempo_gasto_s is None


def test_payload_nao_vazio_em_iniciado_rejeitado():
    with pytest.raises(ValidationError):
        Evento(**evento_dict(event_type="exercicio_iniciado", payload={"acertou": True}))


def test_occurred_at_sem_fuso_rejeitado():
    with pytest.raises(ValidationError):
        Evento(**evento_dict(occurred_at="2026-03-02T12:00:00"))


def test_offset_convertido_para_utc():
    ev = Evento(**evento_dict(occurred_at="2026-03-02T10:00:00-03:00"))
    assert ev.occurred_at_texto == "2026-03-02T13:00:00Z"
    assert ev.occurred_at.utcoffset().total_seconds() == 0


def test_fracao_de_segundo_truncada():
    ev = Evento(**evento_dict(occurred_at="2026-03-02T12:00:00.987Z"))
    assert ev.occurred_at_texto == "2026-03-02T12:00:00Z"
    assert ev.occurred_at.microsecond == 0


@pytest.mark.parametrize("tempo", [0, -5, 12.5, "30", True])
def test_tempo_gasto_invalido(tempo):
    with pytest.raises(ValidationError):
        Evento(**evento_dict(payload={"acertou": True, "tempo_gasto_s": tempo}))


@pytest.mark.parametrize("acertou", ["true", 1, None])
def test_acertou_nao_booleano(acertou):
    with pytest.raises(ValidationError):
        Evento(**evento_dict(payload={"acertou": acertou, "tempo_gasto_s": 10}))


def test_payload_respondido_com_chave_faltando_ou_extra():
    with pytest.raises(ValidationError):
        PayloadRespondido(acertou=True)
    with pytest.raises(ValidationError):
        PayloadRespondido(tempo_gasto_s=10)
    with pytest.raises(ValidationError):
        PayloadRespondido(acertou=True, tempo_gasto_s=10, extra=1)
    with pytest.raises(ValidationError):
        Evento(**evento_dict(payload={"acertou": True}))
    with pytest.raises(ValidationError):
        Evento(**evento_dict(payload={"acertou": True, "tempo_gasto_s": 10, "x": 1}))


def test_campos_extras_no_evento_rejeitados():
    with pytest.raises(ValidationError):
        Evento(**evento_dict(nota=10))


@pytest.mark.parametrize("campo", ["event_id", "student_id", "exercise_id", "topic"])
def test_ids_vazios_rejeitados(campo):
    with pytest.raises(ValidationError):
        Evento(**evento_dict(**{campo: ""}))


def test_tipo_de_evento_desconhecido():
    with pytest.raises(ValidationError):
        Evento(**evento_dict(event_type="exercicio_pulado"))


def test_estado_atualizado_defaults():
    agora = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)
    aluno = EstadoAluno(
        student_id="aluno-1",
        velocidade_media_s=None,
        taxa_abandono=0.0,
        erros_seguidos=0,
        desempenho_relativo=0.0,
        respostas=0,
        ultimo_evento_em=agora,
        ultimo_evento_id="e1",
        atualizado_em=agora,
    )
    est = EstadoAtualizado(aluno=aluno)
    assert est.topico is None
    assert est.exercicio is None


def test_resultado_ingestao_status_fechado():
    assert ResultadoIngestao(status="aceito", event_id="e1").motivo is None
    with pytest.raises(ValidationError):
        ResultadoIngestao(status="talvez", event_id=None)
