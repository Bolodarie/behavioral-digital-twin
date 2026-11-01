"""Defeitos do simulador: duplicados, desordem e malformados, sem tocar nos válidos."""
from datetime import datetime, timezone

from pydantic import ValidationError

from catalogo import exercicio_por_id
from ingestao.simulador import simular
from modelos import Evento

INICIO = datetime(2026, 1, 5, tzinfo=timezone.utc)


def _sim(defeitos: bool, semente: int = 7):
    return simular(semente, 6, INICIO, 21, defeitos=defeitos)


def _valido(dado: dict) -> bool:
    try:
        evento = Evento.model_validate(dado)
    except ValidationError:
        return False
    return exercicio_por_id(evento.exercise_id) is not None


def _tipo_do_defeito(dado: dict) -> str | None:
    """Classifica um malformado; `None` se o dado for válido."""
    if _valido(dado):
        return None
    if "event_id" not in dado:
        return "sem_event_id"
    if exercicio_por_id(dado["exercise_id"]) is None:
        return "exercicio_inexistente"
    if not dado["occurred_at"].endswith("Z"):
        return "sem_fuso"
    if dado["payload"].get("tempo_gasto_s") == 0:
        return "tempo_zero"
    if not isinstance(dado["payload"].get("acertou"), bool):
        return "acertou_texto"
    return "outro"


def test_sem_defeitos_e_cronologico():
    eventos = _sim(False).eventos
    chaves = [(e["occurred_at"], e["event_id"]) for e in eventos]
    assert chaves == sorted(chaves)
    assert len({e["event_id"] for e in eventos}) == len(eventos)


def test_defeitos_preservam_os_eventos_validos():
    limpo = _sim(False).eventos
    sujo = _sim(True).eventos
    unicos = {e["event_id"]: e for e in sujo if _valido(e)}
    assert unicos == {e["event_id"]: e for e in limpo}
    assert len(unicos) == len(limpo)


def test_defeitos_preservam_habilidades_e_perfis():
    limpo, sujo = _sim(False), _sim(True)
    assert sujo.habilidades_iniciais == limpo.habilidades_iniciais
    assert sujo.habilidades_finais == limpo.habilidades_finais
    assert sujo.perfis == limpo.perfis


def test_defeitos_e_reprodutivel():
    assert _sim(True).eventos == _sim(True).eventos


def test_defeitos_gera_duplicados():
    vistos: dict[str, dict] = {}
    repetidos = 0
    for e in _sim(True).eventos:
        if "event_id" not in e:
            continue
        if e["event_id"] in vistos:
            assert e == vistos[e["event_id"]]  # o mesmo dict reenviado
            repetidos += 1
        vistos.setdefault(e["event_id"], e)
    assert repetidos > 0


def test_defeitos_gera_ordem_nao_cronologica():
    instantes = [e["occurred_at"] for e in _sim(True).eventos if _valido(e)]
    assert instantes != sorted(instantes)


def test_defeitos_gera_ao_menos_3_malformados_de_tipos_diferentes():
    malformados = [e for e in _sim(True).eventos if not _valido(e)]
    tipos = {_tipo_do_defeito(e) for e in malformados}
    assert "outro" not in tipos
    assert len(tipos) >= 3
    falham_no_modelo = {
        _tipo_do_defeito(e)
        for e in malformados
        if _tipo_do_defeito(e) != "exercicio_inexistente"
    }
    assert len(falham_no_modelo) >= 3
    for e in malformados:
        if _tipo_do_defeito(e) != "exercicio_inexistente":
            try:
                Evento.model_validate(e)
            except ValidationError:
                continue
            raise AssertionError(f"deveria falhar na validacao: {e}")
