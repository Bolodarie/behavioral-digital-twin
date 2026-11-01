"""Garante a regra de dependência entre camadas (design, seção 3).

Os testes do verificador usam trechos de código em string; o teste real
varre os arquivos do projeto. Módulos que ainda não existem são ignorados
e passam a ser verificados assim que aparecem.
"""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Quem cada camada pode importar (além de si mesma).
PERMITIDO: dict[str, set[str]] = {
    "ingestao": {"modelos", "db", "catalogo"},
    "pipeline": {"gemeo", "modelos", "db", "catalogo"},
    "gemeo": {"modelos", "db", "catalogo"},
    "recomendacao": {"gemeo", "modelos", "catalogo"},
    "api": {"recomendacao", "gemeo", "modelos", "db"},
    "db": {"catalogo"},
    "catalogo": set(),
    "modelos": set(),
    # scripts compõem camadas, mas nunca dependem de tests/
    "scripts": {
        "ingestao", "pipeline", "gemeo", "recomendacao", "api", "modelos", "db", "catalogo",
    },
}

# Regra extra: o recomendador só pode usar os módulos puros do gêmeo.
PROIBIDO_EXTRA: dict[str, set[str]] = {
    "recomendacao": {"gemeo.repositorio"},
}

# Módulos de primeiro nível que pertencem ao projeto (o resto é stdlib/terceiros).
# `tests` entra para que nenhuma camada (nem `scripts`) possa importá-lo.
MODULOS_DO_PROJETO = set(PERMITIDO) | {"tests"}

# O que é verificado: tudo exceto tests/ (o código de teste pode importar qualquer coisa).
ARQUIVOS_VERIFICADOS = ["modelos.py", "db.py"]
PACOTES_VERIFICADOS = [
    "catalogo", "ingestao", "pipeline", "gemeo", "recomendacao", "api", "scripts",
]


# --- verificador ------------------------------------------------------------

def _resolver_relativo(pacote_do_arquivo: str, nivel: int, modulo: str | None) -> str:
    """Resolve `from <.>*modulo import ...` para um nome absoluto (pode ser vazio)."""
    if nivel == 0:
        return modulo or ""
    partes = pacote_do_arquivo.split(".") if pacote_do_arquivo else []
    if nivel > 1:
        partes = partes[: len(partes) - (nivel - 1)]
    if modulo:
        partes += modulo.split(".")
    return ".".join(partes)


def _literal_da_chamada_dinamica(no: ast.Call) -> str | None:
    """Devolve o literal de `importlib.import_module("x")` / `__import__("x")`."""
    func = no.func
    nome = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if nome not in ("import_module", "__import__") or not no.args:
        return None
    arg = no.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def nomes_importados(codigo: str, pacote_do_arquivo: str) -> set[str]:
    """Todos os nomes pontuados importados pelo código, com relativos resolvidos."""
    nomes: set[str] = set()
    for no in ast.walk(ast.parse(codigo)):
        if isinstance(no, ast.Import):
            nomes.update(alias.name for alias in no.names)
        elif isinstance(no, ast.ImportFrom):
            base = _resolver_relativo(pacote_do_arquivo, no.level, no.module)
            if base:
                nomes.add(base)
            for alias in no.names:
                nomes.add(f"{base}.{alias.name}" if base else alias.name)
        elif isinstance(no, ast.Call):
            literal = _literal_da_chamada_dinamica(no)
            if literal is None:
                continue
            nivel = len(literal) - len(literal.lstrip("."))
            nomes.add(_resolver_relativo(pacote_do_arquivo, nivel, literal[nivel:]))
    return nomes


def modulos_do_projeto_importados(codigo: str, pacote_do_arquivo: str) -> set[str]:
    """Módulos de primeiro nível do projeto que o código importa."""
    primeiros = {nome.split(".")[0] for nome in nomes_importados(codigo, pacote_do_arquivo)}
    return primeiros & MODULOS_DO_PROJETO


def violacoes(dono: str, codigo: str, pacote_do_arquivo: str) -> list[str]:
    """Imports que `dono` (camada do arquivo) não pode fazer."""
    problemas = []
    permitidos = PERMITIDO[dono] | {dono}
    for modulo in sorted(modulos_do_projeto_importados(codigo, pacote_do_arquivo) - permitidos):
        problemas.append(f"importa '{modulo}', proibido para '{dono}'")
    for nome in sorted(nomes_importados(codigo, pacote_do_arquivo)):
        for proibido in PROIBIDO_EXTRA.get(dono, set()):
            if nome == proibido or nome.startswith(proibido + "."):
                problemas.append(f"importa '{nome}', proibido para '{dono}'")
    return problemas


def arquivos_do_projeto() -> list[Path]:
    """Arquivos .py que existem hoje entre os verificados (os ausentes são ignorados)."""
    arquivos = [RAIZ / nome for nome in ARQUIVOS_VERIFICADOS if (RAIZ / nome).is_file()]
    for pacote in PACOTES_VERIFICADOS:
        arquivos += sorted((RAIZ / pacote).rglob("*.py"))
    return arquivos


# --- testes do verificador -------------------------------------------------

def test_detecta_import_simples():
    assert modulos_do_projeto_importados("import pipeline.executar", "") == {"pipeline"}


def test_detecta_from_import():
    codigo = "from gemeo.elo import expectativa"
    assert modulos_do_projeto_importados(codigo, "") == {"gemeo"}


def test_detecta_importlib_e_dunder_import():
    codigo = (
        "import importlib\n"
        "a = importlib.import_module('api')\n"
        "b = __import__('pipeline')\n"
    )
    assert modulos_do_projeto_importados(codigo, "") == {"api", "pipeline"}


def test_import_relativo_e_resolvido():
    assert modulos_do_projeto_importados("from .. import pipeline", "ingestao") == {"pipeline"}
    assert modulos_do_projeto_importados("from . import simulador", "ingestao") == {"ingestao"}


def test_ignora_stdlib_e_terceiros():
    assert modulos_do_projeto_importados("import sqlite3, pydantic", "") == set()


def test_import_proibido_e_apontado():
    assert violacoes("ingestao", "from pipeline import consumidor", "ingestao") != []
    assert violacoes("gemeo", "import importlib\nimportlib.import_module('api')", "gemeo") != []
    assert violacoes("recomendacao", "from gemeo.repositorio import ler", "recomendacao") != []
    assert violacoes("recomendacao", "from gemeo import repositorio", "recomendacao") != []


def test_import_permitido_passa():
    assert violacoes("recomendacao", "from gemeo.elo import expectativa", "recomendacao") == []
    assert violacoes("api", "from gemeo import repositorio", "api") == []
    assert violacoes("gemeo", "from . import elo", "gemeo") == []


def test_nenhuma_camada_pode_importar_tests():
    for dono in PERMITIDO:
        assert violacoes(dono, "from tests.utilitarios import dump_gemeo", dono) != []
        assert violacoes(dono, "import tests", dono) != []
        assert violacoes(dono, "import importlib\nimportlib.import_module('tests.fabricas')", dono) != []


def test_scripts_podem_compor_camadas_mas_nao_importar_tests():
    assert violacoes("scripts", "from pipeline.consumidor import processar_pendentes", "scripts") == []
    assert violacoes("scripts", "from scripts.estatistica import spearman", "scripts") == []
    assert violacoes("scripts", "from tests.utilitarios import spearman", "scripts") != []


# --- teste real -------------------------------------------------------------

def test_projeto_respeita_a_regra_de_dependencia():
    problemas = []
    for arquivo in arquivos_do_projeto():
        relativo = arquivo.relative_to(RAIZ)
        dono = relativo.parts[0].removesuffix(".py")
        pacote = ".".join(relativo.parts[:-1])
        problemas += [
            f"{relativo}: {p}"
            for p in violacoes(dono, arquivo.read_text(encoding="utf-8"), pacote)
        ]
    assert problemas == []
