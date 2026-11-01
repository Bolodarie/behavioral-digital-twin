# US1 report: esqueleto do projeto e teste de arquitetura

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/1 (not merged).

## Implemented
- Config: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `data/.gitkeep`.
- Empty packages (`__init__.py`): catalogo, ingestao, pipeline, gemeo, recomendacao, api, scripts, tests.
- `tests/test_arquitetura.py`: `PERMITIDO` (design §3 exactly), `PROIBIDO_EXTRA` (recomendacao -> gemeo.repositorio), `nomes_importados`, `modulos_do_projeto_importados`, `violacoes`, `arquivos_do_projeto`, 7 verifier tests (the 5 from the brief + proibido apontado + permitido passa) and the real scan test. Handles Import, ImportFrom with level>0, importlib.import_module / __import__ (also bare `import_module`) with a literal; relative literals are resolved too. Non-existent files/packages are ignored (picked up when they appear). tests/ and scripts/ excluded.
- `README.md` draft (1 paragraph) and `CLAUDE.md` (dependency rule, decisions, commands), pt-BR.

## TDD evidence
- RED: `$PY -m pytest tests/test_arquitetura.py -v` -> `8 failed`, e.g. `NameError: name 'violacoes' is not defined` / `name 'arquivos_do_projeto' is not defined` (helpers not yet written).
- During GREEN, one bug caught by my own test: absolute imports were wrongly prefixed with the file's package (level 0); fixed in `_resolver_relativo`.
- GREEN: `$PY -m pytest tests/test_arquitetura.py -v` -> `8 passed in 0.02s`; full suite `$PY -m pytest -q` -> `8 passed`.
- Manual proof: temp `ingestao/tmp_ruim.py` (`from pipeline import x`) and `modelos.py` (`import catalogo`) made the real scan test fail with explicit messages; removed afterwards.

## Commits
- 9a75bbe chore: add project skeleton and config
- 93650c7 test: add layer dependency architecture test
- 68a7984 docs: add draft README and CLAUDE.md

## Self-review
- Diff is 16 files (+240); no AI attribution in commits/files (checked with grep; the only match is pre-existing plan text quoting the rule).
- Over-approximation by design: `from gemeo import repositorio` yields `gemeo.repositorio`, caught by the extra rule.

## Concerns
- None blocking. Dynamic imports with non-literal args are not detectable (accepted by the brief). A stray `cat` without stdin hung one shell call early on; no impact on the repo.
