"""Compara a habilidade verdadeira (simulador) com o rating Elo do gêmeo.

Script de composição: simula, ingere num banco temporário, processa e mostra
a tabela e a correlação de Spearman por tópico. Serve de evidência de que o
Elo converge para a habilidade que gerou os dados.
"""
import argparse
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import db
from ingestao.receber import receber
from ingestao.simulador import Simulacao, simular
from pipeline.consumidor import processar_pendentes
from tests.utilitarios import spearman

INICIO_PADRAO = "2026-01-05T00:00:00Z"
MIN_TENTATIVAS = 5  # amostra mínima do aluno no tópico
MIN_ALUNOS = 6  # alunos mínimos no tópico para calcular a correlação


@dataclass(frozen=True)
class LinhaComparacao:
    student_id: str
    perfil: str
    topic_id: str
    habilidade_verdadeira: float
    rating_elo: float
    tentativas: int


def comparar(conn: sqlite3.Connection, simulacao: Simulacao) -> list[LinhaComparacao]:
    """Uma linha por par aluno x tópico que tem tentativas no gêmeo."""
    linhas = conn.execute(
        "SELECT student_id, topic_id, rating_elo, tentativas FROM gemeo_topico "
        "WHERE tentativas > 0 ORDER BY student_id, topic_id"
    ).fetchall()
    return [
        LinhaComparacao(
            student_id=l["student_id"],
            perfil=simulacao.perfis[l["student_id"]],
            topic_id=l["topic_id"],
            habilidade_verdadeira=simulacao.habilidades_finais[l["student_id"]][l["topic_id"]],
            rating_elo=l["rating_elo"],
            tentativas=l["tentativas"],
        )
        for l in linhas
    ]


def _instante_com_fuso(texto: str) -> datetime:
    try:
        instante = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"data/hora ISO invalida: {texto!r}") from None
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise argparse.ArgumentTypeError(f"--inicio precisa ter fuso horario: {texto!r}")
    return instante


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.comparar_habilidades",
        description="Compara habilidade verdadeira e rating Elo por tópico.",
    )
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--alunos", type=int, default=12)
    parser.add_argument("--dias", type=int, default=42)
    parser.add_argument(
        "--inicio",
        type=_instante_com_fuso,
        default=_instante_com_fuso(INICIO_PADRAO),
        help=f"ISO com fuso; padrao fixo ({INICIO_PADRAO}) para a saida ser reproduzivel",
    )
    args = parser.parse_args(argv)
    if args.alunos < 1:
        parser.error("--alunos deve ser >= 1")
    if args.dias < 1:
        parser.error("--dias deve ser >= 1")
    return args


def _tabela(linhas: list[LinhaComparacao]) -> list[str]:
    saida = [
        f"{'aluno':<10} {'perfil':<11} {'topico':<18} {'verdadeira':>10} {'elo':>9} {'tentativas':>10}"
    ]
    for l in linhas:
        saida.append(
            f"{l.student_id:<10} {l.perfil:<11} {l.topic_id:<18} "
            f"{l.habilidade_verdadeira:>10.1f} {l.rating_elo:>9.1f} {l.tentativas:>10}"
        )
    return saida


def _correlacoes(linhas: list[LinhaComparacao]) -> list[str]:
    saida = [
        f"Spearman por topico (alunos com >= {MIN_TENTATIVAS} tentativas; "
        f"minimo de {MIN_ALUNOS} alunos):"
    ]
    topicos = sorted({l.topic_id for l in linhas})
    for topico in topicos:
        amostra = [l for l in linhas if l.topic_id == topico and l.tentativas >= MIN_TENTATIVAS]
        if len(amostra) < MIN_ALUNOS:
            saida.append(f"  {topico:<18} amostra insuficiente ({len(amostra)} alunos)")
            continue
        rho = spearman(
            [l.habilidade_verdadeira for l in amostra], [l.rating_elo for l in amostra]
        )
        saida.append(f"  {topico:<18} {rho:+.3f}  ({len(amostra)} alunos)")
    return saida


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    simulacao = simular(args.semente, args.alunos, args.inicio, args.dias)

    with tempfile.TemporaryDirectory() as pasta:
        conn = db.abrir(Path(pasta) / "comparacao.db")
        try:
            for evento in simulacao.eventos:
                receber(conn, evento)
            processar_pendentes(conn)
            linhas = comparar(conn, simulacao)
        finally:
            conn.close()

    print("\n".join(_tabela(linhas)))
    print()
    print("\n".join(_correlacoes(linhas)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
