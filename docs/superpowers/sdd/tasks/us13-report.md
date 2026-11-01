# US13 report

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/10

## Implemented
- `modelos.py`: `ExercicioRecomendado`, `Recomendacao` (added only).
- `recomendacao/escolher.py`: `ALVO_PADRAO`, `ALVO_RECUPERACAO`, `LIMIAR_EVASAO`, `escolher(...)` pure, defaults to `catalogo.TOPICO_IDS` / `catalogo.EXERCICIOS`. Imports only `catalogo`, `gemeo.elo`, `modelos`.
- `tests/test_recomendacao.py`: 15 tests (brief list + constants test; motivo test parametrized). Per ruling R2, tests for 70%/85% use a=1300, b=1200.

## TDD
- RED: `$PY -m pytest tests/test_recomendacao.py -q` -> `ModuleNotFoundError: No module named 'recomendacao.escolher'` (collection error, 1 error).
- GREEN: same command -> `15 passed`. Full suite `$PY -m pytest -q` -> `162 passed` (includes architecture test).

## Commits
- e33451c feat(modelos): add recommendation contracts
- 41aa6bb feat(recomendacao): add pure exercise recommender

## Self-review
- Limiar strictly `>`. Tie on topic via `min` first-minimum over catalog order; tie on exercise via key `(abs(E-alvo), id)`.
- "tópico ainda não tentado" is decided by absence of the topic in `topicos`; a topic present with 0 attempts is "mais fraco" (the gemeo repo only creates topic rows on answers, so this is moot).
- Unknown topic ids in `topicos` or exercises whose topic is not in `topicos_catalogo` are ignored.
- Input order of `topicos` does not matter (tested). `resolvidos` is not mutated.

## Concerns
None.
