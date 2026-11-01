# US2 report

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/2

## Implemented
- `modelos.py`: TipoEvento, Evento (extra=forbid, ids min_length=1, validador de occurred_at -> UTC, microsecond=0, sem fuso rejeitado; model_validator valida payload por tipo; propriedades occurred_at_texto/acertou/tempo_gasto_s), PayloadRespondido (StrictBool, StrictInt gt=0, extra=forbid), EstadoAluno/Topico/Exercicio, EstadoAtualizado, ResultadoIngestao. Sem imports do projeto.
- `tests/fabricas.py`: evento_dict conforme Interfaces.
- `tests/test_modelos.py`: todos os casos do brief (+ status fechado de ResultadoIngestao).

## TDD
- RED: `$PY -m pytest tests/test_modelos.py -q` -> `ModuleNotFoundError: No module named 'modelos'` (1 error in collection).
- GREEN: same command -> `24 passed`; full suite `$PY -m pytest -q` -> `32 passed`.

## Commits
- 6443f27 test: add event and state contract tests
- d322193 feat: add event and state Pydantic contracts

## Self-review
- Diff so only 3 new files. Architecture test passes.
- Choice: `ResultadoIngestao.event_id` and `.motivo` default to None (brief gave no defaults; more permissive for later USs).
- `payload` stays as the raw dict (validated, not normalized); acertou/tempo_gasto_s read from it.

## Concerns
None.

## Fix round 1
- Change: in `modelos.py`, the `occurred_at` validator now catches `OverflowError` from `astimezone` and raises `ValueError` (becomes `ValidationError`).
- Test: `test_occurred_at_fora_do_intervalo_vira_validation_error` (params `9999-12-31T23:59:59-05:00`, `0001-01-01T00:00:00+05:00`).
- RED: `$PY -m pytest tests/test_modelos.py -q` -> `2 failed, 24 passed` (OverflowError).
- GREEN: same command -> `26 passed`; full suite `$PY -m pytest -q` -> `34 passed`.
- Commit: 5749659 fix: reject out-of-range occurred_at as validation error. Pushed to feat/us02-contratos.
