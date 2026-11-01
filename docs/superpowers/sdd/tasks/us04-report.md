# US4 (Elo): report

**Status:** DONE
**Branch:** feat/us04-elo (worktree /home/igorg/facul/aprendizado/behavioral-digital-twin/.worktrees/us04), based on main 6dedccb
**PR:** https://github.com/Bolodarie/behavioral-digital-twin/pull/3 (base main, not merged)

## What was implemented

- `gemeo/elo.py`: constants `RATING_INICIAL = 1000.0`, `K = 32.0`, `ESCALA = 400.0`; functions:
  - `rating_do_exercicio(dificuldade) -> float`: `800 + 100*(d-1)`, `ValueError` outside 1..5.
  - `expectativa(rating_aluno, rating_exercicio) -> float`: `1 / (1 + 10 ** ((rating_exercicio - rating_aluno) / ESCALA))`.
  - `novo_rating(rating_aluno, rating_exercicio, acertou) -> float`: `rating_aluno + K * (resultado - expectativa)`.
- Module is pure: no imports, no SQL, no clock. Formulas match the brief and spec section 7 literally.
- `tests/test_elo.py`: 9 tests (constants, difficulty mapping, out-of-range `ValueError` for 0 and 6, expectation values, symmetry, equal hit/miss deltas, hard hit gains more than easy hit, easy miss loses more than hard miss).

## TDD evidence

RED (before `gemeo/elo.py` existed):

```
$ .venv/bin/python -m pytest tests/test_elo.py -q
ERROR collecting tests/test_elo.py
E   ModuleNotFoundError: No module named 'gemeo.elo'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

GREEN (after the implementation):

```
$ .venv/bin/python -m pytest tests/test_elo.py -v
collected 9 items ... 9 passed in 0.01s

$ .venv/bin/python -m pytest -q
17 passed in 0.01s
```

Baseline before the change was 8 passed (architecture test). The 17 total = 8 + 9.

## Files changed

- `gemeo/elo.py` (new)
- `tests/test_elo.py` (new)

Commit: `d49daa3 feat(F2/US4): add Elo rating module` (single commit, so no red commit in history). No attribution in commit, files or PR.

## Self-review findings

- Diff reviewed: no extra code, no imports, formulas exact, no attribution strings (grep checked).
- Numeric checks: `expectativa(1000,1200)=0.240253`, `novo_rating(1000,1200,True)=1024.3120`, `novo_rating(1000,1000,True/False)=1016.0/984.0`.

## Concerns (not blocking)

- `rating_do_exercicio(True)` returns `800.0`, because `bool` subclasses `int`. The brief does not require rejecting bools. Ingestion (US8) validates types strictly, so this is not a practical risk here. Can be tightened later if wanted.
- Pushed with `git push -u origin feat/us04-elo`. Nothing merged, nothing pushed elsewhere. Brief's PR body requirements followed (Feature/US, what changes, how to test, acceptance criteria, no AI signature).

## Notes

- The brief's "ask first" clause: nothing in the brief was unclear, so no questions were raised.
- The PR body was written to a temporary file for `gh pr create --body-file` and then removed.
