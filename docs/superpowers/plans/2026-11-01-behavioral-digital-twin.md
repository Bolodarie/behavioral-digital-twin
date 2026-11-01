# behavioral-digital-twin — Plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: usar superpowers:subagent-driven-development para executar este plano. Cada **US** (história de usuário) é feita por um subagente em um worktree próprio, numa branch própria, e termina em **um Pull Request**. Os passos usam checkbox (`- [ ]`).

**Objetivo:** construir a PoC de pipeline de dados com gêmeo digital comportamental descrita no design: simulador de eventos → ingestão → `eventos_brutos` → pipeline → gêmeo (Elo, velocidade, evasão) → API de recomendação.

**Arquitetura:** camadas com dependência em uma direção, verificada por teste (`ast`). Lógica de domínio pura (`gemeo/elo.py`, `evasao.py`, `atualizacao.py`, `recomendacao/escolher.py`); só `gemeo/repositorio.py`, `ingestao/receber.py` e `pipeline/fila.py` falam com o banco. SQLite como fonte da verdade dos eventos brutos; o gêmeo sempre pode ser reconstruído a partir deles.

**Stack:** Python 3.10, SQLite (stdlib), Pydantic v2, FastAPI + uvicorn, pytest, httpx (só testes).

**Spec:** `docs/superpowers/specs/2026-10-31-behavioral-digital-twin-design.md` (manda em caso de dúvida; se for preciso divergir, atualize o documento junto).

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

# F1 — Fundação

### US1: Esqueleto do projeto e teste de arquitetura

**Branch:** `feat/us01-esqueleto` · **Depende de:** nada

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `README.md` (rascunho de 1 parágrafo; versão final na US16), `CLAUDE.md` (regra de dependência, decisões que não se mudam sem conversar, comandos), `data/.gitkeep`
- Create: `catalogo/__init__.py`, `ingestao/__init__.py`, `pipeline/__init__.py`, `gemeo/__init__.py`, `recomendacao/__init__.py`, `api/__init__.py`, `scripts/__init__.py`, `tests/__init__.py`
- Create: `tests/test_arquitetura.py`

**Interfaces:**
- Produces: a matriz de dependências como constante `PERMITIDO: dict[str, set[str]]` em `tests/test_arquitetura.py` (design §3) e a função `modulos_do_projeto_importados(codigo: str, pacote_do_arquivo: str) -> set[str]` (devolve os módulos de primeiro nível do projeto que o código importa).

- [ ] **Step 1: Arquivos de configuração.** `requirements.txt`: `pydantic>=2`, `fastapi>=0.110`, `uvicorn`. `requirements-dev.txt`: `-r requirements.txt`, `pytest`, `httpx`. `pytest.ini`: `testpaths = tests`, `pythonpath = .`. `.gitignore`: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.superpowers/`, `.venv/`, `.worktrees/`, `data/*.db`, `data/*.db-wal`, `data/*.db-shm`.
- [ ] **Step 2: Escrever `tests/test_arquitetura.py` (falhando onde faltar o que testar).** Testes do próprio verificador, sobre trechos de código em string: `test_detecta_import_simples` (`import pipeline.executar` → `{"pipeline"}`), `test_detecta_from_import` (`from gemeo.elo import expectativa` → `{"gemeo"}`), `test_detecta_importlib_e_dunder_import` (`importlib.import_module("api")` e `__import__("pipeline")` com literal), `test_import_relativo_e_resolvido` (em `ingestao/receber.py`, `from .. import pipeline` → `{"pipeline"}`; `from . import simulador` → `{"ingestao"}`), `test_ignora_stdlib_e_terceiros` (`import sqlite3, pydantic` → vazio). Depois o teste real: para cada `.py` em `modelos.py`, `db.py`, `catalogo/`, `ingestao/`, `pipeline/`, `gemeo/`, `recomendacao/`, `api/`, assert que os módulos do projeto importados ⊆ `PERMITIDO[dono] | {dono}`. Regra extra: `recomendacao` não pode importar `gemeo.repositorio`. `tests/` e `scripts/` ficam de fora (scripts de composição). Arquivos/módulos ainda inexistentes são simplesmente ignorados.
- [ ] **Step 3: Rodar** `$PY -m pytest tests/test_arquitetura.py -v` e ver falhar (módulo do verificador ausente) antes de implementar; implementar o verificador com `ast` (inclui `Import`, `ImportFrom` com `level>0`, chamadas `importlib.import_module`/`__import__` com literal); ver passar.
- [ ] **Step 4: `CLAUDE.md` e `README.md`** curtos (pt-BR), com os comandos `pip install -r requirements-dev.txt`, `pytest`.
- [ ] **Step 5: Suíte completa verde, commit(s), abrir PR (protocolo).**

**Aceite:** `pytest` verde; o teste de arquitetura falha se um import proibido for adicionado (provado pelos testes do verificador).

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

### US3: Catálogo e banco

**Branch:** `feat/us03-catalogo-banco` · **Depende de:** US1

**Files:** Create `catalogo/dados.py`, `catalogo/__init__.py` (reexporta), `db.py`, `tests/test_catalogo.py`, `tests/test_db.py`

**Interfaces:**
- Produces em `catalogo`: dataclasses congeladas `Topico(id: str, nome: str)` e `ExercicioCatalogo(id: str, topico_id: str, enunciado: str, dificuldade: int)`; `TOPICOS: tuple[Topico, ...]`, `TOPICO_IDS: tuple[str, ...]` (ordem do catálogo), `EXERCICIOS: tuple[ExercicioCatalogo, ...]`; `exercicio_por_id(exercise_id: str) -> ExercicioCatalogo | None`; `exercicios_do_topico(topico_id: str) -> tuple[ExercicioCatalogo, ...]`.
- Produces em `db.py`: `DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "gemeo.db"`; `abrir(caminho: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection` (cria a pasta, `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `isolation_level=None`, `row_factory=sqlite3.Row`, cria o schema e popula o catálogo de forma idempotente dentro de `BEGIN IMMEDIATE`); `abrir_somente_leitura(caminho) -> sqlite3.Connection` (`file:...?mode=ro` com `Path.resolve().as_uri()`, `row_factory=sqlite3.Row`); `class BancoIndisponivel(Exception)` levantada quando o arquivo não existe/não abre.
- Schema: as seis tabelas do design §5 (`topicos`, `exercicios`, `eventos_brutos`, `gemeo_topico`, `gemeo_exercicio`, `gemeo_aluno` com `ultimo_evento_id`), `CHECK (status IN ('pendente','processado','rejeitado'))`, `CHECK (dificuldade BETWEEN 1 AND 5)`, `event_id UNIQUE` (aceita vários `NULL`), índices em `eventos_brutos(status, occurred_at, event_id)` e `(student_id, occurred_at, event_id)`.

- [ ] **Step 1: Escrever os testes (falhando).** Catálogo: `test_quatro_topicos_na_ordem` (ids acima), `test_cada_topico_tem_quatro_exercicios_com_dificuldades_1_2_3_5` (ids `f"{topico}-{n}"`), `test_ids_unicos_e_dificuldade_entre_1_e_5`, `test_exercicio_por_id` (existente e inexistente → `None`), `test_enunciados_em_portugues_nao_vazios`. Banco: `test_abrir_cria_as_seis_tabelas`, `test_abrir_e_idempotente` (duas aberturas; contagem de tópicos/exercícios igual), `test_modo_wal` (`PRAGMA journal_mode` → `wal`), `test_somente_leitura_recusa_escrita` (`INSERT` → `sqlite3.OperationalError`), `test_somente_leitura_arquivo_inexistente` (`BancoIndisponivel`), `test_status_invalido_recusado` (CHECK), `test_event_id_unico_e_varios_nulos` (segundo mesmo id → `IntegrityError`; duas linhas com `event_id NULL` ok), `test_default_db_path_ancorado_na_pasta_do_projeto`.
- [ ] **Step 2: Rodar e ver falhar; implementar** catálogo (enunciados de álgebra em pt-BR, ex.: "Resolva 2x + 3 = 11.") e `db.py`.
- [ ] **Step 3: Suíte completa verde, commit(s), abrir PR (protocolo).**

**Aceite:** testes verdes; `catalogo` não importa nada do projeto; `db` só importa `catalogo`.

---

# F2 — Gêmeo digital

### US4: Elo

**Branch:** `feat/us04-elo` · **Depende de:** US1 · **Modelo:** haiku

**Files:** Create `gemeo/elo.py`, `tests/test_elo.py`

**Interfaces:** `RATING_INICIAL = 1000.0`, `K = 32.0`, `ESCALA = 400.0`; `rating_do_exercicio(dificuldade: int) -> float` (`800 + 100·(d−1)`; `ValueError` fora de 1..5); `expectativa(rating_aluno: float, rating_exercicio: float) -> float` (`1 / (1 + 10 ** ((rating_exercicio − rating_aluno) / ESCALA))`); `novo_rating(rating_aluno: float, rating_exercicio: float, acertou: bool) -> float` (`rating_aluno + K · (resultado − expectativa)`).

- [ ] **Step 1: Testes (falhando).** `test_rating_do_exercicio` (1→800.0, 3→1000.0, 5→1200.0; 0 e 6 → `ValueError`); `test_expectativa_valores` (`expectativa(1000,1000)==0.5`; `expectativa(1000,1200)≈0.24025`; `expectativa(1200,1000)≈0.75975`, `abs=1e-4`); `test_expectativa_simetrica` (soma 1); `test_novo_rating_acerto_e_erro_iguais` (`1016.0` e `984.0`); `test_acerto_dificil_sobe_mais_que_facil` (`novo_rating(1000,1200,True)≈1024.312`, maior ganho que contra 800); `test_erro_facil_desce_mais_que_dificil`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

### US5: Probabilidade de evasão

**Branch:** `feat/us05-evasao` · **Depende de:** US2

**Files:** Create `gemeo/evasao.py`, `tests/test_evasao.py`

**Interfaces:** constantes nomeadas (valores iniciais nas decisões do planejamento); `probabilidade_evasao(estado: EstadoAluno, agora: datetime) -> float`: sigmoide de `B0 + W_ABANDONO·taxa_abandono + W_ERROS·(min(erros_seguidos,5)/5) + W_DESEMPENHO·desempenho_relativo + W_INATIVIDADE·(min(dias,14)/14)`, com `dias = max(0, (agora − ultimo_evento_em)/1 dia)`.

- [ ] **Step 1: Testes (falhando)** com uma fábrica local `estado(**campos) -> EstadoAluno` (padrão: `taxa_abandono=0, erros_seguidos=0, desempenho_relativo=0, ultimo_evento_em` = `agora`). `test_resultado_entre_0_e_1_exclusivo` (extremos de todos os sinais); `test_cresce_com_inatividade` (0, 3, 7, 14, 30 dias → estritamente crescente até 14, constante depois do teto); `test_cresce_com_abandono`; `test_cresce_com_erros_seguidos` (e satura em 5); `test_cai_com_melhor_desempenho`; `test_aluno_ativo_abaixo_de_0_3` (taxa 0, erros 0, desempenho +0.1, inatividade 0,5 dia); `test_aluno_sumido_acima_de_0_7` (taxa 0.6, erros 4, desempenho −0.3, 14 dias); `test_agora_anterior_ao_ultimo_evento_conta_zero_dias`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

### US6: Atualização do gêmeo por evento (função pura)

**Branch:** `feat/us06-atualizacao` · **Depende de:** US2, US4

**Files:** Create `gemeo/atualizacao.py`, `tests/test_atualizacao.py`

**Interfaces:** `ALFA = 0.2`; `aplicar_evento(evento: Evento, dificuldade: int, aluno: EstadoAluno | None, topico: EstadoTopico | None, exercicio: EstadoExercicio | None) -> EstadoAtualizado`. Pura: não altera os argumentos. Regras (design §7): qualquer evento cria o aluno se `None` (`taxa_abandono=0.0`, `erros_seguidos=0`, `desempenho_relativo=0.0`, `respostas=0`, `velocidade_media_s=None`) e avança `(ultimo_evento_em, ultimo_evento_id)` só se a chave do evento for maior (`atualizado_em = ultimo_evento_em`); `exercicio_iniciado` não mexe em mais nada (`topico` e `exercicio` `None`); `exercicio_abandonado` só `taxa_abandono` (alvo 1); `exercicio_respondido`: Elo do tópico (cria com `RATING_INICIAL` se `None`; `tentativas`, `acertos`), `exercicio` (`tentativas`, `acertou_alguma_vez`), `respostas+1`, velocidade (primeiro valor = o tempo; depois média móvel), `taxa_abandono` (alvo 0), `erros_seguidos` (zera ao acertar, +1 ao errar), `desempenho_relativo` (média móvel de `resultado − E`, com `E` calculada **antes** de atualizar o rating).

- [ ] **Step 1: Testes (falhando)**, usando `tests/fabricas.py` + `Evento.model_validate`. `test_primeiro_iniciado_cria_aluno_sem_topico` (defaults, `topico is None`, `exercicio is None`, `ultimo_evento_id == "e1"`); `test_primeira_resposta_certa` (dificuldade 3: `rating_elo == 1016.0`, `tentativas==1`, `acertos==1`, `velocidade_media_s == 100.0`, `desempenho_relativo ≈ 0.1`, `respostas==1`, `erros_seguidos==0`, `exercicio.acertou_alguma_vez`); `test_segunda_resposta_errada` (encadeando: tempo 50, errou, mesma dificuldade → `rating_elo ≈ 999.263` (`abs=1e-3`), `velocidade_media_s == 90.0`, `erros_seguidos == 1`, `desempenho_relativo ≈ −0.0246` (`abs=1e-3`), `acertos == 1`, `acertou_alguma_vez` continua `True`); `test_abandono_so_mexe_na_taxa` (após a primeira resposta certa: `taxa_abandono == 0.2`, `respostas`, `erros_seguidos`, `velocidade_media_s` iguais, `topico is None`); `test_resposta_depois_de_abandono_puxa_taxa_para_zero` (0.2 → 0.16); `test_entradas_nao_sao_alteradas`; `test_ultimo_evento_so_avanca` (evento mais antigo não recua `ultimo_evento_em`/`ultimo_evento_id`; empate de horário com `event_id` maior avança, com menor não); `test_atualizado_em_vem_do_evento` (nenhum relógio real).
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

### US7: Repositório do gêmeo

**Branch:** `feat/us07-repositorio` · **Depende de:** US2, US3

**Files:** Create `gemeo/repositorio.py`, `tests/test_repositorio.py`

**Interfaces** (todas recebem `conn: sqlite3.Connection`; escrita nunca faz commit): `ler_aluno(conn, student_id) -> EstadoAluno | None`; `ler_topicos(conn, student_id) -> list[EstadoTopico]` (ordenados por `topic_id`); `ler_topico(conn, student_id, topic_id) -> EstadoTopico | None`; `ler_exercicio(conn, student_id, exercise_id) -> EstadoExercicio | None`; `ler_exercicios_resolvidos(conn, student_id) -> set[str]`; `salvar(conn, atualizado: EstadoAtualizado) -> None` (upsert das linhas não nulas); `apagar_aluno(conn, student_id) -> None` (as três tabelas do gêmeo); `apagar_tudo(conn) -> None`. Conversão `datetime` ↔ `YYYY-MM-DDTHH:MM:SSZ`; `float` gravado sem arredondar.

- [ ] **Step 1: Testes (falhando)**, com `db.abrir(tmp_path / "t.db")`. `test_ida_e_volta_exata` (rating `999.2634567891234` volta idêntico, igualdade exata; datetimes iguais e com fuso UTC); `test_salvar_e_upsert` (segundo `salvar` atualiza em vez de duplicar); `test_salvar_com_topico_e_exercicio_none_nao_mexe_neles`; `test_ler_desconhecidos_devolvem_none_ou_vazio`; `test_resolvidos_so_acertou_alguma_vez`; `test_apagar_aluno_so_apaga_aquele_aluno`; `test_apagar_tudo`; `test_salvar_nao_faz_commit` (dentro de `BEGIN`, `salvar`, `ROLLBACK` → nada gravado).
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

---

# F3 — Ingestão e simulação

### US8: Receber evento

**Branch:** `feat/us08-receber` · **Depende de:** US2, US3

**Files:** Create `ingestao/receber.py`, `tests/test_receber.py`

**Interfaces:** `receber(conn: sqlite3.Connection, dado: Any, *, agora: Callable[[], datetime] | None = None) -> ResultadoIngestao`. Ordem: (1) se `dado` é objeto com `event_id` string não vazia já presente em `eventos_brutos` (qualquer status) → `duplicado`, sem escrever; (2) valida com `Evento` + catálogo (`exercise_id` existe; `topic` bate com o do catálogo); falha → grava linha `rejeitado` (`bruto_json` sempre preenchido com `json.dumps(dado, ensure_ascii=False, sort_keys=True, default=str)`, `motivo_rejeicao` legível com até 500 caracteres, `event_id` quando houver) e devolve `rejeitado`; (3) senão grava `pendente` (colunas extraídas, `payload_json`, `recebido_em` = `agora()` ou UTC agora) e devolve `aceito`. Cada chamada é uma transação própria; gravação com `INSERT OR IGNORE` + checagem de `rowcount` (corrida entre duas chamadas vira `duplicado`). `dado` que não é `dict` → `rejeitado` com motivo "dado nao e um objeto".

- [ ] **Step 1: Testes (falhando)** com `evento_dict`. `test_aceito_grava_pendente` (status, `occurred_at` em texto `…Z`, `payload_json` decodifica igual, `recebido_em` vem do relógio injetado); `test_duplicado_nao_grava_de_novo`; `test_reenvio_de_rejeitado_com_mesmo_event_id_e_duplicado`; rejeições parametrizadas, cada uma gravando uma linha `rejeitado` com `bruto_json`: `occurred_at` sem fuso, `tempo_gasto_s=0`, `acertou="true"`, chave extra no payload, `payload` não vazio em iniciado, `student_id=""`, `exercise_id` inexistente (motivo menciona exercício), `topic` divergente do catálogo (motivo menciona tópico); `test_sem_event_id_grava_rejeitado_com_event_id_nulo` (duas vezes → duas linhas); `test_dado_que_nao_e_objeto` (`None`, lista, string); `test_offset_nao_utc_e_normalizado_na_gravacao`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

### US9: Simulador (função pura)

**Branch:** `feat/us09-simulador` · **Depende de:** US3

**Files:** Create `ingestao/simulador.py`, `tests/test_simulador.py`

**Interfaces:** `PERFIS = ("dedicado", "irregular", "desistente")`; `Simulacao` (dataclass congelada): `eventos: list[dict]`, `habilidades_iniciais: dict[str, dict[str, float]]`, `habilidades_finais: dict[str, dict[str, float]]` (aluno → tópico → habilidade na escala do Elo), `perfis: dict[str, str]` (aluno → perfil); `simular(semente: int, n_alunos: int, inicio: datetime, dias: int) -> Simulacao`; funções públicas `rating_do_exercicio(dificuldade: int) -> float` e `probabilidade_base(habilidade: float, rating_exercicio: float) -> float` (reimplementadas aqui, sem importar `gemeo`). Alunos `aluno-001…`, perfil em rodízio (`dedicado`, `irregular`, `desistente`, …). Eventos: dicts com as chaves do design §4, `occurred_at` em texto `…Z`, `event_id` UUID determinístico a partir da semente, ordenados por `(occurred_at, event_id)`. Cada exercício tentado gera `exercicio_iniciado` seguido de `exercicio_respondido` ou `exercicio_abandonado`. Acerto: `probabilidade_base` mais ruído pequeno, limitado a [0.02, 0.98]; tempo gasto depende de perfil e dificuldade; abandono depende do perfil; a habilidade verdadeira cresce devagar com a prática (nunca cai). Perfis: `dedicado` com eventos na maioria dos dias; `irregular` com lacunas longas; `desistente` para antes da metade do período. `ValueError` para `inicio` sem fuso, `n_alunos < 1` ou `dias < 1`. Valores numéricos (frequência, taxas, ganho, tempos) são do construtor.

- [ ] **Step 1: Testes (falhando)** com `semente=42, n_alunos=9, inicio=2026-01-05T00:00:00Z, dias=42`. `test_reprodutivel` e `test_semente_diferente_muda`; `test_eventos_validos_e_consistentes_com_o_catalogo` (todo dict passa em `Evento.model_validate`, `exercise_id` existe e `topic` bate); `test_ordem_cronologica_e_dentro_da_janela`; `test_toda_resposta_ou_abandono_tem_inicio_antes` (mesmo aluno e exercício, horário anterior); `test_perfis_em_rodizio`; `test_desistente_para_antes_da_metade` (último evento ≤ `inicio + dias/2`); `test_dedicado_ativo_na_maioria_dos_dias` (≥ 60% dos dias com evento) e `test_irregular_tem_lacuna_de_4_dias_e_menos_dias_ativos_que_dedicado`; `test_abandono_depende_do_perfil` (fração abandonados/iniciados do desistente > do dedicado); `test_habilidade_nunca_cai_e_cresce_para_dedicado`; `test_escala_igual_a_do_elo` (guarda contra divergência: para dificuldades 1..5, `rating_do_exercicio` do simulador `==` `gemeo.elo.rating_do_exercicio`; para alguns pares, `probabilidade_base` ≈ `elo.expectativa`, `abs=1e-12`); `test_entradas_invalidas`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

### US10: Defeitos e CLI de simulação

**Branch:** `feat/us10-defeitos-cli` · **Depende de:** US8, US9

**Files:** Modify `ingestao/simulador.py`; Create `ingestao/simular.py`, `tests/test_simulador_defeitos.py`, `tests/test_cli_simular.py`

**Interfaces:** `simular(..., defeitos: bool = False)`: com `True`, a lista de eventos passa a conter (a) duplicados (mesmo dict reenviado), (b) ordem embaralhada dentro de janelas, (c) pelo menos 3 eventos malformados de tipos diferentes (sem fuso, `tempo_gasto_s=0`, exercício inexistente, sem `event_id`); nunca altera os eventos válidos. `ingestao/simular.py`: `main(argv: list[str] | None = None) -> int`, opções `--semente` (42), `--alunos` (12), `--dias` (42), `--inicio` (ISO com fuso; padrão `agora − dias`), `--defeitos`, `--db` (`DEFAULT_DB_PATH`); chama `db.abrir` e `receber` por evento e imprime `aceitos: N`, `duplicados: N`, `rejeitados: N` (uma por linha); `python -m ingestao.simular` funciona; `--inicio` sem fuso → erro de uso (código 2).

- [ ] **Step 1: Testes (falhando).** `test_defeitos_preservam_os_eventos_validos` (conjunto de eventos válidos únicos por `event_id` igual com e sem `defeitos`); `test_defeitos_gera_duplicados`, `test_defeitos_gera_ordem_nao_cronologica`, `test_defeitos_gera_ao_menos_3_malformados_de_tipos_diferentes` (falham em `Evento.model_validate`); `test_sem_defeitos_e_cronologico`; CLI: `test_cli_grava_e_imprime_resumo` (`--semente 1 --alunos 3 --dias 7 --inicio 2026-01-05T00:00:00Z --db <tmp>`: retorno 0; contagens impressas batem com `eventos_brutos`), `test_cli_com_defeitos_mostra_duplicados_e_rejeitados` (ambos > 0), `test_cli_inicio_sem_fuso_da_erro_de_uso`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

---

# F4 — Pipeline

### US11: Consumo de eventos com atomicidade

**Branch:** `feat/us11-consumidor` · **Depende de:** US6, US7, US8

**Files:** Create `pipeline/fila.py`, `pipeline/consumidor.py`, `tests/test_consumidor.py`

**Interfaces:**
- `pipeline/fila.py` (SQL sobre `eventos_brutos`): `listar_pendentes(conn) -> list[Evento]` (ordem `(occurred_at, event_id)`); `buscar(conn, event_id) -> tuple[Evento, str] | None` (evento, status); `marcar_processado(conn, event_id, agora_texto: str) -> None`; `marcar_rejeitado(conn, event_id, motivo: str) -> None`.
- `pipeline/consumidor.py`: `class EventoInvalido(Exception)`; `class EventoAtrasado(Exception)` (atributo `student_id`); `ResumoProcessamento` (dataclass): `processados: int`, `rejeitados: int`, `alunos_reconstruidos: int = 0`; `processar_evento(conn, event_id: str, *, agora=None) -> str` (devolve `"processado"`, `"rejeitado"` ou `"ignorado"` quando já estava processado/rejeitado; `event_id` desconhecido → `KeyError`); `processar_pendentes(conn, *, agora=None) -> ResumoProcessamento`.
- Regras: um evento = uma transação (`BEGIN IMMEDIATE` … `COMMIT`): lê estados via repositório, chama `aplicar_evento` (importado no módulo como `aplicar_evento`, para os testes poderem trocá-lo), `salvar`, `marcar_processado` (`processado_em` = `agora()`). `EventoInvalido` (ex.: exercício fora do catálogo) → `ROLLBACK`, marca `rejeitado` com motivo, segue o lote. Qualquer outra exceção → `ROLLBACK`, evento continua `pendente`, exceção sobe. Evento com chave `(occurred_at, event_id)` menor que a do aluno → `EventoAtrasado` (evento fica pendente; a US12 trata).

- [ ] **Step 1: Testes (falhando)**, com `db.abrir(tmp)`, eventos via `evento_dict` + `receber`: `e1` iniciado 12:00:00, `e2` respondido certo (100 s) 12:01:00, `e3` respondido errado (50 s) 12:02:00, todos em `funcoes-3`. `test_processa_pendentes_em_ordem_e_atualiza_o_gemeo` (rating do tópico `funcoes` ≈ 999.263, `tentativas==2`, `acertos==1`; aluno: `respostas==2`, `velocidade_media_s==90.0`, `erros_seguidos==1`, `ultimo_evento_id=="e3"`; exercício `funcoes-3`: `tentativas==2`, `acertou_alguma_vez`; três linhas `processado` com `processado_em` preenchido; resumo `processados==3`); `test_processar_evento_por_id_e_idempotente` (segunda chamada → `"ignorado"`, estado idêntico); `test_segunda_execucao_nao_faz_nada` (resumo zerado); `test_sem_pendentes_nao_da_erro`; `test_erro_de_dominio_rejeita_e_o_lote_segue` (linha inserida direto com `exercise_id` fora do catálogo → `rejeitado` com motivo, os outros processados, `rejeitados==1`); `test_excecao_inesperada_desfaz_o_evento_e_sobe` (trocar `aplicar_evento` por função que falha no 2º evento: 1º continua `processado` e aplicado, 2º `pendente`, gêmeo só com o 1º, `RuntimeError` propagada); `test_evento_atrasado_levanta_e_fica_pendente` (processa `e2`, depois chega evento com horário anterior → `EventoAtrasado`, pendente, gêmeo intacto); `test_alunos_diferentes_sao_independentes`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

### US12: Evento atrasado, reprocessamento e CLI

**Branch:** `feat/us12-reconstrucao-cli` · **Depende de:** US11

**Files:** Modify `pipeline/fila.py`, `pipeline/consumidor.py`; Create `pipeline/executar.py`, `tests/test_reconstrucao.py`, `tests/test_cli_executar.py`

**Interfaces:** em `fila.py`: `eventos_do_aluno(conn, student_id) -> list[Evento]` (status ≠ `rejeitado`, ordem `(occurred_at, event_id)`), `devolver_todos_a_pendente(conn) -> None` (só os não rejeitados). Em `consumidor.py`: `reconstruir_aluno(conn, student_id, *, agora=None) -> int` (transação única: `apagar_aluno`, reaplica todos os eventos do aluno em ordem, marca todos `processado`; `EventoInvalido` durante a reconstrução rejeita o evento de forma permanente e segue; devolve quantos foram aplicados); `reprocessar_tudo(conn, *, agora=None) -> ResumoProcessamento` (`apagar_tudo`, `devolver_todos_a_pendente`, `processar_pendentes`); `processar_pendentes` passa a tratar `EventoAtrasado` chamando `reconstruir_aluno` (conta em `alunos_reconstruidos`, no máximo uma vez por aluno por chamada; pendentes daquele aluno já processados pela reconstrução são pulados). `pipeline/executar.py`: `main(argv=None) -> int`, opções `--db`, `--reprocessar`; imprime `processados: N`, `rejeitados: N`, `alunos_reconstruidos: N`; `python -m pipeline.executar` funciona.

- [ ] **Step 1: Testes (falhando).** Auxiliar em `tests/`: `dump_gemeo(conn) -> list[tuple]` (todas as linhas das três tabelas do gêmeo, ordenadas). `test_ordem_de_chegada_nao_importa` (`simular(semente=7, n_alunos=4, inicio=2026-01-05T00:00:00Z, dias=14)`: banco A com eventos em ordem cronológica e um `processar_pendentes`; banco B com os mesmos eventos embaralhados (`random.Random(0)`), ingeridos em 3 lotes com `processar_pendentes` entre eles; `dump_gemeo(A) == dump_gemeo(B)` com igualdade exata, e `alunos_reconstruidos > 0` em B); `test_empate_de_horario_desempata_por_event_id` (dois eventos do mesmo aluno com o mesmo `occurred_at`, ids `"a"` e `"b"`; processar `"b"` e depois `"a"` chegando → reconstrução → igual a processar `a` depois `b`); `test_reprocessar_tudo_reproduz_o_estado_incremental` (exato); `test_reconstruir_aluno_e_idempotente`; `test_rejeitado_continua_rejeitado_no_reprocessamento` (e não é aplicado); `test_reconstruir_so_afeta_o_aluno_alvo`; `test_reprocessar_banco_vazio`; CLI: `test_cli_processa_e_imprime`, `test_cli_reprocessar_chega_ao_mesmo_estado`, `test_cli_banco_novo_sem_pendentes_imprime_zeros`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

---

# F5 — Recomendação e API

### US13: Recomendação (função pura)

**Branch:** `feat/us13-recomendacao` · **Depende de:** US2, US3, US4

**Files:** Modify `modelos.py`; Create `recomendacao/escolher.py`, `tests/test_recomendacao.py`

**Interfaces:** em `modelos.py`: `ExercicioRecomendado(id: str, enunciado: str, dificuldade: int)` e `Recomendacao(student_id: str, topico: str | None, exercicio: ExercicioRecomendado | None, expectativa_acerto: float | None, probabilidade_evasao: float, motivo: str)`. Em `recomendacao/escolher.py`: `ALVO_PADRAO = 0.70`, `ALVO_RECUPERACAO = 0.85`, `LIMIAR_EVASAO = 0.60`; `escolher(student_id: str, topicos: Sequence[EstadoTopico], resolvidos: set[str], probabilidade_evasao: float, *, topicos_catalogo: Sequence[str] | None = None, exercicios_catalogo: Sequence[ExercicioCatalogo] | None = None) -> Recomendacao` (padrões: `catalogo.TOPICO_IDS`, `catalogo.EXERCICIOS`). Regra do design §8; alvo `ALVO_RECUPERACAO` só se `probabilidade_evasao > LIMIAR_EVASAO` (estritamente maior); desempate de exercício pelo menor `id`; `motivo` = `"<parte do tópico>; <parte do alvo>"`, com "tópico mais fraco" ou "tópico ainda não tentado" e "exercício com cerca de 70% de chance de acerto" ou "risco de evasão alto, exercício mais fácil (cerca de 85% de chance de acerto)"; sem nada a recomendar, `topico=None`, `exercicio=None`, `expectativa_acerto=None` e motivo contendo "todos".

- [ ] **Step 1: Testes (falhando)** com catálogo pequeno injetado: tópico `a` (exercícios `a-1` dif. 1, `a-2` dif. 2, `a-4` dif. 4) e tópico `b` (`b-2` dif. 2, `b-4` dif. 4, `b-5` dif. 5). `test_escolhe_o_topico_de_menor_rating` (a=1100, b=900 → `b`); `test_topico_nao_tentado_conta_como_1000` (a=1100 tentado, b ausente → `b`, motivo com "ainda não tentado"); `test_empate_de_topico_vai_para_a_ordem_do_catalogo`; `test_exercicio_mais_perto_de_70_por_cento` (rating 1200 em um tópico com dificuldades 2, 4, 5 → dificuldade 4; `expectativa_acerto ≈ 0.64006`); `test_evasao_alta_sobe_o_alvo_para_85` (mesma situação com evasão 0.7 → dificuldade 2; motivo com "risco de evasão alto"); `test_limiar_e_estrito` (evasão exatamente 0.60 → alvo 70%); `test_exercicios_resolvidos_sao_excluidos` (resolve o escolhido → vai para o próximo mais perto); `test_topico_todo_resolvido_e_pulado`; `test_tudo_resolvido_devolve_none` (`"todos"` no motivo); `test_empate_de_exercicio_vai_para_o_menor_id` (dois exercícios de mesma dificuldade, ids `x2` e `x1` → `x1`); `test_deterministica`; `test_aluno_sem_nenhum_estado` (usa catálogo real: primeiro tópico `funcoes`); `test_motivo_nao_vazio`.
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

### US14: API (FastAPI)

**Branch:** `feat/us14-api` · **Depende de:** US5, US7, US13

**Files:** Modify `modelos.py`; Create `api/main.py`, `tests/test_api.py`

**Interfaces:** em `modelos.py`: `TopicoResposta(topic_id: str, rating_elo: float, tentativas: int, acertos: int)` e `GemeoResposta(student_id: str, ultimo_evento_em: datetime, velocidade_media_s: float | None, probabilidade_evasao: float, topicos: list[TopicoResposta])`. Em `api/main.py`: `create_app(db_path: Path | str = DEFAULT_DB_PATH, agora: Callable[[], datetime] | None = None) -> FastAPI` (`agora` padrão: UTC real); conexão somente leitura aberta **por requisição** (dependência com `yield`, fechada ao final); `BancoIndisponivel` → `503`; `GET /saude` → `{"status": "ok"}`; `GET /alunos/{student_id}/gemeo` → `GemeoResposta`; `GET /alunos/{student_id}/recomendacao` → `Recomendacao` (usa `repositorio`, `evasao.probabilidade_evasao(estado, agora())` e `escolher`); aluno sem linha em `gemeo_aluno` → `404` com `{"detail": "aluno nao encontrado"}`. Módulo expõe `app = create_app(db_path=<env GEMEO_DB ou padrão>, agora=<relógio fixo se GEMEO_AGORA (ISO com fuso) estiver definida>)` para `uvicorn api.main:app`; valor inválido em `GEMEO_AGORA` levanta `ValueError` na importação (falha alto).

- [ ] **Step 1: Testes (falhando)** com `TestClient`, banco temporário preenchido por `receber` + `processar_pendentes` (eventos `e1..e3` da US11, mais um aluno `so-iniciou` com um único `exercicio_iniciado`) e `agora` fixo. `test_saude_ok`; `test_saude_sem_banco_da_503` (caminho inexistente); `test_aluno_desconhecido_404_nos_dois_endpoints` (inclui id com espaço/caracteres especiais → 404, nunca 500); `test_gemeo_formato_e_valores` (ratings por tópico ordenados, `funcoes` ≈ 999.263, velocidade 90.0, `probabilidade_evasao` igual ao calculado por `evasao.probabilidade_evasao` sobre o estado lido); `test_aluno_so_com_iniciado` (`/gemeo` 200 com `topicos == []` e `velocidade_media_s is None`; `/recomendacao` com `topico == "funcoes"` e exercício não nulo); `test_recomendacao_formato` (`exercicio.id`, `enunciado`, `dificuldade`, `expectativa_acerto`, `motivo`); `test_motivo_acompanha_o_limiar_de_evasao` (avançar `agora` em 30 dias: `"risco de evasão alto" in motivo` se e só se `probabilidade_evasao > 0.60`, sem fixar os pesos); `test_api_nao_altera_o_banco` (`dump` das tabelas igual antes/depois de chamar os três endpoints); `test_docs_disponivel` (`/docs` 200); `test_relogio_do_ambiente` (`GEMEO_AGORA` válida fixa o relógio; inválida → `ValueError` ao importar o módulo recarregado).
- [ ] **Step 2: Falhar → implementar → passar → suíte verde → commit → PR.**

---

# F6 — Fechamento

### US15: Convergência do Elo e fluxo ponta a ponta

**Branch:** `feat/us15-ponta-a-ponta` · **Depende de:** US9, US10, US11, US14

**Files:** Create `tests/utilitarios.py`, `scripts/comparar_habilidades.py`, `tests/test_utilitarios.py`, `tests/test_ponta_a_ponta.py`

**Interfaces:** `tests/utilitarios.py`: `spearman(xs: Sequence[float], ys: Sequence[float]) -> float` (postos médios para empates, Pearson dos postos; implementação própria, sem scipy). `scripts/comparar_habilidades.py`: `LinhaComparacao` (dataclass: `student_id`, `perfil`, `topic_id`, `habilidade_verdadeira`, `rating_elo`, `tentativas`), `comparar(conn, simulacao) -> list[LinhaComparacao]` (só pares aluno×tópico com tentativas) e `main(argv=None) -> int` que simula (`--semente 42 --alunos 12 --dias 42 --inicio …`), ingere num banco temporário, processa, imprime a tabela e a correlação de Spearman por tópico (usada no README). Script de composição: fora do teste de arquitetura.

- [ ] **Step 1: Testes do `spearman` (falhando).** `xs=[1,2,3,4]`, `ys=[10,20,30,40]` → `1.0`; `ys` invertido → `-1.0`; com empates `xs=[1,2,2,3]`, `ys=[1,3,2,4]` → `≈ 0.9487` (`abs=1e-3`); tamanhos diferentes → `ValueError`.
- [ ] **Step 2: Testes ponta a ponta (falhando)**, com `simular(semente=42, n_alunos=12, inicio=2026-01-05T00:00:00Z, dias=42)`. `test_elo_converge_para_a_habilidade_verdadeira` (por tópico, entre alunos com ≥ 5 tentativas nele e ao menos 6 alunos: Spearman entre habilidade verdadeira final e `rating_elo` ≥ `LIMIAR_CONVERGENCIA`; o limiar é escolhido pelo construtor depois de medir, alto o bastante para falhar se o Elo estiver quebrado); `test_limiar_nao_e_trivial` (controle negativo: permutando os ratings entre alunos com `random.Random(0)`, a correlação fica abaixo do limiar); `test_defeitos_nao_mudam_o_gemeo_final` (simulação com `defeitos=True` ingerida em ordem embaralhada + `processar_pendentes` → `dump_gemeo` **igual**, exato, ao da simulação sem defeitos; os malformados aparecem como `rejeitado`); `test_evasao_distingue_perfis` (com `agora = inicio + dias`, a média de `probabilidade_evasao` dos `desistente` > a dos `dedicado`, lida pela API `TestClient`; e toda `/recomendacao` dos 12 alunos responde 200).
- [ ] **Step 3: Falhar → implementar o utilitário e o script → passar → suíte verde → commit → PR.**

### US16: README e CLAUDE.md finais

**Branch:** `feat/us16-documentacao` · **Depende de:** todas

**Files:** Modify `README.md`, `CLAUDE.md`

- [ ] **Step 1: Rodar o fluxo completo de verdade** num banco temporário e guardar a saída real: `python -m ingestao.simular --semente 42 --alunos 12 --dias 42 --inicio 2026-01-05T00:00:00Z --defeitos --db <tmp>`; `python -m pipeline.executar --db <tmp>`; `GEMEO_DB=<tmp> GEMEO_AGORA=2026-02-16T00:00:00Z uvicorn api.main:app` com `curl` em `/saude`, `/alunos/aluno-001/gemeo`, `/alunos/aluno-003/recomendacao`; `python -m scripts.comparar_habilidades`.
- [ ] **Step 2: Escrever o `README.md` (pt-BR, sem jargão comercial):** o que é e por quê; diagrama do fluxo (design §2); como rodar (instalar → simular → processar → API) com as saídas reais do passo 1; camadas e regra de dependência; tabela do modelo de dados; como o Elo, a velocidade e a evasão são calculados; o que é guardado × o que é calculado na leitura; tabela "habilidade verdadeira × Elo estimado" do script; como o pipeline trata duplicado, atrasado, rejeitado e reprocessamento; seção "Evoluções possíveis" (broker de mensagens, BKT, dificuldade que evolui, modelo treinado com dados reais, ponte com o assistente da PoC 1).
- [ ] **Step 3: Atualizar `CLAUDE.md`:** comandos reais, regra de dependência, decisões que não se mudam sem conversar (fonte da verdade nos eventos brutos; domínio puro; API só leitura; relógio injetado; igualdade exata no reprocessamento).
- [ ] **Step 4: Conferir** que todo comando do README roda como escrito; suíte verde; commit; abrir PR (protocolo).

---

## Fechamento do processo (controlador, fora das USs)

- [ ] Revisão final da branch inteira (`main` depois da US16 contra o commit inicial do projeto) no modelo mais capaz, seguindo o SDD: no máximo **uma** onda de correção, com PR próprio `fix:`/`refactor:`, e re-revisão escopada.
- [ ] Registro do fluxo versionado, como na PoC 1: copiar o ledger, os briefs e os relatórios do workspace do SDD para `docs/superpowers/sdd/` e abrir PR `docs: record the subagent-driven execution`.
- [ ] Sugerir ao Igor rodar a demo uma vez manualmente (comandos do README).

## Autoauditoria do plano

- **Cobertura do design:** §2 fluxo → US8/US11/US14; §3 estrutura e regra → US1; §4 eventos → US2/US8; §5 modelo de dados → US3/US7; §6 pipeline (atomicidade, atrasado, reprocessar, idempotência, igualdade exata) → US11/US12; §7 cálculos → US4/US5/US6; §8 recomendação e API → US13/US14; §9 simulador, defeitos e CLIs → US9/US10 (e CLI do pipeline na US12); §10 catálogo → US3; §11 testes → distribuídos e US15; §12 entregáveis → US1/US16 e fechamento.
- **Tipos entre USs:** nomes e assinaturas conferidos entre as seções "Interfaces" (`EstadoAtualizado`, `aplicar_evento`, `salvar`, `ResultadoIngestao`, `escolher`, `probabilidade_evasao`, `Simulacao.perfis`, `ResumoProcessamento`).
- **Arquivos disjuntos por onda:** onda 2 (`modelos.py` / `catalogo`+`db.py` / `gemeo/elo.py`), onda 3 (`gemeo/evasao.py` / `atualizacao.py` / `repositorio.py`), onda 4 (`ingestao/receber.py` / `ingestao/simulador.py` / `recomendacao/` + `modelos.py` só na US13), onda 5 (`ingestao/simulador.py`+`simular.py` / `pipeline/` / `api/` + `modelos.py` só na US14), onda 6 (`pipeline/` / `tests/`+`scripts/`).
