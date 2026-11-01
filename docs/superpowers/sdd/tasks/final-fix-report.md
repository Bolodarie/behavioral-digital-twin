# Final fix wave report (branch fix/final-review-wave, from main fc69656)

Final `pytest` output (full suite, no `filterwarnings`): `288 passed in 17.5s` (no "warnings summary" section; 0 warnings). Baseline was 282 tests.

## Commits
- 7206c08 chore: add httpx2 to dev requirements to silence Starlette warning
- c1e6228 fix: probe gemeo_aluno on read-only open and answer 503 for foreign SQLite files
- 5f06f61 refactor: forbid importing tests from any layer and move spearman to scripts.estatistica
- 4cb47e3 fix: rebuild the student twin when processar_evento receives a late event
- 42f9254 docs: align README, CLAUDE.md and spec with late-event rebuild, clock, SQL and determinism wording

## Per finding
### 3 httpx2
`httpx2` added to requirements-dev.txt (httpx kept), installed in the shared venv (httpx2 2.14.0). Suite had 282 passed and no warnings right after install. Removed README "Um aviso de terceiros" bullet; CLAUDE.md had no such line, only the dev-deps mentions (updated to list httpx2).

### 4 read-only probe
Choice: probe lives in `db.abrir_somente_leitura` (every endpoint and any caller benefits). It runs `SELECT 1 FROM gemeo_aluno LIMIT 1`; any `sqlite3.Error` (OperationalError "no such table" included) becomes `BancoIndisponivel` -> existing 503 handler (`{"detail": "banco indisponivel"}`), and the connection is closed before raising (leak fixed). `/saude` body no longer repeats a query (the dependency already proved it). Tests: `test_sqlite_sem_tabelas_do_gemeo_da_503` (API: /saude, /gemeo, /recomendacao all 503 with the detail body) and `test_somente_leitura_sem_tabelas_do_gemeo` (db: raises and the spied connection is closed). RED: both failed before the change (200/500 and DID NOT RAISE); GREEN after. README limitation bullet removed; README API paragraph now says 503 also for missing twin tables. CLAUDE.md did not mention it.

### 2 dependency test + spearman
`tests/test_arquitetura.py`: `MODULOS_DO_PROJETO = set(PERMITIDO) | {"tests"}`; added a `scripts` entry in `PERMITIDO` (may compose all layers, never `tests`) and `scripts` to the verified packages, so `scripts/` is now actually scanned (previously it was out entirely, which is also why the backwards edge went unseen). New verifier tests: `test_nenhuma_camada_pode_importar_tests` (plain, `import tests`, importlib form, every layer), `test_scripts_podem_compor_camadas_mas_nao_importar_tests`. The real-project test passes. `spearman` and `_postos` moved verbatim to `scripts/estatistica.py` (stdlib only); `scripts/comparar_habilidades.py`, `tests/test_ponta_a_ponta.py`, `tests/test_utilitarios.py` import from there; `tests/utilitarios.py` keeps only `dump_gemeo`. README/CLAUDE.md: the dependency block now says `recomendacao -> gemeo (sem gemeo.repositorio; na prática só elo e evasao)`, plus a sentence that the check is by import name and cannot see attribute access after a plain `import gemeo`; the "tests/ e scripts/ ficam de fora" sentence became "scripts/ também é verificado; só tests/ fica de fora"; folder tree mentions estatistica.py.
Note: the "RED" for the blind spot is the brief's own verification (`violacoes("pipeline", "from tests.utilitarios import spearman", ...) == []`); I did not re-run the old behavior.

### 1 processar_evento late event
Private `_processar(conn, event_id, agora) -> (resultado, processados, rejeitados)` now catches `EventoInvalido` (reject) and `EventoAtrasado` (calls `_reconstruir`, one transaction, same exactness) and returns `"reconstruido"` with the counts of pending events the rebuild consumed. `processar_evento` returns its first element; `processar_pendentes` uses all three (counting `alunos_reconstruidos` once per student per call by `evento.student_id`; consumed pendings are skipped by the status check as before). The `EventoAtrasado` class stays as an internal signal (docstring updated). The late check also lost its dead `or ""`.
Tests: replaced the two pinning the raise. `test_evento_atrasado_reconstroi_o_aluno_e_iguala_a_ordem_cronologica` (returns "reconstruido", both events processado, `dump_gemeo` == a second DB processed chronologically, then a second call gives "ignorado"); `test_empate_de_horario_decide_pelo_event_id` now asserts "reconstruido"; `test_processar_evento_isolado_reconstroi_em_vez_de_levantar` (replaces "continua levantando"; the test that EventoAtrasado is no longer raised is implicit: the call returns instead of `pytest.raises`); new `test_reconstrucao_por_processar_evento_atomica` (failure mid-rebuild leaves the twin and the pending status untouched, no open transaction). RED: 4 failed with `EventoAtrasado` raised at consumidor.py:89; GREEN: all pass, and the existing `test_processar_pendentes_conta_o_aluno_reconstruido_uma_vez` still passes unchanged. Docs: module docstring, README (return values, "Atrasado" paragraph), spec section on `processar_evento`, CLAUDE.md rule. The implementation plan (docs/superpowers/plans) was left as is (historical).

## Wording
- Clock: README and CLAUDE.md now say no twin value uses the clock; `recebido_em`, `processado_em` and the API's "agora" default to the real clock and accept an injected one; injected clocks must be timezone-aware. Verified against code: naive datetimes are read as local time by `astimezone` in the stamps (receber/consumidor); in the API a naive clock makes `agora - ultimo_evento_em` raise TypeError, so the text says "the API fails" rather than "local time" for it (more exact than the brief's phrasing).
- "até o último bit" (README intro and the guarantee paragraph): added "same environment: same machine and Python version; `10 **` and `math.exp` are not bit-identical across platforms".
- SQL: README now says twin/event-table SQL lives only in `gemeo/repositorio.py` (twin), `ingestao/receber.py` and `pipeline/fila.py` (events); infrastructure SQL is in `db.py` (schema, catalog, PRAGMAs, probe), `api/main.py` (`BEGIN`) and `scripts/comparar_habilidades.py` (one read SELECT). CLAUDE.md mirrors it.

## NOT NULL column
`gemeo_aluno.ultimo_evento_id TEXT NOT NULL` and the dead `or ""` dropped. No migration (CREATE IF NOT EXISTS leaves old DB files unchanged; twin tables are derived data, a fresh DB is the supported path); added a README limitation bullet "Sem migração de schema" and a test (`test_gemeo_aluno_exige_ultimo_evento_id`).

## Demo
simular (seed 42, 12 alunos, 42 dias, --defeitos) -> `pipeline.executar` (processados 1828, alunos_reconstruidos 0, as documented) -> API via TestClient: /saude ok, recomendacao 200.

## Concerns / decisions
- Added `scripts` to `PERMITIDO` and scanned it (beyond the literal brief) because "scripts also must not import tests" needed a real check.
- README keeps documenting `EventoAtrasado` nowhere publicly; it remains importable.
- Nothing pushed; no `git push`/`gh` attempted. Branch fix/final-review-wave has 5 local commits ready for the controller.
