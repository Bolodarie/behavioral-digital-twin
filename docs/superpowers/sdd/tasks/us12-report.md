# US12 report: evento atrasado, reprocessamento e CLI

Status: DONE_WITH_CONCERNS (branch pushed; PR NOT opened, see Concerns)

## Implemented
- `pipeline/fila.py`: `eventos_do_aluno` (non-rejected rows, SQL order `(occurred_at, event_id)`; a row that cannot become an `Evento` (bad JSON, invalid field, non-canonical `occurred_at` text) is marked `rejeitado` with a pt-BR motivo and skipped, R10), `devolver_todos_a_pendente` (only `processado` rows; `processado_em` cleared), helpers `rejeitar_na_reconstrucao`, `remarcar_processado`, `ids_pendentes_do_aluno`.
- `pipeline/consumidor.py`: `reconstruir_aluno` (one `BEGIN IMMEDIATE` transaction: `apagar_aluno`, reapply in key order, `EventoInvalido` rejects permanently and continues, all applied marked `processado` with refreshed `processado_em`; returns applied count); `reprocessar_tudo`; `processar_pendentes` now catches `EventoAtrasado`, rebuilds that student, counts `alunos_reconstruidos` once per student, and later pendings of that student are skipped by the existing status re-check (`ignorado`). Rebuild-resolved pending events are counted in `processados`/`rejeitados` of the summary. `processar_evento` still raises `EventoAtrasado` (public contract kept).
- `pipeline/executar.py`: `main(argv)`, `--db`, `--reprocessar`, prints the three lines, closes the connection in `finally`; `python -m pipeline.executar` works.
- `tests/test_consumidor.py`: US11's late-event test changed to call `processar_evento` (the batch no longer stops).

## Atomicity of reprocessar_tudo
The reset (`apagar_tudo` + `devolver_todos_a_pendente`) is a single transaction, so there is never an empty twin with "processed" events. The re-application then runs event by event via `processar_pendentes` (not one giant transaction): if interrupted, the twin is a consistent prefix in key order and rerunning `processar_pendentes` finishes it. Trade-off: readers (API) see a partial twin while reprocessing runs. A fully atomic version would need savepoints around the US11 core; judged not reasonable here.

## Tests
- `$PY -m pytest -q`: 270 passed (full suite, 1 unrelated starlette deprecation warning).
- New: `tests/test_reconstrucao.py` (all brief tests plus: processar_pendentes counts a rebuilt student once, processar_evento still raises, rejection during rebuild, 5 parametrized unreconstructable-row cases, rollback when failure happens on the 3rd event of a rebuild, `eventos_do_aluno` ordering/exclusion, `devolver_todos_a_pendente`), `tests/test_cli_executar.py` (3 brief tests + `python -m` subprocess). `dump_gemeo` lives in test_reconstrucao.py and is imported by the CLI test.
- TDD evidence. RED: `$PY -m pytest tests/test_reconstrucao.py tests/test_cli_executar.py -q` -> `ImportError: cannot import name 'reconstruir_aluno'` / `ModuleNotFoundError: No module named 'pipeline.executar'` (2 errors during collection). GREEN: after implementing, the same files plus test_consumidor passed; first run had 3 failures that were my test bug (`agora=` given a datetime instead of a callable), fixed in the tests; then full suite 270 passed.

## Files
Modified: `pipeline/fila.py`, `pipeline/consumidor.py`, `tests/test_consumidor.py`. Created: `pipeline/executar.py`, `tests/test_reconstrucao.py`, `tests/test_cli_executar.py`.
Commits: 5f2f0df feat(pipeline): rebuild a student's twin on late events and add full reprocess; 3486668 feat(pipeline): add executar CLI with --reprocessar. Pushed to origin/feat/us12-reconstrucao-cli.

## Self-review / concerns
- PR NOT created: `gh pr create` was denied by the permission classifier ("Out-of-Place Publication"); I did not work around it. PR body is below; open with `gh pr create --base main --title "feat(F4/US12): evento atrasado, reprocessamento e CLI do pipeline" --body-file <file>`.
- Left untouched (deferred US11 minors): `listar_pendentes` still raises for the whole queue if one pending row is unreconstructable (so `reprocessar_tudo` on a tampered `processado` row would raise; the rebuild path itself is tolerant); status-rollback test gap; `processar_evento` false "rejeitado" under a concurrent writer.
- Rebuild rewrites `processado_em` of all re-applied events (they were re-applied now).
- Non-canonical `occurred_at` text in a stored row is treated as unreconstructable so SQL text order and Python datetime order cannot disagree.

## PR body
## Feature e US
F3 Ingestão e simulação, US9: simulador (função pura).

## O que muda
- `ingestao/simulador.py`: `simular(semente, n_alunos, inicio, dias) -> Simulacao`, `PERFIS`, `rating_do_exercicio` e `probabilidade_base` (escala do Elo reimplementada de propósito, sem importar `gemeo`).
- Três perfis em rodízio: `dedicado` (estuda na maioria dos dias), `irregular` (lacunas de 4 a 7 dias), `desistente` (para antes da metade do período). Abandono e tempo gasto dependem do perfil e da dificuldade; a habilidade verdadeira só cresce com a prática.
- Saída determinística: `event_id` são UUIDs sorteados da semente, eventos ordenados por `(occurred_at, event_id)`, sem relógio, banco ou arquivo.
- Os eventos válidos saem de um único fluxo `random.Random(semente)`, deixando outro fluxo livre para os defeitos da US10.
- `tests/test_simulador.py`: testes de reprodutibilidade, validade contra `Evento` e catálogo, ordem e janela, início antes de resposta/abandono, perfis, abandono, habilidade e guarda contra divergência da escala do Elo.

## Como testar
`python -m pytest tests/test_simulador.py -q` e `python -m pytest -q`.

## Critérios de aceite
- Mesma semente gera eventos idênticos; sementes diferentes geram eventos diferentes.
- Todo evento passa em `Evento.model_validate` e é consistente com o catálogo.
- Cada exercício tentado tem `exercicio_iniciado` estritamente anterior à resposta ou ao abandono.
- Perfis, abandono e crescimento de habilidade se comportam como descrito; `ValueError` para entradas inválidas.
