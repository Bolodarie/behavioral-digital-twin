"""Utilitários compartilhados pelos testes."""
import sqlite3


def dump_gemeo(conn: sqlite3.Connection) -> list[tuple]:
    """Todas as linhas das três tabelas do gêmeo, ordenadas e sem arredondar."""
    consultas = {
        "aluno": "SELECT * FROM gemeo_aluno ORDER BY student_id",
        "topico": "SELECT * FROM gemeo_topico ORDER BY student_id, topic_id",
        "exercicio": "SELECT * FROM gemeo_exercicio ORDER BY student_id, exercise_id",
    }
    return [
        (tabela, *tuple(linha))
        for tabela, sql in consultas.items()
        for linha in conn.execute(sql).fetchall()
    ]
