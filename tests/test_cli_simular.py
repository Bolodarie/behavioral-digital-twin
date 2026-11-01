"""CLI de simulação: grava via `receber` e imprime o resumo."""
import subprocess
import sys
from pathlib import Path

import pytest

import db
from ingestao.simular import main

RAIZ = Path(__file__).resolve().parent.parent
BASE = ["--semente", "1", "--alunos", "3", "--dias", "7", "--inicio", "2026-01-05T00:00:00Z"]


def _resumo(saida: str) -> dict[str, int]:
    linhas = saida.strip().splitlines()
    assert [l.split(":")[0] for l in linhas] == ["aceitos", "duplicados", "rejeitados"]
    return {l.split(":")[0]: int(l.split(":")[1]) for l in linhas}


def _contagem(caminho, status: str) -> int:
    conn = db.abrir(caminho)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM eventos_brutos WHERE status = ?", (status,)
        ).fetchone()[0]
    finally:
        conn.close()


def test_cli_grava_e_imprime_resumo(tmp_path, capsys):
    banco = tmp_path / "t.db"
    assert main([*BASE, "--db", str(banco)]) == 0
    resumo = _resumo(capsys.readouterr().out)
    assert resumo["aceitos"] > 0
    assert resumo["duplicados"] == 0
    assert resumo["rejeitados"] == 0
    assert _contagem(banco, "pendente") == resumo["aceitos"]
    assert _contagem(banco, "rejeitado") == resumo["rejeitados"]


def test_cli_com_defeitos_mostra_duplicados_e_rejeitados(tmp_path, capsys):
    banco = tmp_path / "t.db"
    assert main([*BASE, "--defeitos", "--db", str(banco)]) == 0
    resumo = _resumo(capsys.readouterr().out)
    assert resumo["duplicados"] > 0
    assert resumo["rejeitados"] > 0
    assert _contagem(banco, "pendente") == resumo["aceitos"]
    assert _contagem(banco, "rejeitado") == resumo["rejeitados"]


def test_cli_defeitos_aceita_os_mesmos_eventos_que_sem_defeitos(tmp_path, capsys):
    main([*BASE, "--db", str(tmp_path / "a.db")])
    limpo = _resumo(capsys.readouterr().out)
    main([*BASE, "--defeitos", "--db", str(tmp_path / "b.db")])
    sujo = _resumo(capsys.readouterr().out)
    assert sujo["aceitos"] == limpo["aceitos"]


def test_cli_inicio_sem_fuso_da_erro_de_uso(tmp_path, capsys):
    argv = ["--inicio", "2026-01-05T00:00:00", "--db", str(tmp_path / "t.db")]
    with pytest.raises(SystemExit) as saida:
        main(argv)
    assert saida.value.code == 2
    assert "fuso" in capsys.readouterr().err


def test_cli_roda_como_modulo(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "ingestao.simular", *BASE, "--db", str(tmp_path / "t.db")],
        cwd=RAIZ, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert _resumo(proc.stdout)["aceitos"] > 0
