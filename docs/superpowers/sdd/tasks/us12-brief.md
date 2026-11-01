## Restrições globais (valem para toda US)

- Python **3.10**: type hints modernos (`X | None`, `list[int]`), sem recursos 3.11+.
- Dependências de runtime só `pydantic>=2`, `fastapi>=0.110`, `uvicorn`; `httpx` e `pytest` só em `requirements-dev.txt`. `sqlite3` da stdlib. Nada de numpy, scipy, pandas, SQLAlchemy.
- Regra de dependência entre camadas (design §3), verificada por `tests/test_arquitetura.py`. Não enfraqueça esse teste para fazer código passar; corrija o import.
- Contratos entre camadas em Pydantic (`modelos.py`), nunca dicionários soltos. Exceção deliberada: o simulador emite `dict` (imita um produtor externo) e a ingestão os converte.
- Timestamps: UTC, texto `YYYY-MM-DDTHH:MM:SSZ` no banco; `datetime` com fuso nos modelos. Resolução de 1 s.
- Lógica de domínio pura: nada de `datetime.now()` fora das bordas (CLIs, `create_app`, `receber`/`processar_*` via parâmetro `agora` injetável).
- Todo valor do gêmeo vem dos eventos: `atualizado_em`/`ultimo_evento_em` usam o horário do evento, nunca o relógio real; nada é arredondado ao gravar.
- Idioma: docstrings curtas, mensagens, seed e README em **português do Brasil**; identificadores como no design (`event_id`, `acertou`, `tempo_gasto_s`, `rating_elo`...).
- Documentação sem jargão comercial.
- **Sem atribuição a Claude/IA em lugar nenhum:** nada de `Co-Authored-By`, nem "Generated with Claude Code" em commit, PR ou arquivo. Commits em Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`), em inglês curto, como na PoC 1.
- Testes enxutos e focados no comportamento; relógio injetado e semente fixa; nunca depender da data de hoje.

## Foco da revisão (entradas que o design implica e nenhuma US testaria por si)

1. **Empate de `occurred_at`** para o mesmo aluno: ordem por `event_id` e gatilho de reconstrução pela chave completa. Testes em US6 (avanço do `ultimo_evento_*`) e US12 (empate).
2. **`occurred_at` com deslocamento diferente de UTC, sem fuso, com frações de segundo:** convertido, rejeitado e truncado, respectivamente. Testes em US2 e US8.
3. **Tipos estritos e lixo estrutural:** `acertou` não booleano, `tempo_gasto_s` zero/negativo/float/string/bool, chaves extras, `student_id` vazio, dado que nem é objeto. Testes em US2 e US8.
4. **Estados incomuns de aluno:** só `exercicio_iniciado`, aluno desconhecido, aluno que resolveu tudo. Testes em US13 e US14.
5. **Primeira execução:** pipeline sem nada pendente e API sem banco criado. Testes em US12 e US14.

## Modelo de execução

**Features → USs.** Cada US = uma branch `feat/usNN-<slug>` a partir da `main` atualizada = um worktree em `.worktrees/usNN` = um subagente implementador = um PR para `main`.

| Feature | USs |
|---|---|
| F1 Fundação | US1 esqueleto e teste de arquitetura · US2 contratos Pydantic · US3 catálogo e banco |
| F2 Gêmeo digital | US4 Elo · US5 evasão · US6 atualização por evento · US7 repositório |
| F3 Ingestão e simulação | US8 receber evento · US9 simulador · US10 defeitos e CLI de simulação |
| F4 Pipeline | US11 consumo e atomicidade · US12 evento atrasado, reprocessamento e CLI |
| F5 Recomendação e API | US13 recomendação · US14 API |
| F6 Fechamento | US15 convergência e ponta a ponta · US16 README e CLAUDE.md finais |

**Dependências e ondas** (até 3 USs em paralelo; cada onda parte da `main` já com a onda anterior integrada; USs da mesma onda mexem em arquivos diferentes):

| Onda | USs | Dependem de |
|---|---|---|
| 1 | US1 | — |
| 2 | US2, US3, US4 | US1 |
| 3 | US5, US6, US7 | US2 (US6 também US4; US7 também US3) |
| 4 | US8, US9, US13 | US2, US3 (US13 também US4) |
| 5 | US10, US11, US14 | US10: US8, US9 · US11: US6, US7, US8 · US14: US5, US7, US13 |
| 6 | US12, US15 | US12: US11 · US15: US9, US10, US11, US14 |
| 7 | US16 | todas |

**Protocolo por US** (o controlador faz o setup; o implementador faz o resto):
- Venv único em `<repo>/.venv` (`uv venv --system-site-packages --python 3.10`; `uv pip install -r requirements-dev.txt` depois da US1). Os worktrees usam esse mesmo interpretador: `PY=/home/igorg/facul/aprendizado/behavioral-digital-twin/.venv/bin/python`. Testes: `$PY -m pytest ...` dentro do worktree (o `pytest.ini` põe a raiz no `pythonpath`).
- Setup: `git -C <repo> pull --ff-only` e `git worktree add .worktrees/usNN -b feat/usNN-<slug> main`.
- TDD: teste falhando → implementação mínima → verde → suíte completa verde (`$PY -m pytest -q`) → commits pequenos.
- Fim: `git push -u origin feat/usNN-<slug>` e `gh pr create --base main --title "feat(F<n>/US<N>): <título>" --body ...`. O corpo do PR tem: Feature e US; o que muda; como testar; critérios de aceite da US. Sem assinatura de IA.
- O implementador **não** faz merge. Revisão de tarefa (spec + qualidade) e ciclo de correção seguem o SDD; correções entram como commits novos na mesma branch/PR.
- **Merge:** só depois de revisão limpa e suíte verde, e **apenas se o Igor autorizar** (pergunta no fim do plano). Recomendado: squash por US, apagando a branch, para a `main` ficar com um commit por US e a onda seguinte partir dela.
- Bloqueio: se um implementador reportar BLOCKED/NEEDS_CONTEXT, siga o SDD (mais contexto, modelo mais forte ou quebrar a US).

**Modelos sugeridos:** implementadores `sonnet`, exceto US4 (fórmulas completas) em `haiku`; revisores `sonnet`; revisão final da branch inteira no modelo mais capaz. Sempre informar o modelo ao despachar.

## Decisões do planejamento (valem como regras; estão fora do design ou o refinam)

- O simulador **não** importa `gemeo.elo` (regra de dependência) e reimplementa a fórmula de propósito: o processo gerador deve ser independente do estimador. Um teste (US9) garante que as duas escalas não divergem.
- `EstadoAtualizado` e `ResultadoIngestao` ficam em `modelos.py` (US2) para desacoplar US6/US7/US8.
- `recomendacao.escolher` recebe o catálogo por parâmetro opcional (padrão: catálogo real) para a API não precisar importar `catalogo` e os testes usarem catálogos pequenos.
- Conexões SQLite abertas com `isolation_level=None` (autocommit); transações são explícitas (`BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`). `salvar` do repositório nunca faz commit.
- Ids do catálogo: `f"{topico}-{n}"`, `n = 1..4`, com dificuldades fixas `1, 2, 3, 5` (rating Elo 800, 900, 1000, 1200); tópicos `funcoes`, `equacao_1_grau`, `equacao_2_grau`, `sistemas_lineares`. Os testes dependem disso.
- US11 deixa o evento atrasado levantando `EventoAtrasado` (evento fica pendente); US12 troca isso por reconstrução. Estado intermediário assumido e documentado.
- Pesos iniciais da evasão (ajustáveis, mantendo as propriedades do design §7): `B0=-2.0`, `W_ABANDONO=3.0`, `W_ERROS=1.5`, `W_DESEMPENHO=-2.0`, `W_INATIVIDADE=3.0`.
- Fórmula das médias móveis, sempre nesta forma (para a igualdade exata): `x_novo = x + ALFA * (alvo - x)` com `ALFA = 0.2`.

---


# TEXTO DA SUA US (é o seu requisito; valores exatos aqui valem ao pé da letra)

### US12: Evento atrasado, reprocessamento e CLI

**Branch:** `feat/us12-reconstrucao-cli` · **Depende de:** US11

**Files:** Modify `pipeline/fila.py`, `pipeline/consumidor.py`; Create `pipeline/executar.py`, `tests/test_reconstrucao.py`, `tests/test_cli_executar.py`

**Interfaces:** em `fila.py`: `eventos_do_aluno(conn, student_id) -> list[Evento]` (status ≠ `rejeitado`, ordem `(occurred_at, event_id)`), `devolver_todos_a_pendente(conn) -> None` (só os não rejeitados). Em `consumidor.py`: `reconstruir_aluno(conn, student_id, *, agora=None) -> int` (transação única: `apagar_aluno`, reaplica todos os eventos do aluno em ordem, marca todos `processado`; `EventoInvalido` durante a reconstrução rejeita o evento de forma permanente e segue; devolve quantos foram aplicados); `reprocessar_tudo(conn, *, agora=None) -> ResumoProcessamento` (`apagar_tudo`, `devolver_todos_a_pendente`, `processar_pendentes`); `processar_pendentes` passa a tratar `EventoAtrasado` chamando `reconstruir_aluno` (conta em `alunos_reconstruidos`, no máximo uma vez por aluno por chamada; pendentes daquele aluno já processados pela reconstrução são pulados). `pipeline/executar.py`: `main(argv=None) -> int`, opções `--db`, `--reprocessar`; imprime `processados: N`, `rejeitados: N`, `alunos_reconstruidos: N`; `python -m pipeline.executar` funciona.

- [ ] **Step 1: Testes (falhando).** Auxiliar em `tests/`: `dump_gemeo(conn) -> list[tuple]` (todas as linhas das três tabelas do gêmeo, ordenadas). `test_ordem_de_chegada_nao_importa` (`simular(semente=7, n_alunos=4, inicio=2026-01-05T00:00:00Z, dias=14)`: banco A com eventos em ordem cronológica e um `processar_pendentes`; banco B com os mesmos eventos embaralhados (`random.Random(0)`), ingeridos em 3 lotes com `processar_pendentes` entre eles; `dump_gemeo(A) == dump_gemeo(B)` com igualdade exata, e `alunos_reconstruidos > 0` em B); `test_empate_de_horario_desempata_por_event_id` (dois eventos do mesmo aluno com o mesmo `occurred_at`, ids `"a"` e `"b"`; processar `"b"` e depois `"a"` chegando → reconstrução → igual a processar `a` depois `b`); `test_reprocessar_tudo_reproduz_o_estado_incremental` (exato); `test_reconstruir_aluno_e_idempotente`; `test_rejeitado_continua_rejeitado_no_reprocessamento` (e não é aplicado); `test_reconstruir_so_afeta_o_aluno_alvo`; `test_reprocessar_banco_vazio`; CLI: `test_cli_processa_e_imprime`, `test_cli_reprocessar_chega_ao_mesmo_estado`, `test_cli_banco_novo_sem_pendentes_imprime_zeros`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

---

