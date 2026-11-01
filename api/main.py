"""API de leitura do gêmeo (design, seção 8).

Só leitura: cada requisição abre uma conexão somente leitura e a fecha ao final.
A probabilidade de evasão é calculada na hora, com o relógio injetado.
"""
import os
import sqlite3
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from db import DEFAULT_DB_PATH, BancoIndisponivel, abrir_somente_leitura
from gemeo import evasao, repositorio
from modelos import EstadoAluno, GemeoResposta, Recomendacao, TopicoResposta
from recomendacao.escolher import escolher

ALUNO_NAO_ENCONTRADO = "aluno nao encontrado"


def _agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    db_path: Path | str = DEFAULT_DB_PATH,
    agora: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Monta a aplicação; `agora` padrão é o relógio real (UTC)."""
    relogio = agora or _agora_utc
    app = FastAPI(title="Gêmeo digital do aluno", version="1.0")

    @app.exception_handler(BancoIndisponivel)
    async def _banco_indisponivel(_: Request, __: BancoIndisponivel) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "banco indisponivel"})

    # Dependência assíncrona de propósito: a conexão SQLite nasce, é usada e fecha
    # na mesma thread (a do laço de eventos); uma dependência síncrona poderia
    # rodar em outra thread do pool e o SQLite recusaria o uso.
    async def conexao() -> AsyncIterator[sqlite3.Connection]:
        conn = abrir_somente_leitura(db_path)
        try:
            # Leitura única e consistente: todas as consultas da requisição
            # veem o mesmo instante do banco, mesmo com o pipeline gravando.
            conn.execute("BEGIN")
            yield conn
        finally:
            conn.close()

    def _aluno_ou_404(conn: sqlite3.Connection, student_id: str) -> EstadoAluno:
        estado = repositorio.ler_aluno(conn, student_id)
        if estado is None:
            raise HTTPException(status_code=404, detail=ALUNO_NAO_ENCONTRADO)
        return estado

    @app.get("/saude")
    async def saude(_: sqlite3.Connection = Depends(conexao)) -> dict[str, str]:
        # `abrir_somente_leitura` já provou que o banco abre e tem o schema do gêmeo.
        return {"status": "ok"}

    @app.get("/alunos/{student_id}/gemeo", response_model=GemeoResposta)
    async def gemeo(
        student_id: str, conn: sqlite3.Connection = Depends(conexao)
    ) -> GemeoResposta:
        estado = _aluno_ou_404(conn, student_id)
        topicos = repositorio.ler_topicos(conn, student_id)
        return GemeoResposta(
            student_id=estado.student_id,
            ultimo_evento_em=estado.ultimo_evento_em,
            velocidade_media_s=estado.velocidade_media_s,
            probabilidade_evasao=evasao.probabilidade_evasao(estado, relogio()),
            topicos=[
                TopicoResposta(
                    topic_id=t.topic_id,
                    rating_elo=t.rating_elo,
                    tentativas=t.tentativas,
                    acertos=t.acertos,
                )
                for t in topicos
            ],
        )

    @app.get("/alunos/{student_id}/recomendacao", response_model=Recomendacao)
    async def recomendacao(
        student_id: str, conn: sqlite3.Connection = Depends(conexao)
    ) -> Recomendacao:
        estado = _aluno_ou_404(conn, student_id)
        return escolher(
            student_id,
            repositorio.ler_topicos(conn, student_id),
            repositorio.ler_exercicios_resolvidos(conn, student_id),
            evasao.probabilidade_evasao(estado, relogio()),
        )

    return app


def _relogio_do_ambiente(texto: str | None) -> Callable[[], datetime] | None:
    """Relógio fixo a partir de `GEMEO_AGORA` (ISO 8601 com fuso); falha alto se inválido."""
    if texto is None:
        return None
    try:
        momento = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"GEMEO_AGORA inválida (esperado ISO 8601 com fuso): {texto!r}") from exc
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError(f"GEMEO_AGORA precisa ter fuso horário: {texto!r}")
    fixo = momento.astimezone(timezone.utc)
    return lambda: fixo


app = create_app(
    db_path=os.environ.get("GEMEO_DB", DEFAULT_DB_PATH),
    agora=_relogio_do_ambiente(os.environ.get("GEMEO_AGORA")),
)
