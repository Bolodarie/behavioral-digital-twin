# behavioral-digital-twin

PoC de portfólio: pipeline de dados com gêmeo digital comportamental para um curso de álgebra (cursinho popular). Python 3.10, SQLite, Pydantic, FastAPI. O objetivo é **demonstrar engenharia de dados e separação de camadas**, não evoluir um produto.

Design completo e aprovado: `docs/superpowers/specs/2026-10-31-behavioral-digital-twin-design.md`. Em caso de dúvida, ele manda; se for preciso divergir, atualize o documento junto.

## Comandos

```bash
pip install -r requirements-dev.txt  # runtime (pydantic, fastapi, uvicorn) + pytest, httpx
pytest                               # suíte de testes
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

- **Eventos brutos são a fonte da verdade:** tabela só de inserção, idempotência por `event_id`; apagar o gêmeo e reprocessar tem que dar exatamente o mesmo estado.
- **Ordem `(occurred_at, event_id)`:** o desempate por `event_id`, não pela chegada, torna o resultado independente da ordem de chegada.
- **Todo valor do gêmeo vem dos eventos:** `atualizado_em`/`ultimo_evento_em` usam o horário do evento, nunca o relógio real; nada é arredondado ao gravar.
- **Lógica de domínio pura:** `elo`, `evasao`, `atualizacao` e `recomendacao/escolher` recebem estado e evento e devolvem novo estado, sem SQL. Nada de `datetime.now()` fora das bordas (CLIs, `create_app`, `agora` injetável).
- **Banco:** conexões com `isolation_level=None` e transações explícitas; `salvar` do repositório nunca faz commit. A API usa conexão somente leitura e não dispara processamento.
- **Simulador independente do estimador:** `ingestao` não importa `gemeo.elo`; reimplementa a fórmula de propósito (um teste garante que as escalas não divergem).

## Convenções

- Idioma: docstrings curtas, mensagens, seed e README em **português do Brasil**; documentação sem jargão comercial.
- Python 3.10 (type hints modernos, sem recursos 3.11+). Contratos entre camadas em Pydantic (`modelos.py`), não dicts soltos (exceção: o simulador emite `dict`, a ingestão converte).
- Timestamps: UTC, texto `YYYY-MM-DDTHH:MM:SSZ` no banco; `datetime` com fuso nos modelos; resolução de 1 s.
- Dependências de runtime só `pydantic>=2`, `fastapi>=0.110`, `uvicorn`; `httpx` e `pytest` só em dev. `sqlite3` da stdlib; nada de numpy, scipy, pandas, SQLAlchemy.
- Banco em `data/` (não versionar `*.db`). Commits em Conventional Commits, em inglês curto.
- Testes enxutos e focados no comportamento, com relógio injetado e semente fixa; nunca depender da data de hoje. Antes de dizer que algo está pronto, rode `pytest`.
