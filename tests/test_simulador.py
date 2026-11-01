"""Testes do simulador: reprodutibilidade, consistência e comportamento por perfil."""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pytest

from catalogo import exercicio_por_id
from gemeo import elo
from ingestao import simulador
from ingestao.simulador import PERFIS, simular
from modelos import Evento

INICIO = datetime(2026, 1, 5, tzinfo=timezone.utc)
DIAS = 42
N_ALUNOS = 9
FORMATO = "%Y-%m-%dT%H:%M:%SZ"


def _instante(texto: str) -> datetime:
    return datetime.strptime(texto, FORMATO).replace(tzinfo=timezone.utc)


def _dias_ativos(sim, aluno: str) -> set[int]:
    return {
        (_instante(e["occurred_at"]) - INICIO).days
        for e in sim.eventos
        if e["student_id"] == aluno
    }


def _maior_lacuna(dias_ativos: set[int]) -> int:
    maior = atual = 0
    for dia in range(DIAS):
        atual = 0 if dia in dias_ativos else atual + 1
        maior = max(maior, atual)
    return maior


def _alunos_do_perfil(sim, perfil: str) -> list[str]:
    return [a for a, p in sim.perfis.items() if p == perfil]


@pytest.fixture(scope="module", params=[42, 7, 2026])
def sim(request):
    return simular(request.param, N_ALUNOS, INICIO, DIAS)


@pytest.fixture(scope="module")
def sim42():
    return simular(42, N_ALUNOS, INICIO, DIAS)


def test_reprodutivel(sim42):
    de_novo = simular(42, N_ALUNOS, INICIO, DIAS)
    assert json.dumps(de_novo.eventos) == json.dumps(sim42.eventos)
    assert de_novo == sim42


def test_semente_diferente_muda(sim42):
    outra = simular(43, N_ALUNOS, INICIO, DIAS)
    assert outra.eventos != sim42.eventos
    ids_a = {e["event_id"] for e in sim42.eventos}
    ids_b = {e["event_id"] for e in outra.eventos}
    assert not ids_a & ids_b


def test_eventos_validos_e_consistentes_com_o_catalogo(sim):
    assert sim.eventos
    ids = [e["event_id"] for e in sim.eventos]
    assert len(set(ids)) == len(ids)
    for dado in sim.eventos:
        evento = Evento.model_validate(dado)
        exercicio = exercicio_por_id(evento.exercise_id)
        assert exercicio is not None
        assert exercicio.topico_id == evento.topic
        assert dado["occurred_at"] == evento.occurred_at_texto


def test_ordem_cronologica_e_dentro_da_janela(sim):
    chaves = [(e["occurred_at"], e["event_id"]) for e in sim.eventos]
    assert chaves == sorted(chaves)
    fim = INICIO + timedelta(days=DIAS)
    for dado in sim.eventos:
        assert INICIO <= _instante(dado["occurred_at"]) < fim


def test_toda_resposta_ou_abandono_tem_inicio_antes(sim):
    inicios = defaultdict(list)
    for e in sim.eventos:
        if e["event_type"] == "exercicio_iniciado":
            inicios[(e["student_id"], e["exercise_id"])].append(e["occurred_at"])
    encerramentos = [
        e
        for e in sim.eventos
        if e["event_type"] in ("exercicio_respondido", "exercicio_abandonado")
    ]
    assert encerramentos
    for e in encerramentos:
        antes = inicios[(e["student_id"], e["exercise_id"])]
        assert any(t < e["occurred_at"] for t in antes)
    # cada tentativa tem exatamente um encerramento
    assert sum(len(v) for v in inicios.values()) == len(encerramentos)


def test_perfis_em_rodizio(sim):
    assert len(sim.perfis) == N_ALUNOS
    esperado = {f"aluno-{i + 1:03d}": PERFIS[i % 3] for i in range(N_ALUNOS)}
    assert sim.perfis == esperado
    assert {e["student_id"] for e in sim.eventos} <= set(sim.perfis)


def test_desistente_para_antes_da_metade(sim):
    limite = INICIO + timedelta(days=DIAS / 2)
    for aluno in _alunos_do_perfil(sim, "desistente"):
        instantes = [
            _instante(e["occurred_at"]) for e in sim.eventos if e["student_id"] == aluno
        ]
        assert instantes
        assert max(instantes) <= limite


def test_dedicado_ativo_na_maioria_dos_dias(sim):
    for aluno in _alunos_do_perfil(sim, "dedicado"):
        assert len(_dias_ativos(sim, aluno)) / DIAS >= 0.6


def test_irregular_tem_lacuna_de_4_dias_e_menos_dias_ativos_que_dedicado(sim):
    dedicados = [len(_dias_ativos(sim, a)) for a in _alunos_do_perfil(sim, "dedicado")]
    for aluno in _alunos_do_perfil(sim, "irregular"):
        ativos = _dias_ativos(sim, aluno)
        assert _maior_lacuna(ativos) >= 4
        assert len(ativos) < min(dedicados)


def test_abandono_depende_do_perfil(sim):
    def fracao(perfil: str) -> float:
        alunos = set(_alunos_do_perfil(sim, perfil))
        eventos = [e for e in sim.eventos if e["student_id"] in alunos]
        iniciados = sum(e["event_type"] == "exercicio_iniciado" for e in eventos)
        abandonados = sum(e["event_type"] == "exercicio_abandonado" for e in eventos)
        assert iniciados
        return abandonados / iniciados

    assert fracao("desistente") > fracao("dedicado")


def test_habilidade_nunca_cai_e_cresce_para_dedicado(sim):
    assert set(sim.habilidades_iniciais) == set(sim.habilidades_finais) == set(sim.perfis)
    for aluno, iniciais in sim.habilidades_iniciais.items():
        finais = sim.habilidades_finais[aluno]
        assert set(finais) == set(iniciais)
        for topico, inicial in iniciais.items():
            assert finais[topico] >= inicial
    for aluno in _alunos_do_perfil(sim, "dedicado"):
        iniciais = sim.habilidades_iniciais[aluno]
        finais = sim.habilidades_finais[aluno]
        assert sum(finais.values()) > sum(iniciais.values()) + 50


def test_escala_igual_a_do_elo():
    for dificuldade in range(1, 6):
        assert simulador.rating_do_exercicio(dificuldade) == elo.rating_do_exercicio(
            dificuldade
        )
    for habilidade, rating in [(1000.0, 1000.0), (800.0, 1200.0), (1234.5, 900.0)]:
        assert simulador.probabilidade_base(habilidade, rating) == pytest.approx(
            elo.expectativa(habilidade, rating), abs=1e-12
        )


def test_entradas_invalidas():
    with pytest.raises(ValueError):
        simular(1, 3, datetime(2026, 1, 5), DIAS)
    with pytest.raises(ValueError):
        simular(1, 0, INICIO, DIAS)
    with pytest.raises(ValueError):
        simular(1, 3, INICIO, 0)
