"""Repositório do gêmeo: leitura e gravação das tabelas `gemeo_*`.

`salvar` e as remoções nunca fazem commit nem abrem transação: quem chama
decide a fronteira (o pipeline usa `BEGIN IMMEDIATE` ... `COMMIT`/`ROLLBACK`).
Floats são gravados sem arredondar; datas ficam como `YYYY-MM-DDTHH:MM:SSZ`.
"""
import sqlite3
from datetime import datetime, timezone

from modelos import EstadoAluno, EstadoAtualizado, EstadoExercicio, EstadoTopico

FORMATO_DATA = "%Y-%m-%dT%H:%M:%SZ"


def _para_texto(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).strftime(FORMATO_DATA)


def _de_texto(texto: str) -> datetime:
    return datetime.strptime(texto, FORMATO_DATA).replace(tzinfo=timezone.utc)


def _aluno(linha: sqlite3.Row) -> EstadoAluno:
    return EstadoAluno(
        student_id=linha["student_id"],
        velocidade_media_s=linha["velocidade_media_s"],
        taxa_abandono=linha["taxa_abandono"],
        erros_seguidos=linha["erros_seguidos"],
        desempenho_relativo=linha["desempenho_relativo"],
        respostas=linha["respostas"],
        ultimo_evento_em=_de_texto(linha["ultimo_evento_em"]),
        ultimo_evento_id=linha["ultimo_evento_id"],
        atualizado_em=_de_texto(linha["atualizado_em"]),
    )


def _topico(linha: sqlite3.Row) -> EstadoTopico:
    return EstadoTopico(
        student_id=linha["student_id"],
        topic_id=linha["topic_id"],
        rating_elo=linha["rating_elo"],
        tentativas=linha["tentativas"],
        acertos=linha["acertos"],
        atualizado_em=_de_texto(linha["atualizado_em"]),
    )


def _exercicio(linha: sqlite3.Row) -> EstadoExercicio:
    return EstadoExercicio(
        student_id=linha["student_id"],
        exercise_id=linha["exercise_id"],
        tentativas=linha["tentativas"],
        acertou_alguma_vez=bool(linha["acertou_alguma_vez"]),
    )


def ler_aluno(conn: sqlite3.Connection, student_id: str) -> EstadoAluno | None:
    linha = conn.execute(
        "SELECT * FROM gemeo_aluno WHERE student_id = ?", (student_id,)
    ).fetchone()
    return _aluno(linha) if linha else None


def ler_topicos(conn: sqlite3.Connection, student_id: str) -> list[EstadoTopico]:
    linhas = conn.execute(
        "SELECT * FROM gemeo_topico WHERE student_id = ? ORDER BY topic_id",
        (student_id,),
    ).fetchall()
    return [_topico(linha) for linha in linhas]


def ler_topico(
    conn: sqlite3.Connection, student_id: str, topic_id: str
) -> EstadoTopico | None:
    linha = conn.execute(
        "SELECT * FROM gemeo_topico WHERE student_id = ? AND topic_id = ?",
        (student_id, topic_id),
    ).fetchone()
    return _topico(linha) if linha else None


def ler_exercicio(
    conn: sqlite3.Connection, student_id: str, exercise_id: str
) -> EstadoExercicio | None:
    linha = conn.execute(
        "SELECT * FROM gemeo_exercicio WHERE student_id = ? AND exercise_id = ?",
        (student_id, exercise_id),
    ).fetchone()
    return _exercicio(linha) if linha else None


def ler_exercicios_resolvidos(conn: sqlite3.Connection, student_id: str) -> set[str]:
    """Ids dos exercícios que o aluno acertou ao menos uma vez."""
    linhas = conn.execute(
        "SELECT exercise_id FROM gemeo_exercicio "
        "WHERE student_id = ? AND acertou_alguma_vez = 1",
        (student_id,),
    ).fetchall()
    return {linha["exercise_id"] for linha in linhas}


def salvar(conn: sqlite3.Connection, atualizado: EstadoAtualizado) -> None:
    """Upsert das partes não nulas do estado. Nunca faz commit."""
    a = atualizado.aluno
    conn.execute(
        "INSERT INTO gemeo_aluno (student_id, velocidade_media_s, taxa_abandono, "
        "erros_seguidos, desempenho_relativo, respostas, ultimo_evento_em, "
        "ultimo_evento_id, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (student_id) DO UPDATE SET "
        "velocidade_media_s = excluded.velocidade_media_s, "
        "taxa_abandono = excluded.taxa_abandono, "
        "erros_seguidos = excluded.erros_seguidos, "
        "desempenho_relativo = excluded.desempenho_relativo, "
        "respostas = excluded.respostas, "
        "ultimo_evento_em = excluded.ultimo_evento_em, "
        "ultimo_evento_id = excluded.ultimo_evento_id, "
        "atualizado_em = excluded.atualizado_em",
        (
            a.student_id,
            a.velocidade_media_s,
            a.taxa_abandono,
            a.erros_seguidos,
            a.desempenho_relativo,
            a.respostas,
            _para_texto(a.ultimo_evento_em),
            a.ultimo_evento_id,
            _para_texto(a.atualizado_em),
        ),
    )
    t = atualizado.topico
    if t is not None:
        conn.execute(
            "INSERT INTO gemeo_topico (student_id, topic_id, rating_elo, tentativas, "
            "acertos, atualizado_em) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (student_id, topic_id) DO UPDATE SET "
            "rating_elo = excluded.rating_elo, "
            "tentativas = excluded.tentativas, "
            "acertos = excluded.acertos, "
            "atualizado_em = excluded.atualizado_em",
            (
                t.student_id,
                t.topic_id,
                t.rating_elo,
                t.tentativas,
                t.acertos,
                _para_texto(t.atualizado_em),
            ),
        )
    e = atualizado.exercicio
    if e is not None:
        conn.execute(
            "INSERT INTO gemeo_exercicio (student_id, exercise_id, tentativas, "
            "acertou_alguma_vez) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (student_id, exercise_id) DO UPDATE SET "
            "tentativas = excluded.tentativas, "
            "acertou_alguma_vez = excluded.acertou_alguma_vez",
            (e.student_id, e.exercise_id, e.tentativas, int(e.acertou_alguma_vez)),
        )


def apagar_aluno(conn: sqlite3.Connection, student_id: str) -> None:
    """Remove o gêmeo de um aluno (as três tabelas). Nunca faz commit."""
    for tabela in ("gemeo_exercicio", "gemeo_topico", "gemeo_aluno"):
        conn.execute(f"DELETE FROM {tabela} WHERE student_id = ?", (student_id,))


def apagar_tudo(conn: sqlite3.Connection) -> None:
    """Remove o gêmeo de todos os alunos. Nunca faz commit."""
    for tabela in ("gemeo_exercicio", "gemeo_topico", "gemeo_aluno"):
        conn.execute(f"DELETE FROM {tabela}")
