# behavioral-digital-twin

PoC de portfólio: pipeline de dados com gêmeo digital comportamental para um curso de álgebra (cursinho popular). Python 3.10, SQLite, Pydantic v2, FastAPI. O objetivo é **demonstrar engenharia de dados e separação de camadas**, não evoluir um produto.

Design completo e aprovado: `docs/superpowers/specs/2026-10-31-behavioral-digital-twin-design.md`. Em caso de dúvida, ele manda; se for preciso divergir, atualize o documento junto. O README descreve o que o código faz hoje (fórmulas, constantes, limitações): mudou o código, confira o README.

## Comandos

```bash
pip install -r requirements-dev.txt   # runtime (pydantic, fastapi, uvicorn) + pytest, httpx, httpx2
pytest                                # suíte de testes

python -m ingestao.simular --semente 42 --alunos 12 --dias 42 --inicio 2026-01-05T00:00:00Z --defeitos   # [--db caminho]
python -m pipeline.executar [--reprocessar]                                                              # [--db caminho]
GEMEO_AGORA=2026-02-16T00:00:00Z uvicorn api.main:app             # API; GEMEO_DB escolhe o banco (padrão data/gemeo.db)
python -m scripts.comparar_habilidades                            # tabela "habilidade verdadeira × Elo estimado"
```

## Regra de dependência (inegociável)

`X ──► Y` = X pode importar Y:

```
ingestao     ──► modelos, db, catalogo
pipeline     ──► gemeo, modelos, db, catalogo
gemeo        ──► modelos, db, catalogo
recomendacao ──► gemeo (só módulos puros: elo, evasao), modelos, catalogo
api          ──► recomendacao, gemeo, modelos, db
db           ──► catalogo
catalogo, modelos ──► (nada do projeto)
```

- `recomendacao` nunca importa `gemeo.repositorio`; quem lê o banco e chama o recomendador é a API.
- `tests/test_arquitetura.py` (via `ast`, incluindo `importlib` e `__import__`) falha se qualquer fronteira for violada. `tests/` e `scripts/` ficam de fora. Não enfraqueça esse teste para fazer código passar; corrija o import.

## Decisões que não se mudam sem conversar

- **Eventos brutos são a fonte da verdade:** `eventos_brutos` só recebe inserção de eventos (depois só mudam `status`, `motivo_rejeicao` e `processado_em`); idempotência por `event_id`. O gêmeo é sempre reconstruível a partir dela: apagar o gêmeo e reprocessar tem que dar exatamente o mesmo estado.
- **Ordem `(occurred_at, event_id)`:** o desempate por `event_id`, não pela chegada, torna o resultado independente da ordem de chegada. Evento atrasado (chave menor que a do aluno) reconstrói o aluno.
- **Lógica de domínio pura:** `elo`, `evasao`, `atualizacao` e `recomendacao/escolher` recebem estado e evento e devolvem novo estado, sem SQL. SQL só em `gemeo/repositorio`, `ingestao/receber` e `pipeline/fila`.
- **API só leitura:** conexão `mode=ro`, sem como disparar processamento. A probabilidade de evasão não é gravada: é calculada na leitura (o sumiço do aluno não gera evento).
- **Relógio injetado:** `agora` é parâmetro (CLIs, `create_app`, `GEMEO_AGORA`); nada de `datetime.now()` fora das bordas. Todo valor do gêmeo vem dos eventos: `atualizado_em`/`ultimo_evento_em` usam o horário do evento, e nada é arredondado ao gravar.
- **Igualdade exata no reprocessamento:** testes comparam o gêmeo com `==`, não com tolerância. Por isso a média móvel é sempre `x + ALFA * (alvo - x)`; não reescreva a conta em outra forma.
- **Simulador independente do estimador:** `ingestao` não importa `gemeo.elo`; reimplementa a escala de propósito, e `test_escala_igual_a_do_elo` guarda contra divergência. Não "reaproveite" o `elo` no simulador.
- **Erros:** erro de domínio ligado ao evento (`EventoInvalido`) rejeita de forma permanente e o lote segue; qualquer outra exceção desfaz o evento, ele fica `pendente` e a exceção sobe. Não engula erro inesperado.
- **Banco:** conexões com `isolation_level=None` e transações explícitas; `salvar` do repositório nunca faz commit.

## Convenções

- Idioma: docstrings curtas, mensagens, seed e README em **português do Brasil**; documentação sem jargão comercial.
- Python 3.10 (type hints modernos, sem recursos 3.11+). Contratos entre camadas em Pydantic (`modelos.py`), não dicts soltos (exceção: o simulador emite `dict`, a ingestão converte).
- Timestamps: UTC, texto `YYYY-MM-DDTHH:MM:SSZ` no banco; `datetime` com fuso nos modelos; resolução de 1 s.
- Dependências de runtime só `pydantic>=2`, `fastapi>=0.110`, `uvicorn`; `httpx`, `httpx2` e `pytest` só em dev. `sqlite3` da stdlib; nada de numpy, scipy, pandas, SQLAlchemy.
- Banco em `data/gemeo.db` (ancorado na pasta do projeto via `DEFAULT_DB_PATH`); não versionar `*.db`.
- Commits em Conventional Commits, em inglês curto (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`), **sem nenhuma atribuição a IA** (nada de `Co-Authored-By`, nada de "Generated with ..." em commit, PR ou arquivo).
- Testes enxutos e focados no comportamento, com relógio injetado e semente fixa; nunca dependem da data de hoje.
- Antes de dizer que algo está pronto, rode `pytest` **e** a demo (simular → processar → API, como no README).
