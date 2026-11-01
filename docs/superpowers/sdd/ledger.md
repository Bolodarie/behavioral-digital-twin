# SDD ledger — plan: docs/superpowers/plans/2026-11-01-behavioral-digital-twin.md

Spec: docs/superpowers/specs/2026-10-31-behavioral-digital-twin-design.md (reachable).
Unit of work = US (one branch feat/usNN-*, one worktree .worktrees/usNN, one PR to main). Merge into main by the controller (squash) — AUTHORIZED by the user ("vc msm pode mergear tbm"), only after clean review + green suite.
Waves (max 3 parallel): 1:US1 | 2:US2,US3,US4 | 3:US5,US6,US7 | 4:US8,US9,US13 | 5:US10,US11,US14 | 6:US12,US15 | 7:US16
Brief helper: scratchpad/brief.sh N (plan headings are "### USn", so the stock task-brief script does not match).
Shared venv: <repo>/.venv (py3.10, pydantic 2.14, fastapi 0.162, pytest, httpx).

## Pre-flight scan (rows per task and per shared-file/interface pair)

| Row | Finding |
|---|---|
| US1 self | Tests define the checker helpers inside tests/test_arquitetura.py, so a literal "module missing" red step cannot happen. OK → Ruling R1. |
| US2 self | Tests vs interfaces agree (strict types, UTC, trunc). OK. |
| US3 self | Schema is delegated to spec §5 (+ultimo_evento_id); column names live only in the spec. OK if brief carries spec path → Ruling R4. |
| US4 self | Numbers re-derived: E(1000,1200)=0.24025, novo_rating(1000,1200,True)=1024.312. OK. |
| US5 self | Suggested weights re-derived: ativo p≈0.11 (<0.3), sumido p≈0.99 (>0.7). OK. |
| US6 self | Re-derived: step1 rating 1016.0, desempenho 0.1; step2 rating 999.263, vel 90.0, desempenho −0.0246; abandono 0.2 then 0.16. OK. |
| US7 self | OK. |
| US8 self | OK. Dup check before validation (documented). |
| US9 self | OK; needs strictly-earlier iniciado (1s resolution). |
| US10 self | Valid events must be unchanged by defeitos → needs independent RNG stream → Ruling R3. |
| US11 self | Numbers match US6. EventoAtrasado is an interim contract (US12 replaces). OK. |
| US12 self | OK. Rebuild must skip pending events already applied by rebuild (stated). |
| US13 self | test "rating 1200 em tópico com dificuldades 2,4,5" would pick topic `a` (untried=1000 < 1200) unless topic a is made stronger → Ruling R2. Re-derived: E(1200,d4)=0.64006, d2=0.8490, d5=0.5; target .70→d4, .85→d2. |
| US14 self | OK; relies on US11 event numbers. |
| US15 self | Needs US10 defeitos with unchanged valid events (R3). OK. |
| US16 self | OK. |
| US2↔US6/US7/US8/US13/US14 (modelos.py) | Producers/consumers consistent. US13 and US14 both edit modelos.py in different waves (4 vs 5). OK. |
| US3↔US7 (gemeo_* columns) | Names from spec §5 ↔ EstadoTopico/EstadoAluno/EstadoExercicio fields match. OK (R4). |
| US3↔US8↔US11 (eventos_brutos) | receber writes columns that fila reads (payload_json + columns rebuild Evento). OK (R4). |
| US6↔US11 (aplicar_evento) | Same signature; US11 imports name `aplicar_evento` into consumidor for monkeypatch. OK. |
| US9↔US10 (simulador.py) | US10 adds param `defeitos`; waves differ. OK. |
| US9↔US4 (escala Elo) | Guard test imports both. OK. |
| US11↔US12 (consumidor.py, fila.py) | US12 modifies; waves differ. OK. |
| US13↔US14 (escolher/Recomendacao) | API calls escolher with default catalog; no catalogo import in api. OK. |
| US1 matrix ↔ all packages | api→{recomendacao,gemeo,modelos,db}; pipeline→{gemeo,modelos,db,catalogo}; ingestao→{modelos,db,catalogo}. All US imports comply. OK. |

## Rulings
- Ruling R1: US1 TDD red = tests written first against undefined helpers (NameError), helpers then implemented in the same test file — plan wording "módulo ausente" read loosely — cost if wrong: none.
- Ruling R2: In US13 brief, make the topic `a` state rating 1300 so topic `b` (difficulties 2,4,5, rating 1200) is the weakest and the chosen one — otherwise the test's premise fails — cost if wrong: one fix round.
- Ruling R3: In US9/US10 briefs, defeitos must draw from a separate RNG stream (or post-process) so valid events are byte-identical with and without defeitos — cost if wrong: US15 exact-equality test fails.
- Ruling R4: Every dispatch carries the spec path; spec §5 is authoritative for table/column names — cost if wrong: schema drift between US3/US7/US8/US11.
- Ruling R5: Controller merges each US PR into main with squash after clean review + green suite, deletes the branch, then pulls main — authorized by the user.
- Ruling R6: Briefs are built by scratchpad/brief.sh (preamble + US text) instead of scripts/task-brief — headings differ.

## Progress
Task US1: dispatched implementer (sonnet, agent aea2ebd5cd441d550), BASE fbea59b, worktree .worktrees/us01
Task US1: implementer DONE (commits fbea59b..68a7984, PR #1); reviewer dispatched (sonnet, a256900aad67d653a)
Task US1: minor (deferred): arch-test violation asserts are `!= []` (don't pin which rule fired); unregistered future top-level modules go unverified (suggest guard); import_module(name=...) / package= arg not resolved; no alias-import verifier cases; double parse in violacoes.
Task US1: complete (commits fbea59b..68a7984, review clean) — squash-merged as PR #1
Wave 2 BASE=6dedccb: dispatching US2 (sonnet), US3 (sonnet), US4 (haiku)
Wave 2 dispatched (BASE 6dedccb): US2 impl a48819d1eb556c8c8 (sonnet), US3 impl a6b820efc81196a9f (sonnet), US4 impl a220c4898f43e6482 (haiku)
Task US2: implementer DONE (6dedccb..d322193, PR #2); reviewer dispatched
Task US4: implementer DONE (6dedccb..d49daa3, PR #3); reviewer dispatched
Task US3: implementer DONE (6dedccb..1fbf3cd, PR #4); reviewer dispatched. Note: gemeo_topico/gemeo_exercicio have FKs to catalog (foreign_keys=ON)
Task US2: review round 0: spec ✅, quality Needs fixes — 1 Important (OverflowError for extreme occurred_at escapes ValidationError), fix round 1 dispatched (resume a48819d1eb556c8c8)
Task US2: minor (deferred): epoch numbers accepted as occurred_at (fraction truncated); whitespace-only ids accepted; tempo_gasto_s has no upper bound (SQLite int64 overflow downstream); Evento mutable (no frozen); Estado* datetimes not forced to UTC/aware; test gaps (non-dict payload, payload None); one test bundles five assertions.
Task US4: minor (deferred): 10**x OverflowError at gap ~123k (unreachable); rating_do_exercicio accepts bool/float (2.5→850.0); no test for saturation / non-integer difficulty.
Task US4: complete (commits 6dedccb..d49daa3, review clean) — squash-merged as PR #3
Task US2: fix round 1/5 (1 addressed by implementer, awaiting scoped re-review; commits d322193..5749659)
Task US3: review round 0: spec ✅, quality Needs fixes — 2 Important (concurrent first abrir → "database is locked" at WAL pragma; abrir on junk file raises raw DatabaseError instead of BancoIndisponivel). Fix round 1 dispatched (resume a6b820efc81196a9f)
Task US3: minor (deferred): abrir_somente_leitura leaks conn if the SELECT 1 probe fails; ROLLBACK failure masks original error (guard with in_transaction); SCHEMA.split(";") brittle; INSERT OR IGNORE seed never updates existing rows / schema never migrates (undocumented); TEXT PKs without NOT NULL (topicos.id, exercicios.id, gemeo_aluno.student_id); topic order duplicated in two dicts in catalogo/dados.py (zip truncation); idempotency test only compares counts; no mode=ro special-chars test.
Task US2: fix round 1/5 (1 addressed, 0 open; commits d322193..5749659)
Task US2: complete (commits 6dedccb..5749659, review clean after 1 fix round) — squash-merged as PR #2
Wave 3 (early start, US7 waits for US3 merge): BASE=4f23bab; dispatching US5 (sonnet), US6 (sonnet)
Task US3: fix round 1/5 implemented (commits 1fbf3cd..d64966b), scoped re-review dispatched. Wave 3: US5 impl a4b984b46d3b57215, US6 impl ae8862ea75a565579 (worktrees us05, us06 from 4f23bab)
Task US5: implementer DONE (4f23bab..5634fde, PR #5); reviewer dispatched
Task US3: fix round 1/5 (2 addressed, 0 open; commits 1fbf3cd..d64966b)
Task US3: complete (commits 6dedccb..d64966b, review clean after 1 fix round) — squash-merged as PR #4
Task US3: minor (deferred, from re-review): concurrency test uses fork and leaves children if one dies; BEGIN IMMEDIATE relies on connect timeout (10s) not on its own retry.
US7: worktree .worktrees/us07 from main (db.py now available)
Task US7: dispatched implementer (sonnet), BASE 21c11e9, worktree us07
Task US5: minor (deferred): exp(-z) unguarded for out-of-domain taxa_abandono/desempenho_relativo (EstadoAluno does not constrain them); naive datetimes → TypeError (undocumented); "(0,1) exclusive" test never approaches saturation; report misstated z range (really [-4,7.5]).
Task US5: complete (commits 4f23bab..5634fde, review clean) — squash-merged as PR #5
Task US9: dispatching implementer (sonnet), worktree us09 (wave 4 early start)
Task US9: implementer a357ee32127c6a421 dispatched (BASE 5b37c51). Active: US6 ae8862ea75a565579, US7 a8c7ac3497a85d323, US9
Task US6: implementer DONE (4f23bab..234530e, PR #6; impl committed before tests, RED/GREEN claimed); reviewer dispatched
Task US7: implementer DONE (21c11e9..605cc41, PR #7); reviewer dispatched
Task US6: review round 0: spec ✅, quality Needs fixes — 1 Important (no consistency guards between event and incoming aluno/topico/exercicio; dificuldade validated only on respondido). Ruling R7: validate dificuldade for ALL event types + identity guards at top of aplicar_evento. Fix round 1 dispatched (resume ae8862ea75a565579)
Task US6: minor (deferred): late-event contract undocumented in docstring (averages/respostas still applied, topic atualizado_em goes backwards); respondido branch ~60 lines (split helpers); _fechar defined after use; non-abandonado/respondido falls through as iniciado; assert ALFA==0.2 restates constant; missing tests: first event abandonado, iniciado leaves other fields, second attempt tentativas.
Task US7: minor (deferred): _para_texto on naive datetime shifts by local TZ; row mappers need row_factory=Row (undocumented); upsert test doesn't check ultimo_evento_* change / velocidade back to None; no FK-failure-path test (aluno row written before topic FK error → relies on caller's transaction); duplicated table tuple; strftime silently truncates microseconds.
Task US7: complete (commits 21c11e9..605cc41, review clean) — squash-merged as PR #7
Task US8: dispatching implementer (sonnet), worktree us08
Task US8: implementer dispatched (BASE 4ca64b1). Active: US6 fix (ae8862ea75a565579), US9 impl (a357ee32127c6a421), US8 impl
Task US9: implementer DONE (5b37c51..19ab50c, PR #8; impl+tests in one commit, 31 tests); reviewer dispatched
Task US6: fix round 1/5 implemented (234530e..b119794); scoped re-review dispatched
Task US8: implementer DONE (4ca64b1..e3a129d, PR #9); reviewer dispatched
Task US6: fix round 1/5 (1 addressed, 0 open; commits 234530e..b119794)
Task US6: minor (deferred, from re-review): identity guards tested only with respondido events (type-agnostic code).
Task US6: complete (commits 4f23bab..b119794, review clean after 1 fix round) — squash-merged as PR #6
Task US9: minor (deferred): empty simulation for small dias undocumented (perfis lists students with zero events); iniciado-before test weak (any earlier iniciado satisfies); inline magic numbers in simulador.py; R3 only a docstring convention (US10 must keep valid events identical — US15 asserts exact equality); no non-UTC inicio / small-dias / cross-run reproducibility test; Simulacao shallow-frozen, helpers lack docstrings.
Task US9: complete (commits 5b37c51..19ab50c, review clean) — squash-merged as PR #8
Task US13: dispatching implementer (sonnet), worktree us13
Task US13: implementer dispatched (BASE e1d2031). Active: US8 reviewer (ada2b3ea22ee00715), US13 impl
Task US8: review round 0: spec ❌ (robustness), quality Needs fixes — 3 Important (RecursionError on deep nesting crashes receber; lone surrogates crash INSERT; no test for exception/rollback path). Ruling R8: hostile input must become `rejeitado`, never an exception — overrides plan's literal ensure_ascii=False where it conflicts (fallback chain; non-UTF8-encodable strings → rejeitado, columns NULL) — cost if wrong: raw JSON in DB less readable in rare cases. Fix round 1 dispatched (resume abee909f964f405f1)
Task US8: minor (deferred): rowcount==0 path effectively dead (pre-check + insert in same BEGIN IMMEDIATE; plan-mandated), OR IGNORE would mask other violations; motivos mixed English/Portuguese, truncation mid-sentence; duplicated time-format helper vs Evento.occurred_at_texto; naive agora() read as local time; ROLLBACK failure masks original exception.
Task US13: implementer DONE (e1d2031..41aa6bb, PR #10); reviewer dispatched
Task US8: fix round 1/5 implemented (e3a129d..fcf809f); scoped re-review dispatched
Task US13: minor (deferred): duplicate EstadoTopico rows for same topic resolved last-wins (order-dependent); probabilidade_evasao unvalidated/echoed (NaN→default target); test gaps (state for unknown topic, unknown resolvidos ids, tied weakest topics with first solved, 0.6001 threshold); `id` param shadows builtin in tests; "não tentado" means no EstadoTopico row.
Task US13: complete (commits e1d2031..41aa6bb, review clean) — squash-merged as PR #10
Task US14: dispatching implementer (sonnet), worktree us14
Ruling R9: plan defect — US14 tests were specified to fill the DB via receber + processar_pendentes (US8/US11, not merged when US14 runs, and out of api's dependencies). Ruled: US14 test fixture applies events with aplicar_evento + repositorio.salvar (tests may import anything); end-to-end through ingestion+pipeline+API is covered by US15 — cost if wrong: fixture slightly less end-to-end in US14.
Task US14: implementer dispatched (BASE e0caaa0). Active: US8 re-review (a1dc137b90c93b841), US14 impl
Task US8: fix round 1/5 (3 addressed, 0 open; commits e3a129d..fcf809f)
Task US8: minor (deferred, from re-review): non-encodable-text backstop in _validar unreachable/untested (pydantic rejects lone surrogates first); non-encodable event_id stored NULL → retry not deduped (harmless, rejeitado); clock test doesn't pin ROLLBACK (trigger test does); deep payload not preserved in bruto_json (placeholder).
Task US8: complete (commits 4ca64b1..fcf809f, review clean after 1 fix round) — squash-merged as PR #9
Wave 5: US10 + US11 dispatching (worktrees us10, us11 from main); US14 impl a826f1dfa00fd6a68 running
Wave 5 dispatched (BASE 23ad99d): US10 impl a6ac2518a2db26cbe, US11 impl a10a6e2ad71a6e586, US14 impl a826f1dfa00fd6a68 (BASE e0caaa0)
Task US14: implementer DONE (e0caaa0..f03d8ff, PR #11); reviewer dispatched
Task US10: implementer DONE (23ad99d..e9f4bce, PR #12); reviewer dispatched
Task US11: implementer DONE (23ad99d..979da0a, PR #13); reviewer dispatched
Task US14: minor (deferred): schema-less valid SQLite file → 500 (no such table) on /gemeo,/recomendacao while /saude says 200 (probe SELECT 1 FROM sqlite_master too weak; suggest probing gemeo_aluno + translating OperationalError → 503); blocking SQLite in async def with default 5s timeout; test gaps (503 on /recomendacao, %2F body, write-reject/snapshot assertions); GEMEO_DB="" → Path("") silent 503; py3.10 fromisoformat rejects fractional seconds in GEMEO_AGORA; duplicated aluno+evasao lines in both endpoints; abrir_somente_leitura leaks conn if probe raises (db.py, pre-existing).
Task US14: complete (commits e0caaa0..f03d8ff, review clean) — squash-merged as PR #11
Open item for final cleanup (not a ruling yet): main suite prints 1 third-party StarletteDeprecationWarning (starlette TestClient + httpx → "install httpx2"); tests are green. Decide at final review: add a narrow filterwarnings in pytest.ini or switch the dev dependency; "test output should be pristine".
Merged so far (main 758f0e2): US1 US2 US3 US4 US5 US6 US7 US8 US9 US13 US14. In review: US10 (a1f1949e89e6764d7), US11 (ab05a064c4731abda). Remaining: US12, US15, US16.
Task US10: minor (deferred): huge --dias without --inicio → OverflowError traceback; CLI messages/help without pt-BR accents and no docstrings on main/_argumentos/_instante_com_fuso; guarantee-swap branch (simulador.py:118-126) untested and looser than comment; _TIPOS_MALFORMADOS defined after _malformado; malformed-kinds test hard to read/duplicates receber's catalog check; no CLI test for non-positive --alunos/--dias.
Task US10: complete (commits 23ad99d..e9f4bce, review clean) — squash-merged as PR #12
Task US11: minor (deferred): poison-pill rows — one unreconstructable pending row (bad payload_json/NULL field) makes listar_pendentes raise for the whole queue (fila.py:182-200, consumidor.py:117); status-rollback not proven by a test (fails before marcar_processado; no failure-after-mark / COMMIT / KeyboardInterrupt case; exercicio write rollback unchecked); processar_evento may return "rejeitado" falsely if another writer processed the event between the two transactions (no rowcount check); naive agora() read as local TZ; dead `or ""` on ultimo_evento_id and opaque unpack of fila.buscar; EventoAtrasado head-of-line blocking (by design until US12).
Task US11: complete (commits 23ad99d..979da0a, review clean) — squash-merged as PR #13
Ruling R10: US12 carries the US11 deferred minors as FYI; for NEW code (`eventos_do_aluno` / reconstruir_aluno) an unreconstructable row must be marked rejeitado (domain error) instead of crashing the rebuild — cost if wrong: one fix round.
Ruling R11: plan defect — US15's exact-equality test with defeitos=True needs late-event reconstruction (US12), but the plan lists US15 as depending only on US9/US10/US11/US14 and parallel to US12. Ruled: US15 runs AFTER US12 is merged (wave 7), US16 becomes wave 8 — cost: one extra sequential step, no rework.
Task US12: dispatching implementer (sonnet), worktree us12
Task US12: implementer a-pending dispatched (BASE 8deba2d); nothing else running
Task US12: implementer DONE_WITH_CONCERNS (8deba2d..3486668); branch pushed but PR NOT opened — the implementer's gh pr create was denied by the permission classifier ("Out-of-Place Publication") and it asked the controller to run it. Not laundering it: surfaced to the user for an explicit yes. Review proceeds on the pushed branch (read-only). Implementer concerns: reprocessar_tudo reset is one transaction but reapplication is per event (API readers may see partial twin during reprocess); edited US11's test_consumidor late-event test (now uses processar_evento); US11 deferred minors left alone; rebuild rewrites processado_em of re-applied events.
User answered the PR question: "Sim, abra o PR" — controller opens PRs when an implementer's gh pr create is denied (same rules: no AI signature, merge only after clean review + green suite). US12 PR opened by the controller as #14.
Task US12: minor (deferred): rebuild vs normal path disagree on non-canonical occurred_at rows (_evento_reconstruivel checks, listar_pendentes/buscar don't) — only reachable by bypassing receber; reprocessar_tudo inherits listar_pendentes fragility (one unreconstructable processado row after reset → empty twin until fixed; worth a README/docstring line); R10 motivo detail is raw English pydantic/json text; test_reprocessar_tudo_reproduz... reverses arrival to no effect (all pending, re-sorted) — name overstates; CLI reprocess test checks only processados; dump_gemeo helper lives in test_reconstrucao.py (should be in a shared tests module); two tests cover the same EventoAtrasado contract; rebuild overwrites processado_em (original processing time lost).
Task US12: complete (commits 8deba2d..3486668, review clean — fuzz by reviewer found no order breaking exact equality) — squash-merged as PR #14
Task US15: dispatching implementer (sonnet), worktree us15
Task US15: implementer dispatched (BASE bccf9a2)
Task US15: implementer DONE_WITH_CONCERNS (bccf9a2..0cbcf01): its git push and gh pr create were denied by the permission classifier; the user had authorized the controller to open the PRs of the following USs ("Sim, abra o PR ... e os das próximas USs"), so the controller pushed the branch and opened PR #15. Reviewer dispatched. Implementer concern under review: convergence test deviates from literal per-topic threshold (per-topic Spearman 0.47/0.35/0.05/0.47 with 9-10 students/topic; test asserts every topic >0 and pooled Spearman >= 0.25, measured 0.325, control -0.058).
Task US15: review round 0: spec ❌ (per-topic threshold deviation), quality Needs fixes — 1 Important (convergence test too weak: tuned to seed 42, fails on seeds 45/48/50 with 12 students, passes with inverted expectativa / difficulty ignored / K=2..96). Ruling R12: convergence test on its own ~40-student fixture with a real per-topic threshold + pooled threshold, mutation evidence required (inverted expectativa, K=-32, difficulty ignored must FAIL; >=6 seeds must pass) — cost if wrong: one more fix round. Fix round 1 dispatched (resume aaa6082e953af450d); implementer commits locally, controller pushes.
Task US15: minor (deferred): defects test does not assert duplicados>0; evasion test ignores `irregular` and its 404 branch is dead; scripts/comparar_habilidades imports tests.utilitarios.spearman (script → tests dependency); script output text without accents ("topico"), asserted by a test; loop variable `l` (E741).
Task US15: fix round 1/5 implemented (0cbcf01..87a2be7), pushed by controller to PR #15; scoped re-review dispatched
Task US15: fix round 1/5 (1 addressed, 1 new open — script-reproducibility test reduced to 6 students × 14 days no longer reaches the Spearman-printing branch; commits 0cbcf01..87a2be7). Fix round 2 dispatched (resume aaa6082e953af450d).
Task US15: minor (deferred, from re-review): code comment on thresholds doesn't say seed 48 falls below 0.20 per topic nor that limits must be re-measured after any simulator/Elo change; per-topic limit is a regression pin on seed 42 (about 10 students/topic → high variance), not a statistical claim; per-topic negative control dropped (luck-dependent).
Task US15: fix round 2/5 implemented (87a2be7..8d47bd7), pushed; scoped re-review dispatched
Task US15: fix round 2/5 (1 addressed, 0 open; commits 87a2be7..8d47bd7)
Task US15: minor (deferred, from re-review 2): script test is not independent of the code under test (shares simular/receber/processar_pendentes/comparar/spearman) — checks composition/format/determinism only; 13.6 s total leaves ~1.4 s margin to the 15 s budget; scripts → tests.utilitarios dependency.
Task US15: complete (commits bccf9a2..8d47bd7, review clean after 2 fix rounds) — squash-merged as PR #15
Task US16: dispatching implementer (sonnet), worktree us16 (last US)
Task US16: implementer dispatched (BASE 7f4f46e)
Task US16: implementer DONE_WITH_CONCERNS (7f4f46e..a450b12); branch pushed by implementer, gh pr create denied → controller opened PR #16 (user-authorized); reviewer dispatched. Notes: port 8000 busy so API checked on 18765 (README says 8000); convergence numbers quoted from the test comment, not re-measured; re-running simular --defeitos gives duplicados 1927 / rejeitados 2 (events without event_id re-rejected as new rows).
Task US16: minor (deferred): README/CLAUDE.md say the clock appears "only at the borders (CLIs and create_app)" — also receber (recebido_em), consumidor._agora_texto (processado_em) and api._agora_utc default to the real clock when agora is None (injectable, metadata only; twin values never use it); "até o último bit" holds only in the same environment (libm); "só módulos puros" for recomendacao→gemeo is enforced only as "not gemeo.repositorio"; data-model section omits PKs/indexes/foreign_keys pragma; /recomendacao text omits that expectativa_acerto is null when all solved.
Task US16: complete (commits 7f4f46e..a450b12, review clean — reviewer re-ran the whole flow and matched every number) — squash-merged as PR #16
ALL 16 USs MERGED. Next: final whole-branch review (fable) on fbea59b..main, then ONE fix wave if needed, record of the SDD flow, finish.
Final whole-branch review dispatched (fable) on fbea59b..fc69656 (main), 16 commits, 52 files, +5662 lines
Final review (fable): Ready to merge: WITH FIXES, no Critical. Important: (1) processar_evento still raises EventoAtrasado (plan said US12 replaces it with rebuild); (2) arch test blind spot (`tests` not in MODULOS_DO_PROJETO) + scripts→tests.utilitarios backwards edge; (3) test output not pristine (httpx2); (4) /saude weak probe + 500 on schema-less DB; (5) SDD record not yet versioned (controller's closing step). Triage: fix before done = /saude, scripts→tests edge, httpx2 warning, README clock/bit-exact wording; acceptable = poison-pill, false "rejeitado" under concurrent writer, naive agora, evasao exp, other ledger minors. Reviewer fuzzed exactness (24 rounds incl. crashes and 2 concurrent writers) — all bit-identical.
Ruling R13: processar_evento rebuilds the student on a late event and returns "reconstruido" (instead of raising) — aligns the code with the plan's stated US12 intent; cost if wrong: one function contract + 2 tests to revert.
Ruling R14: fix wave includes (1)-(4), README/CLAUDE.md wording, and NOT NULL on gemeo_aluno.ultimo_evento_id; excludes helper consolidation, PRAGMA synchronous, poison-pill, exp clamp, accents, other nits (acceptable for a portfolio PoC per the reviewer's triage) — cost if wrong: those minors stay.
Fix wave dispatched (ONE fix subagent, sonnet), worktree .worktrees/fix, branch fix/final-review-wave.
Fix wave DONE (fc69656..42f9254, 5 commits, 288 tests, 0 warnings); implementer could not push → controller pushed the branch and opened the PR (user-authorized); scoped re-review dispatched. Implementer extras: scripts now scanned by the arch test (got a PERMITIDO entry); probe lives in db.abrir_somente_leitura; naive clock in API raises TypeError (documented); no migration for NOT NULL column (README limitation + test); spec's processar_evento line updated, plan file untouched.
Final fix wave: re-review verdict — all 4 Important findings + wording + NOT NULL ADDRESSED, no new breakage (reviewer fuzzed processar_evento event-by-event: identical to chronological reference). Out-of-scope obs: README/CLAUDE.md "SQL de infraestrutura" lists omit BEGIN/COMMIT/ROLLBACK in consumidor.py (trivial); a late event that is itself invalid returns "reconstruido" and is rejected inside the rebuild (same as processar_pendentes).
Final fix wave: complete (fc69656..42f9254) — squash-merged as PR #17. main suite: green, 0 warnings.
