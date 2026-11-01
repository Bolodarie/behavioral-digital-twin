# US16 report

Status: DONE. Branch feat/us16-documentacao, commit a450b12 "docs: final README and CLAUDE.md", pushed to origin. `gh pr create` was DENIED by the permission classifier (Out-of-Place Publication); PR NOT opened. The controller should open it (title "feat(F6/US16): README e CLAUDE.md finais", base main; body drafted in pt-BR: Feature/US, what changes, how to test, acceptance criteria, no signature).

## Real runs (temp DB under scratchpad, never in the repo)
- simular (--semente 42 --alunos 12 --dias 42 --inicio 2026-01-05T00:00:00Z --defeitos): aceitos 1828, duplicados 91, rejeitados 10 (2 each: sem fuso, tempo_gasto_s zero, acertou texto, sem event_id, exercicio inexistente).
- executar: processados 1828, rejeitados 0, alunos_reconstruidos 0. Second run: 0/0/0. --reprocessar: 1828/0/0; hash of the three twin tables identical before and after.
- API with uvicorn (real server, curl worked; port 8000 was already taken so verified on 18765): /saude 200, aluno-001/gemeo (prob. evasao 0.0932), aluno-003/recomendacao (evasao 0.8844, equacao_2_grau-1, expectativa 0.6757), aluno-001/recomendacao (equacao_1_grau-4, dif. 5, 0.276), aluno-999/gemeo 404. JSON blocks in the README are byte-identical to `python -m json.tool --no-ensure-ascii` output.
- scripts.comparar_habilidades: 48 rows + Spearman (+0.467, +0.345, +0.050, +0.467); README shows the 16 `dedicado` rows verbatim (verified by string match) and the full Spearman block.

## Verification of README commands
Ran verbatim in a copy of the worktree (scratchpad/copy, so data/ stayed clean): pip install -r requirements-dev.txt, pytest (282 passed, 1 warning), the simular/executar/--reprocessar commands, uvicorn with GEMEO_AGORA + the 3 curls (only the port differs), scripts.comparar_habilidades. Suite also green in the worktree (282 passed).

## Limitations verified against main
- corrupt payload_json pending row -> listar_pendentes raises JSONDecodeError (whole queue).
- SQLite file without twin tables: /saude 200, /gemeo 500; missing file: 503 on both.
- Zero events: `--semente 5 --alunos 1 --dias 1` prints aceitos: 0; desistente emits nothing with --dias <= 2 (int(dias*0.4) == 0).
- reprocessar_tudo commit-then-reapply, processado_em rewritten on rebuild, insert-only events, 1 s resolution, Starlette/httpx deprecation warning: confirmed from code and pytest output.

## Discrepancies / notes
- Design §9 says rerunning is idempotent in spirit; in practice rerunning simular with --defeitos returns duplicados 1927 and rejeitados 2: the 2 malformed events without event_id cannot be deduplicated and are rejected again as new rows. README says so (not "everything duplicate").
- With --defeitos the CLI demo shows alunos_reconstruidos: 0 because all events are ingested before the first processing (the batch is sorted). Reconstruction needs a late event after processing; README explains this (covered by tests/test_reconstrucao.py).
- Design §8 mentions the recommendation target when expectativa cannot reach 0.85; README documents the actual behavior (aluno-003 gets 0.68, the best possible).
- README measured convergence numbers (0.416 aggregate / 0.232 per topic) are quoted from the comment in tests/test_ponta_a_ponta.py (seeds 42 and 1..7, minimum), not re-measured.
- CLAUDE.md mentions the "no AI attribution" rule in words; the README mentions nothing about authorship.
