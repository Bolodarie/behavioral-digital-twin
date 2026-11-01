# US10 report

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/12 (branch feat/us10-defeitos-cli, not merged).

## Implemented
- `ingestao/simulador.py`: `simular(..., defeitos=False)`. `_aplicar_defeitos` is a post-processing step over the finished valid list, using `random.Random(f"defeitos-{semente}")` (separate stream). Duplicates (~5%, deepcopy of same dict, inserted after the original), shuffled windows of 20 (p=0.25 each, plus a guaranteed inversion of the first two arrivals if no window changed order), 10 malformed events (2 each of: sem_fuso, tempo_zero, acertou_texto, sem_event_id, exercicio_inexistente) built from a fixed template with fresh event_ids (never colliding with valid ones). With defeitos=False output unchanged.
- `ingestao/simular.py`: CLI `main(argv)` with --semente/--alunos/--dias/--inicio/--defeitos/--db; real clock only for default `--inicio`; closes DB in `finally`; prints the 3 lines; `--inicio` naive -> argparse error (exit 2); `python -m ingestao.simular` works. Imports only db, ingestao.receber, ingestao.simulador.

## Tests
- tests/test_simulador_defeitos.py (7): preserves valid events (+ skill/profile equality), reproducible, duplicates, non-chronological, >=3 malformed kinds failing Evento.model_validate (unknown exercise is the 5th kind; it passes model_validate and is rejected by receber's catalog check), sem defeitos cronologico.
- tests/test_cli_simular.py (5): summary matches eventos_brutos, defects show duplicados/rejeitados > 0, accepted count equal with/without defects, naive --inicio exit 2, runs as module.
- Full suite: 215 passed. Demo: `--defeitos` -> aceitos 1828, duplicados 91, rejeitados 10.

## TDD
- RED: `$PY -m pytest tests/test_simulador_defeitos.py -q` -> 7 failed, `TypeError: simular() got an unexpected keyword argument 'defeitos'`; `tests/test_cli_simular.py` -> `ModuleNotFoundError: No module named 'ingestao.simular'`.
- GREEN: `$PY -m pytest tests/test_simulador_defeitos.py tests/test_simulador.py -q` -> 38 passed; `tests/test_cli_simular.py` -> 5 passed; full suite 215 passed.

## Commits
- feat(ingestao): add defects option to the simulator
- feat(ingestao): add simulation CLI

## Files
ingestao/simulador.py, ingestao/simular.py, tests/test_simulador_defeitos.py, tests/test_cli_simular.py

## Self-review / concerns
- Design doc says CLIs have no `__main__`; the brief requires `python -m` so `__main__` was added (design doc not edited; US16 may want to align it).
- Because every malformed event has a fresh/no event_id, rejected rows never shadow valid events; accepted count is identical with and without defects (tested).
- Duplicates may arrive before or after their original; both orders are harmless since the dicts are identical.
