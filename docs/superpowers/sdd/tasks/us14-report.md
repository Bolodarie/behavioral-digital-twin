# US14 report

Status: DONE (PR https://github.com/Bolodarie/behavioral-digital-twin/pull/11)
Commit: f03d8ff feat(api): add read-only recommendation and twin endpoints

## Implemented
- modelos.py: added TopicoResposta, GemeoResposta (nothing existing altered).
- api/main.py: create_app(db_path, agora); /saude, /alunos/{id}/gemeo, /alunos/{id}/recomendacao; BancoIndisponivel -> 503 {"detail": "banco indisponivel"}; unknown student -> 404 {"detail": "aluno nao encontrado"}; module-level `app` from GEMEO_DB / GEMEO_AGORA (invalid or tz-less -> ValueError on import).
- Read-only connection per request via an async yield dependency (so open/use/close happen in one thread; a sync dependency may run in a different pool thread and SQLite would refuse). `BEGIN` on the connection gives all reads of a request one consistent snapshot.
- tests/test_api.py: 17 tests; fixture follows ruling R9 (db.abrir + aplicar_evento + repositorio.salvar; no ingestao/pipeline). funcoes rating ~999.263, velocidade 90.0 confirmed.

## TDD
RED: `$PY -m pytest tests/test_api.py -q` -> `ModuleNotFoundError: No module named 'api.main'` (collection error).
GREEN: same command -> `17 passed`. Full suite: `179 passed` (was 162).

## Files
modelos.py, api/main.py, tests/test_api.py

## Self-review / concerns
- Architecture test passes (api imports only db, gemeo, modelos, recomendacao).
- Extra tests beyond the brief: topics ordering, evasion grows with time, limiar checked for both students over several `agora` values.
- `%2F` in student_id never reaches the route (decoded to a path separator) -> 404 from routing, body is the framework default, not the custom detail.
- Starlette emits a deprecation warning about httpx in TestClient (harmless).
- No concerns blocking.
