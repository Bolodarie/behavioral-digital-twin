# US3 report: catálogo e banco

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/4

## Implemented
- catalogo/dados.py + catalogo/__init__.py (re-exports): Topico, ExercicioCatalogo (frozen), TOPICOS, TOPICO_IDS, EXERCICIOS, exercicio_por_id, exercicios_do_topico. Ids f"{topico}-{n}", difficulties 1,2,3,5, 4 topics in plan order, pt-BR statements.
- db.py: DEFAULT_DB_PATH, abrir, abrir_somente_leitura, BancoIndisponivel; six tables per spec §5 (gemeo_aluno with ultimo_evento_id), CHECKs, UNIQUE event_id, two indexes; schema + catalog seeded idempotently (INSERT OR IGNORE) inside BEGIN IMMEDIATE.
- Tests: tests/test_catalogo.py (7), tests/test_db.py (13), including the briefed ones plus extra: FK enforcement/autocommit, dificuldade CHECK, index columns, ultimo_evento_id column, frozen dataclasses.

## TDD evidence
RED: `$PY -m pytest tests/test_catalogo.py tests/test_db.py -q` -> 2 collection errors (ImportError: cannot import name 'EXERCICIOS' from 'catalogo'; ModuleNotFoundError: No module named 'db').
GREEN: same command -> `20 passed`. Full suite `$PY -m pytest -q` -> `28 passed` (includes architecture test).

## Commits
- 427a32a feat(catalogo): topics and exercises seed
- 1fbf3cd feat(db): sqlite schema, seeded catalog and read-only connection

## Files
catalogo/__init__.py, catalogo/dados.py, db.py, tests/test_catalogo.py, tests/test_db.py

## Self-review
- catalogo imports only stdlib; db imports only catalogo (architecture test green).
- abrir closes the connection if schema creation fails; BancoIndisponivel raised on OSError/sqlite3.Error at open and on missing file in read-only.
- abrir_somente_leitura uses Path.resolve().as_uri() + ?mode=ro.

## Concerns
- None blocking. Notes: topic/exercise FKs are declared (foreign_keys=ON), so later USs must insert catalog-valid ids into gemeo_topico/gemeo_exercicio (eventos_brutos has no FKs, since raw invalid events must be storable). Statement-marker check in test_enunciados is a light heuristic.

## Fix round 1 (review findings 1 and 2)
Commit: d64966b fix(db): retry WAL switch on lock and wrap setup errors as BancoIndisponivel (pushed to PR #4).

Changes in db.py:
- New `_ativar_wal`: retries `PRAGMA journal_mode=WAL` on OperationalError containing "locked"/"busy", exponential backoff 5ms..100ms, bounded by `ESPERA_MAXIMA_S = 10.0`; other errors propagate immediately. Connection `timeout` also set to that value.
- `abrir`: all setup (mkdir, connect, WAL, foreign_keys, schema/seed) is inside one try; any `OSError`/`sqlite3.Error` closes the connection and raises `BancoIndisponivel` chained with `from exc` (also after lock retries are exhausted). Non-sqlite exceptions close the connection and propagate.

Covering tests (tests/test_db.py):
- `test_arquivo_corrompido_vira_banco_indisponivel` (junk-bytes file).
- `test_primeira_abertura_concorrente` (8 forked processes with a Barrier, fresh path, 5 rounds; every call must succeed and see 16 exercises).

RED: `$PY -m pytest tests/test_db.py -q` -> `2 failed, 13 passed` (corrupt file: raw sqlite3 error; concurrent: `OperationalError('database is locked')`).
GREEN: same command -> `15 passed` (run 3 times); concurrent test alone run 8 times -> all passed; full suite `$PY -m pytest -q` -> `30 passed`.

Concerns: none. The concurrency test uses the `fork` start method (Linux/macOS only).
