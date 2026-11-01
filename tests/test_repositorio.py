"""Repositório do gêmeo: leitura, upsert, remoção e fronteira de transação."""
from datetime import datetime, timezone

import pytest

import db
from gemeo import repositorio
from modelos import EstadoAluno, EstadoAtualizado, EstadoExercicio, EstadoTopico

T0 = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 3, 2, 12, 5, 30, tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    c = db.abrir(tmp_path / "t.db")
    yield c
    c.close()


def aluno(student_id="a1", em=T0, **kw) -> EstadoAluno:
    dados = dict(
        student_id=student_id,
        velocidade_media_s=95.5,
        taxa_abandono=0.1,
        erros_seguidos=2,
        desempenho_relativo=-0.25,
        respostas=7,
        ultimo_evento_em=em,
        ultimo_evento_id="e1",
        atualizado_em=em,
    )
    dados.update(kw)
    return EstadoAluno(**dados)


def topico(student_id="a1", topic_id="funcoes", rating=1000.0, em=T0, **kw) -> EstadoTopico:
    dados = dict(
        student_id=student_id,
        topic_id=topic_id,
        rating_elo=rating,
        tentativas=3,
        acertos=2,
        atualizado_em=em,
    )
    dados.update(kw)
    return EstadoTopico(**dados)


def exercicio(student_id="a1", exercise_id="funcoes-3", tentativas=1, acertou=True) -> EstadoExercicio:
    return EstadoExercicio(
        student_id=student_id,
        exercise_id=exercise_id,
        tentativas=tentativas,
        acertou_alguma_vez=acertou,
    )


def completo(student_id="a1", **kw) -> EstadoAtualizado:
    return EstadoAtualizado(
        aluno=aluno(student_id),
        topico=topico(student_id, **kw),
        exercicio=exercicio(student_id),
    )


def contar(conn, tabela) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


def test_ida_e_volta_exata(conn):
    entrada = EstadoAtualizado(
        aluno=aluno(velocidade_media_s=123.456789012345),
        topico=topico(rating=999.2634567891234, em=T1),
        exercicio=exercicio(tentativas=4, acertou=False),
    )
    repositorio.salvar(conn, entrada)

    assert repositorio.ler_aluno(conn, "a1") == entrada.aluno
    lido = repositorio.ler_topico(conn, "a1", "funcoes")
    assert lido.rating_elo == 999.2634567891234
    assert lido.atualizado_em == T1
    assert lido.atualizado_em.utcoffset() == timezone.utc.utcoffset(None)
    assert lido == entrada.topico
    assert repositorio.ler_exercicio(conn, "a1", "funcoes-3") == entrada.exercicio
    a = repositorio.ler_aluno(conn, "a1")
    assert a.ultimo_evento_em.tzinfo is not None and a.atualizado_em.tzinfo is not None


def test_velocidade_media_nula_volta_nula(conn):
    repositorio.salvar(conn, EstadoAtualizado(aluno=aluno(velocidade_media_s=None)))
    assert repositorio.ler_aluno(conn, "a1").velocidade_media_s is None


def test_salvar_e_upsert(conn):
    repositorio.salvar(conn, completo())
    repositorio.salvar(
        conn,
        EstadoAtualizado(
            aluno=aluno(respostas=8, em=T1),
            topico=topico(rating=1010.5, tentativas=4, em=T1),
            exercicio=exercicio(tentativas=2),
        ),
    )

    assert contar(conn, "gemeo_aluno") == 1
    assert contar(conn, "gemeo_topico") == 1
    assert contar(conn, "gemeo_exercicio") == 1
    assert repositorio.ler_aluno(conn, "a1").respostas == 8
    assert repositorio.ler_topico(conn, "a1", "funcoes").rating_elo == 1010.5
    assert repositorio.ler_exercicio(conn, "a1", "funcoes-3").tentativas == 2


def test_salvar_com_topico_e_exercicio_none_nao_mexe_neles(conn):
    repositorio.salvar(conn, completo())
    repositorio.salvar(conn, EstadoAtualizado(aluno=aluno(respostas=9, em=T1)))

    assert repositorio.ler_aluno(conn, "a1").respostas == 9
    assert repositorio.ler_topico(conn, "a1", "funcoes") == topico()
    assert repositorio.ler_exercicio(conn, "a1", "funcoes-3") == exercicio()


def test_ler_desconhecidos_devolvem_none_ou_vazio(conn):
    assert repositorio.ler_aluno(conn, "x") is None
    assert repositorio.ler_topicos(conn, "x") == []
    assert repositorio.ler_topico(conn, "x", "funcoes") is None
    assert repositorio.ler_exercicio(conn, "x", "funcoes-3") is None
    assert repositorio.ler_exercicios_resolvidos(conn, "x") == set()


def test_ler_topicos_ordenados_por_topic_id(conn):
    for t in ("sistemas_lineares", "equacao_1_grau", "funcoes"):
        repositorio.salvar(conn, EstadoAtualizado(aluno=aluno(), topico=topico(topic_id=t)))
    ids = [t.topic_id for t in repositorio.ler_topicos(conn, "a1")]
    assert ids == ["equacao_1_grau", "funcoes", "sistemas_lineares"]


def test_resolvidos_so_acertou_alguma_vez(conn):
    for ex, acertou in (("funcoes-1", True), ("funcoes-2", False), ("funcoes-3", True)):
        repositorio.salvar(
            conn,
            EstadoAtualizado(aluno=aluno(), exercicio=exercicio(exercise_id=ex, acertou=acertou)),
        )
    repositorio.salvar(
        conn,
        EstadoAtualizado(aluno=aluno("b"), exercicio=exercicio("b", "funcoes-4", acertou=True)),
    )
    assert repositorio.ler_exercicios_resolvidos(conn, "a1") == {"funcoes-1", "funcoes-3"}


def test_apagar_aluno_so_apaga_aquele_aluno(conn):
    repositorio.salvar(conn, completo("a1"))
    repositorio.salvar(conn, completo("b1"))

    repositorio.apagar_aluno(conn, "a1")

    assert repositorio.ler_aluno(conn, "a1") is None
    assert repositorio.ler_topicos(conn, "a1") == []
    assert repositorio.ler_exercicio(conn, "a1", "funcoes-3") is None
    assert repositorio.ler_aluno(conn, "b1") is not None
    assert len(repositorio.ler_topicos(conn, "b1")) == 1
    assert repositorio.ler_exercicio(conn, "b1", "funcoes-3") is not None


def test_apagar_tudo(conn):
    repositorio.salvar(conn, completo("a1"))
    repositorio.salvar(conn, completo("b1"))

    repositorio.apagar_tudo(conn)

    for tabela in ("gemeo_aluno", "gemeo_topico", "gemeo_exercicio"):
        assert contar(conn, tabela) == 0
    assert contar(conn, "topicos") > 0  # catálogo intacto


def test_salvar_nao_faz_commit(conn):
    conn.execute("BEGIN")
    repositorio.salvar(conn, completo())
    assert conn.in_transaction
    conn.execute("ROLLBACK")

    for tabela in ("gemeo_aluno", "gemeo_topico", "gemeo_exercicio"):
        assert contar(conn, tabela) == 0
