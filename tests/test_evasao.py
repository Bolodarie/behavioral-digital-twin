from datetime import datetime, timedelta, timezone

from gemeo.evasao import probabilidade_evasao
from modelos import EstadoAluno

AGORA = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)


def estado(dias_inativo: float = 0.0, **campos) -> EstadoAluno:
    base = dict(
        student_id="a1",
        velocidade_media_s=None,
        taxa_abandono=0.0,
        erros_seguidos=0,
        desempenho_relativo=0.0,
        respostas=10,
        ultimo_evento_em=AGORA - timedelta(days=dias_inativo),
        ultimo_evento_id="e1",
        atualizado_em=AGORA,
    )
    base.update(campos)
    return EstadoAluno(**base)


def test_resultado_entre_0_e_1_exclusivo():
    minimo = estado(taxa_abandono=0.0, erros_seguidos=0, desempenho_relativo=1.0)
    maximo = estado(
        dias_inativo=1000, taxa_abandono=1.0, erros_seguidos=1000,
        desempenho_relativo=-1.0,
    )
    assert 0.0 < probabilidade_evasao(minimo, AGORA) < 1.0
    assert 0.0 < probabilidade_evasao(maximo, AGORA) < 1.0


def test_cresce_com_inatividade():
    dias = [0, 3, 7, 14]
    valores = [probabilidade_evasao(estado(dias_inativo=d), AGORA) for d in dias]
    assert all(a < b for a, b in zip(valores, valores[1:]))
    assert probabilidade_evasao(estado(dias_inativo=30), AGORA) == valores[-1]


def test_cresce_com_abandono():
    taxas = [0.0, 0.25, 0.5, 1.0]
    valores = [probabilidade_evasao(estado(taxa_abandono=t), AGORA) for t in taxas]
    assert all(a < b for a, b in zip(valores, valores[1:]))


def test_cresce_com_erros_seguidos():
    valores = [probabilidade_evasao(estado(erros_seguidos=n), AGORA) for n in range(6)]
    assert all(a < b for a, b in zip(valores, valores[1:]))
    assert probabilidade_evasao(estado(erros_seguidos=9), AGORA) == valores[-1]


def test_cai_com_melhor_desempenho():
    niveis = [-0.5, 0.0, 0.5]
    valores = [probabilidade_evasao(estado(desempenho_relativo=d), AGORA) for d in niveis]
    assert all(a > b for a, b in zip(valores, valores[1:]))


def test_aluno_ativo_abaixo_de_0_3():
    ativo = estado(dias_inativo=0.5, desempenho_relativo=0.1)
    assert probabilidade_evasao(ativo, AGORA) < 0.3


def test_aluno_sumido_acima_de_0_7():
    sumido = estado(
        dias_inativo=14, taxa_abandono=0.6, erros_seguidos=4, desempenho_relativo=-0.3
    )
    assert probabilidade_evasao(sumido, AGORA) > 0.7


def test_agora_anterior_ao_ultimo_evento_conta_zero_dias():
    futuro = estado(dias_inativo=-2)  # último evento 2 dias depois de "agora"
    assert probabilidade_evasao(futuro, AGORA) == probabilidade_evasao(estado(), AGORA)
