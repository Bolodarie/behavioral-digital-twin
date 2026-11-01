"""CLI de simulação: gera eventos e os entrega à ingestão (design, seção 9).

Único ponto da ingestão que lê o relógio real: o padrão de `--inicio` é
`agora - dias`, para a simulação terminar "agora".
"""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db
from ingestao.receber import receber
from ingestao.simulador import simular


def _instante_com_fuso(texto: str) -> datetime:
    try:
        instante = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"data/hora ISO invalida: {texto!r}") from None
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            f"--inicio precisa ter fuso horario (ex.: 2026-01-05T00:00:00Z): {texto!r}"
        )
    return instante


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ingestao.simular",
        description="Simula alunos e grava os eventos em eventos_brutos.",
    )
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--alunos", type=int, default=12)
    parser.add_argument("--dias", type=int, default=42)
    parser.add_argument(
        "--inicio",
        type=_instante_com_fuso,
        default=None,
        help="ISO com fuso; padrao: agora menos --dias",
    )
    parser.add_argument(
        "--defeitos", action="store_true", help="inclui duplicados, desordem e malformados"
    )
    parser.add_argument("--db", type=Path, default=db.DEFAULT_DB_PATH)
    args = parser.parse_args(argv)
    if args.alunos < 1:
        parser.error("--alunos deve ser >= 1")
    if args.dias < 1:
        parser.error("--dias deve ser >= 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    inicio = args.inicio or datetime.now(timezone.utc) - timedelta(days=args.dias)
    simulacao = simular(args.semente, args.alunos, inicio, args.dias, defeitos=args.defeitos)

    contagem = {"aceito": 0, "duplicado": 0, "rejeitado": 0}
    conn = db.abrir(args.db)
    try:
        for evento in simulacao.eventos:
            contagem[receber(conn, evento).status] += 1
    finally:
        conn.close()

    print(f"aceitos: {contagem['aceito']}")
    print(f"duplicados: {contagem['duplicado']}")
    print(f"rejeitados: {contagem['rejeitado']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
