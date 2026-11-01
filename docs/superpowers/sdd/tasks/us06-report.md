# US6 report

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/6

## Implemented
`gemeo/atualizacao.py`: `ALFA = 0.2`, `aplicar_evento(...) -> EstadoAtualizado`, pure, using `model_copy`. Moving averages always `x + ALFA*(alvo-x)`, no rounding. Expectation E computed before the rating update. `atualizado_em` of the student = `ultimo_evento_em`; topic `atualizado_em` = event time. Last-event key advances only if `(occurred_at, event_id)` is strictly greater.

## Tests
`tests/test_atualizacao.py`: 9 tests (the 8 specified + erros_seguidos reset on hit). Focused: 9 passed. Full suite: 52 passed.

## TDD
RED: `$PY -m pytest tests/test_atualizacao.py -q` -> `ModuleNotFoundError: No module named 'gemeo.atualizacao'` (collection error).
GREEN: same command -> `9 passed in 0.05s`; full `$PY -m pytest -q` -> `52 passed`.

## Commits
116ca41 feat: apply events to the twin state as a pure function
234530e test: cover per-event twin updates
(Implementation committed before tests; RED/GREEN was run before committing.)

## Files
gemeo/atualizacao.py, tests/test_atualizacao.py (only these; `git diff 4f23bab HEAD` shows just them. Diff against the current local main also shows other US files because main moved.)

## Self-review / concerns
- Topic `atualizado_em` uses the event time even for non-advancing (late) events; the pipeline reconstructs on late events so this is not exercised.
- `dificuldade` is validated by `rating_do_exercicio` (ValueError if outside 1..5) only on respondido events.

## Fix round 1
Change: `_validar_entradas` at the top of `aplicar_evento` (gemeo/atualizacao.py). `dificuldade` must be an int (bool rejected) in 1..5 for ALL event types (reuses `rating_do_exercicio`); `ValueError` in pt-BR if `aluno`/`topico`/`exercicio` (only when not None) have a different `student_id`, `topic_id` or `exercise_id` than the event, messages cite the offending values.
Covering tests (tests/test_atualizacao.py): `test_dificuldade_invalida_e_rejeitada_em_todos_os_tipos` (3 types x 7 invalid values), `test_aluno_de_outro_student_id_e_rejeitado`, `test_topico_de_outro_aluno_ou_topico_e_rejeitado`, `test_exercicio_de_outro_aluno_ou_exercicio_e_rejeitado`.
RED: `$PY -m pytest tests/test_atualizacao.py -q` -> `21 failed, 12 passed`.
GREEN: same command -> `33 passed in 0.07s`; full `$PY -m pytest -q` -> `76 passed in 0.09s`.
Commit: fix: validate difficulty and state identity in aplicar_evento (pushed to feat/us06-atualizacao).
