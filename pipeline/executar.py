"""CLI do pipeline: processa os eventos pendentes ou reprocessa tudo.

Único ponto do pipeline que escolhe o banco; o relógio real só carimba
`processado_em` (nenhum valor do gêmeo depende dele).
"""
import argparse
from pathlib import Path

import db
from pipeline.consumidor import processar_pendentes, reprocessar_tudo


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.executar",
        description="Aplica os eventos pendentes ao gemeo digital.",
    )
    parser.add_argument("--db", type=Path, default=db.DEFAULT_DB_PATH)
    parser.add_argument(
        "--reprocessar",
        action="store_true",
        help="apaga o gemeo e reaplica todos os eventos nao rejeitados",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    conn = db.abrir(args.db)
    try:
        executar = reprocessar_tudo if args.reprocessar else processar_pendentes
        resumo = executar(conn)
    finally:
        conn.close()

    print(f"processados: {resumo.processados}")
    print(f"rejeitados: {resumo.rejeitados}")
    print(f"alunos_reconstruidos: {resumo.alunos_reconstruidos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
