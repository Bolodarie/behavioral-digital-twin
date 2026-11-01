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

### US2: Contratos Pydantic dos eventos e dos estados

**Branch:** `feat/us02-contratos` · **Depende de:** US1

**Files:** Create `modelos.py`, `tests/test_modelos.py`, `tests/fabricas.py`

**Interfaces:**
- Produces em `modelos.py`:
  - `TipoEvento(str, Enum)`: `EXERCICIO_INICIADO="exercicio_iniciado"`, `EXERCICIO_RESPONDIDO="exercicio_respondido"`, `EXERCICIO_ABANDONADO="exercicio_abandonado"`.
  - `Evento(BaseModel)` (`extra="forbid"`): `event_id: str`, `student_id: str`, `exercise_id: str`, `topic: str` (todos `min_length=1`), `event_type: TipoEvento`, `occurred_at: datetime`, `payload: dict[str, Any]`. Propriedades: `occurred_at_texto -> str` (`YYYY-MM-DDTHH:MM:SSZ`), `acertou -> bool | None`, `tempo_gasto_s -> int | None` (só preenchidos em `exercicio_respondido`). `occurred_at` sai sempre em UTC com microssegundo 0.
  - `PayloadRespondido(BaseModel)` (`extra="forbid"`): `acertou: StrictBool`, `tempo_gasto_s: StrictInt` (`gt=0`).
  - `EstadoAluno`: `student_id: str`, `velocidade_media_s: float | None`, `taxa_abandono: float`, `erros_seguidos: int`, `desempenho_relativo: float`, `respostas: int`, `ultimo_evento_em: datetime`, `ultimo_evento_id: str`, `atualizado_em: datetime`.
  - `EstadoTopico`: `student_id`, `topic_id`, `rating_elo: float`, `tentativas: int`, `acertos: int`, `atualizado_em: datetime`.
  - `EstadoExercicio`: `student_id`, `exercise_id`, `tentativas: int`, `acertou_alguma_vez: bool`.
  - `EstadoAtualizado`: `aluno: EstadoAluno`, `topico: EstadoTopico | None = None`, `exercicio: EstadoExercicio | None = None` (`None` = não mudou).
  - `ResultadoIngestao`: `status: Literal["aceito","duplicado","rejeitado"]`, `event_id: str | None`, `motivo: str | None`.
- Produces em `tests/fabricas.py`: `evento_dict(event_id="e1", student_id="aluno-1", exercise_id="funcoes-3", topic="funcoes", event_type="exercicio_respondido", occurred_at="2026-03-02T12:00:00Z", payload=None, **sobrescrever) -> dict` (payload padrão: `{"acertou": True, "tempo_gasto_s": 100}` para respondido, `{}` para os outros).

- [ ] **Step 1: Escrever `tests/test_modelos.py` (falhando).** `test_evento_respondido_valido` (campos e `acertou`/`tempo_gasto_s` acessíveis); `test_evento_iniciado_e_abandonado_com_payload_vazio`; `test_payload_nao_vazio_em_iniciado_rejeitado`; `test_occurred_at_sem_fuso_rejeitado`; `test_offset_convertido_para_utc` (`"2026-03-02T10:00:00-03:00"` → `occurred_at_texto == "2026-03-02T13:00:00Z"`); `test_fracao_de_segundo_truncada` (`"…12:00:00.987Z"` → `…12:00:00Z`); `test_tempo_gasto_invalido` (parametrizado: `0`, `-5`, `12.5`, `"30"`, `True` → `ValidationError`); `test_acertou_nao_booleano` (`"true"`, `1`, `None`); `test_payload_respondido_com_chave_faltando_ou_extra`; `test_campos_extras_no_evento_rejeitados`; `test_ids_vazios_rejeitados` (`event_id`, `student_id`, `exercise_id`, `topic`); `test_tipo_de_evento_desconhecido`; `test_estado_atualizado_defaults` (`topico` e `exercicio` `None`).
- [ ] **Step 2: Rodar e ver falhar; implementar `modelos.py` e `tests/fabricas.py`** (validação do payload por tipo em um `model_validator(mode="after")` ou equivalente; conversão para UTC e `microsecond=0` num validador do campo `occurred_at`).
- [ ] **Step 3: Suíte completa verde, commit(s), abrir PR (protocolo).**

**Aceite:** todos os casos acima verdes; nenhum import de outros módulos do projeto em `modelos.py`.

