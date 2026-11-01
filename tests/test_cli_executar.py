"""CLI do pipeline: processa pendentes, ou reprocessa tudo, e imprime o resumo."""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import db
from ingestao.receber import receber
from ingestao.simulador import simular
from pipeline.executar import main
from tests.utilitarios import dump_gemeo

RAIZ = Path(__file__).resolve().parent.parent
INICIO = datetime(2026, 1, 5, tzinfo=timezone.utc)


def _resumo(saida: str) -> dict[str, int]:
    linhas = saida.strip().splitlines()
    assert [l.split(":")[0] for l in linhas] == [
        "processados",
        "rejeitados",
        "alunos_reconstruidos",
    ]
    return {l.split(": ")[0]: int(l.split(": ")[1]) for l in linhas}


def _popular(caminho, semente=1, alunos=3, dias=7) -> int:
    eventos = simular(semente, alunos, INICIO, dias).eventos
    conn = db.abrir(caminho)
    try:
        for evento in eventos:
            assert receber(conn, evento).status == "aceito"
    finally:
        conn.close()
    return len(eventos)


def _dump(caminho):
    conn = db.abrir(caminho)
    try:
        return dump_gemeo(conn)
    finally:
        conn.close()


def test_cli_processa_e_imprime(tmp_path, capsys):
    banco = tmp_path / "t.db"
    total = _popular(banco)

    assert main(["--db", str(banco)]) == 0

    assert _resumo(capsys.readouterr().out) == {
        "processados": total,
        "rejeitados": 0,
        "alunos_reconstruidos": 0,
    }
    conn = db.abrir(banco)
    try:
        pendentes = conn.execute(
            "SELECT COUNT(*) FROM eventos_brutos WHERE status = 'pendente'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert pendentes == 0
    assert _dump(banco) != []


def test_cli_reprocessar_chega_ao_mesmo_estado(tmp_path, capsys):
    banco = tmp_path / "t.db"
    total = _popular(banco)
    assert main(["--db", str(banco)]) == 0
    capsys.readouterr()
    antes = _dump(banco)

    assert main(["--db", str(banco), "--reprocessar"]) == 0

    assert _resumo(capsys.readouterr().out)["processados"] == total
    assert _dump(banco) == antes


def test_cli_banco_novo_sem_pendentes_imprime_zeros(tmp_path, capsys):
    banco = tmp_path / "novo.db"

    assert main(["--db", str(banco)]) == 0

    assert _resumo(capsys.readouterr().out) == {
        "processados": 0,
        "rejeitados": 0,
        "alunos_reconstruidos": 0,
    }
    assert banco.exists()


def test_python_m_pipeline_executar_funciona(tmp_path):
    banco = tmp_path / "t.db"
    _popular(banco, alunos=1, dias=3)

    resultado = subprocess.run(
        [sys.executable, "-m", "pipeline.executar", "--db", str(banco)],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert _resumo(resultado.stdout)["processados"] > 0
