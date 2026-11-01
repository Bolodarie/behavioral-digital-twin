# US8 report: receber evento

PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/9 (branch feat/us08-receber)

## Implemented
`ingestao/receber.py`: `receber(conn, dado, *, agora=None) -> ResultadoIngestao`, following the brief's order (duplicate check -> Evento + catalog validation -> insert rejeitado/pendente), `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` per call, `INSERT OR IGNORE` with `rowcount` check. Uses real `eventos_brutos` columns from `db.py`. Imports only `modelos`, `catalogo`. Messages are ASCII Portuguese ("dado nao e um objeto", "exercicio inexistente no catalogo", "topic diverge do catalogo").
Details: event_id used only when a non-empty str; `bruto_json` falls back to `json.dumps(repr(dado))` when `sort_keys` fails (mixed-type keys); motivo from pydantic errors is "campo: mensagem; ..." truncated to 500; `payload_json` is `json.dumps(payload, sort_keys=True)`; `recebido_em` as `YYYY-MM-DDTHH:MM:SSZ`.

## Tests
`tests/test_receber.py`: 25 cases (all brief items plus: duplicate beats invalid resend, non-str event_id, mixed keys, long motivo truncated, no open transaction, default clock). Full suite: 108 passed.

## TDD evidence
RED: `$PY -m pytest tests/test_receber.py -q` -> `ModuleNotFoundError: No module named 'ingestao.receber'` (collection error), committed as `test(ingestao): add receber tests`.
GREEN: same command -> `25 passed`; then `$PY -m pytest -q` -> `108 passed`.

## Files
ingestao/receber.py, tests/test_receber.py

## Self-review
Diff reviewed. Removed a stray unused import. Validation happens before the transaction (pure), duplicate check inside it. Race between concurrent calls covered by `INSERT OR IGNORE` rowcount (not exercised by a concurrent test; only the logic path).

## Concerns
None blocking. The race path (rowcount == 0 after the pre-check) is not unit-tested because `BEGIN IMMEDIATE` serializes writers on one DB.

## Fix round 1 (ruling R8: hostile input becomes `rejeitado`, never an exception)

Changes in `ingestao/receber.py`:
- `_bruto_json` always returns valid UTF-8 JSON: `ensure_ascii=False`; if not UTF-8-encodable (lone surrogates) retry with `ensure_ascii=True`; on any exception (TypeError, ValueError, RecursionError...) fall back to a guarded `repr`-based JSON string, ending at `{"erro": "nao serializavel"}`.
- `_event_id_de` returns None when the id is not UTF-8-encodable (so the lookup/INSERT never receives it; row stores NULL).
- Motivos are sanitized (`backslashreplace`) so they are always encodable; `RecursionError` during validation gives "dado aninhado demais"; defensive check turns a valid event with non-encodable `event_id`/`student_id` into `rejeitado` ("texto com caracteres invalidos"). (Pydantic itself already rejects lone surrogates in strings, so that check is a backstop.)
- Genuine DB failures still do `ROLLBACK; raise`.

Tests (`tests/test_receber.py`, 41 total): deep dict/list nesting (5000 levels, as extra field and as whole dado); lone surrogate in event_id, student_id, extra field, payload value, payload key, exercise_id, topic, occurred_at, event_type, and as a dict key; clock that raises (propagates, `in_transaction` False, no row); failing insert via a RAISE trigger (propagates, rollback, no row, works again after dropping the trigger). Tightened: `"x: extra inputs"` motivo match; truncation test asserts `len(motivo) == 500` and matches the stored column.

RED: `$PY -m pytest tests/test_receber.py -q` -> `14 failed, 27 passed` (RecursionError / UnicodeEncodeError; the clock and trigger tests already passed since the rollback path was correct).
GREEN: same command -> `41 passed`; full suite `$PY -m pytest -q` -> `124 passed`.
Commits: 6de3844 test(ingestao): cover hostile input and rollback path; fcf809f fix(ingestao): turn hostile input into rejected rows (pushed to feat/us08-receber, PR #9).
