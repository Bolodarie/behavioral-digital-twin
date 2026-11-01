"""Fluxo ponta a ponta: simulador -> ingestão -> pipeline -> gêmeo -> API."""
import random
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import db
from api.main import create_app
from ingestao.receber import receber
from ingestao.simulador import simular
from pipeline.consumidor import processar_pendentes
from scripts.comparar_habilidades import comparar, main
from scripts.estatistica import spearman
from tests.utilitarios import dump_gemeo

SEMENTE, ALUNOS, DIAS = 42, 12, 42
INICIO = datetime(2026, 1, 5, tzinfo=timezone.utc)
MIN_TENTATIVAS = 5
MIN_ALUNOS = 6
# A convergência usa uma turma maior (a de 12 alunos dá 9 a 10 alunos por tópico e
# erro de amostragem de cerca de 0,35: não distingue um Elo correto de um quase
# certo). Medido com 40 alunos e 42 dias, nas sementes 42, 1..7 (menor valor):
# Spearman agregado 0,416 e por tópico 0,232. Os limiares ficam alguns centésimos
# abaixo disso e acima do que Elo defeituoso produz na semente 42: expectativa
# invertida (0,143 agregado, 0,068 por tópico), dificuldade ignorada (0,255 e
# 0,128), K negativo ou nulo (negativo / correlação indefinida).
ALUNOS_CONVERGENCIA = 40
LIMIAR_CONVERGENCIA = 0.35  # Spearman agregado dos pares aluno x tópico
LIMIAR_POR_TOPICO = 0.20


def _ingerir_e_processar(caminho, simulacao) -> dict[str, int]:
    contagem = {"aceito": 0, "duplicado": 0, "rejeitado": 0}
    conn = db.abrir(caminho)
    try:
        for evento in simulacao.eventos:
            contagem[receber(conn, evento).status] += 1
        processar_pendentes(conn)
    finally:
        conn.close()
    return contagem


def _dump(caminho):
    conn = db.abrir(caminho)
    try:
        return dump_gemeo(conn)
    finally:
        conn.close()


@pytest.fixture(scope="module")
def simulacao():
    return simular(semente=SEMENTE, n_alunos=ALUNOS, inicio=INICIO, dias=DIAS)


@pytest.fixture(scope="module")
def caminho_db(tmp_path_factory, simulacao):
    caminho = tmp_path_factory.mktemp("ponta_a_ponta") / "gemeo.db"
    _ingerir_e_processar(caminho, simulacao)
    return caminho


@pytest.fixture(scope="module")
def linhas(caminho_db, simulacao):
    conn = db.abrir_somente_leitura(caminho_db)
    try:
        return comparar(conn, simulacao)
    finally:
        conn.close()


@pytest.fixture(scope="module")
def linhas_convergencia(tmp_path_factory):
    simulacao = simular(
        semente=SEMENTE, n_alunos=ALUNOS_CONVERGENCIA, inicio=INICIO, dias=DIAS
    )
    caminho = tmp_path_factory.mktemp("convergencia") / "gemeo.db"
    _ingerir_e_processar(caminho, simulacao)
    conn = db.abrir_somente_leitura(caminho)
    try:
        return comparar(conn, simulacao)
    finally:
        conn.close()


def _por_topico(linhas):
    """Tópicos com amostra suficiente: ≥ MIN_ALUNOS alunos com ≥ MIN_TENTATIVAS."""
    grupos: dict[str, list] = {}
    for linha in linhas:
        if linha.tentativas >= MIN_TENTATIVAS:
            grupos.setdefault(linha.topic_id, []).append(linha)
    return {t: ls for t, ls in grupos.items() if len(ls) >= MIN_ALUNOS}


def _correlacao(ls, ratings=None) -> float:
    ratings = ratings if ratings is not None else [l.rating_elo for l in ls]
    return spearman([l.habilidade_verdadeira for l in ls], ratings)


def test_comparar_so_traz_pares_com_tentativas(linhas, simulacao):
    assert linhas
    assert all(l.tentativas >= 1 for l in linhas)
    assert {l.student_id for l in linhas} <= set(simulacao.perfis)
    for l in linhas:
        assert l.perfil == simulacao.perfis[l.student_id]
        assert l.habilidade_verdadeira == simulacao.habilidades_finais[l.student_id][l.topic_id]


def test_elo_converge_para_a_habilidade_verdadeira(linhas_convergencia):
    topicos = _por_topico(linhas_convergencia)
    assert len(topicos) == 4  # a amostra cobre todos os tópicos
    for topico, ls in topicos.items():
        assert _correlacao(ls) >= LIMIAR_POR_TOPICO, topico
    todos = [l for ls in topicos.values() for l in ls]
    assert _correlacao(todos) >= LIMIAR_CONVERGENCIA


def test_limiar_nao_e_trivial(linhas_convergencia):
    """Controle negativo: ratings embaralhados entre alunos ficam abaixo do limiar agregado.

    Só o agregado: por tópico (cerca de 10 alunos) o acaso sozinho passa de
    `LIMIAR_POR_TOPICO` com frequência, então um controle por tópico não prova nada.
    """
    todos = [l for ls in _por_topico(linhas_convergencia).values() for l in ls]
    ratings = [l.rating_elo for l in todos]
    random.Random(0).shuffle(ratings)
    assert _correlacao(todos, ratings) < LIMIAR_CONVERGENCIA


def test_defeitos_nao_mudam_o_gemeo_final(tmp_path, caminho_db):
    com_defeitos = simular(
        semente=SEMENTE, n_alunos=ALUNOS, inicio=INICIO, dias=DIAS, defeitos=True
    )
    caminho = tmp_path / "defeitos.db"

    contagem = _ingerir_e_processar(caminho, com_defeitos)

    assert contagem["rejeitado"] > 0
    conn = db.abrir(caminho)
    try:
        rejeitados = conn.execute(
            "SELECT COUNT(*) FROM eventos_brutos WHERE status = 'rejeitado'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert rejeitados == contagem["rejeitado"]
    assert _dump(caminho) != []
    assert _dump(caminho) == _dump(caminho_db)


def test_evasao_distingue_perfis(caminho_db, simulacao):
    agora = INICIO + timedelta(days=DIAS)
    cliente = TestClient(create_app(caminho_db, agora=lambda: agora))
    com_eventos = {e["student_id"] for e in simulacao.eventos}
    evasao: dict[str, list[float]] = {"dedicado": [], "irregular": [], "desistente": []}

    for aluno, perfil in simulacao.perfis.items():
        recomendacao = cliente.get(f"/alunos/{aluno}/recomendacao")
        gemeo = cliente.get(f"/alunos/{aluno}/gemeo")
        if aluno not in com_eventos:
            assert recomendacao.status_code == gemeo.status_code == 404
            continue
        assert recomendacao.status_code == 200
        assert gemeo.status_code == 200
        evasao[perfil].append(gemeo.json()["probabilidade_evasao"])

    assert evasao["dedicado"] and evasao["desistente"]
    media = lambda xs: sum(xs) / len(xs)
    assert media(evasao["desistente"]) > media(evasao["dedicado"])


DIAS_SCRIPT = 21  # com 14 dias (12 alunos) só um tópico passa dos 6 alunos mínimos; com 21, todos
ARGS_SCRIPT = ["--semente", "42", "--alunos", "12", "--dias", str(DIAS_SCRIPT)]
TOPICOS = ("funcoes", "equacao_1_grau", "equacao_2_grau", "sistemas_lineares")
LINHA_CORRELACAO = re.compile(r"^\s+(\w+)\s+([+-]\d\.\d{3})\s+\((\d+) alunos\)$")


def test_script_imprime_tabela_e_correlacao_reproduziveis(capsys, tmp_path):
    assert main(ARGS_SCRIPT) == 0
    primeira = capsys.readouterr().out
    assert main(ARGS_SCRIPT) == 0
    assert capsys.readouterr().out == primeira
    assert "aluno-001" in primeira
    tabela, _, secao = primeira.partition("Spearman por topico")
    assert secao
    assert "aluno-001" in tabela
    assert all(topico in secao for topico in TOPICOS)

    # Ao menos um tópico tem correlação calculada (não só "amostra insuficiente")
    # e o número impresso bate com o calculado direto por `comparar`.
    impressas = {}
    for linha in secao.splitlines():
        achou = LINHA_CORRELACAO.match(linha)
        if achou:
            impressas[achou.group(1)] = (float(achou.group(2)), int(achou.group(3)))
    assert impressas

    simulacao = simular(semente=42, n_alunos=12, inicio=INICIO, dias=DIAS_SCRIPT)
    caminho = tmp_path / "script.db"
    _ingerir_e_processar(caminho, simulacao)
    conn = db.abrir_somente_leitura(caminho)
    try:
        esperadas = _por_topico(comparar(conn, simulacao))
    finally:
        conn.close()
    assert set(impressas) == set(esperadas)
    for topico, (rho, alunos) in impressas.items():
        assert alunos == len(esperadas[topico])
        assert rho == pytest.approx(_correlacao(esperadas[topico]), abs=5e-4)
