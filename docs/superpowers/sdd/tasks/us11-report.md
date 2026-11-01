# US11 report: consumo de eventos com atomicidade

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/13 (branch feat/us11-consumidor, worktree .worktrees/us11).

## Implemented
- `pipeline/fila.py`: `listar_pendentes`, `buscar`, `marcar_processado`, `marcar_rejeitado` (interface da US) + `status_de` (extra, para distinguir id desconhecido de linha rejeitada na ingestao, que nao tem campos de evento).
- `pipeline/consumidor.py`: `EventoInvalido`, `EventoAtrasado(student_id)`, `ResumoProcessamento`, `processar_evento`, `processar_pendentes`; `aplicar_evento` importado no modulo (monkeypatchavel); `repositorio` importado como modulo.
  - Uma transacao por evento via context manager (`BEGIN IMMEDIATE`/`COMMIT`; `ROLLBACK` em qualquer excecao, guardado por `conn.in_transaction`). O status e relido dentro da transacao (idempotencia segura entre processos).
  - `EventoInvalido` (exercicio fora do catalogo; tambem topic divergente do catalogo, como `receber` faz): rollback, nova transacao marca `rejeitado` com motivo (<=500 chars), lote segue.
  - Atrasado: chave completa `(occurred_at, event_id) < (ultimo_evento_em, ultimo_evento_id)` -> `EventoAtrasado`, evento pendente, contrato provisorio documentado na docstring (US12 troca por reconstrucao).
  - Qualquer outra excecao (incl. `ValueError` de `aplicar_evento`): rollback, pendente, sobe.
  - `agora()` so carimba `processado_em`.

## Tests (tests/test_consumidor.py, 14)
Os 9 da US + KeyError para id desconhecido, evento rejeitado na ingestao -> `ignorado`, topic divergente -> rejeitado, falha no `salvar` apos escrita parcial (rollback), empate de horario decidido por `event_id`, relogio padrao.

TDD:
- RED: `pytest tests/test_consumidor.py -q` -> `ModuleNotFoundError: No module named 'pipeline.consumidor'` (1 error during collection).
- GREEN: `pytest tests/test_consumidor.py -q` -> `14 passed in 0.21s`.
- Suite completa: `217 passed in 1.39s` (inclui test_arquitetura).

## Files
pipeline/fila.py, pipeline/consumidor.py, tests/test_consumidor.py. Commit: 979da0a `feat(pipeline): consume pending events atomically`.

## Self-review / concerns
- `buscar` devolve `None` tambem para linhas rejeitadas na ingestao (sem campos de evento); `processar_evento` usa `status_de` antes, entao nao ha problema.
- `listar_pendentes` reconstroi `Evento` por Pydantic; uma linha pendente corrompida direto no banco levantaria `ValidationError` e interromperia o lote (receber nunca grava isso).
- `ultimo_evento_id` None tratado como `""` na comparacao (o modelo exige str; apenas defesa).
- `EventoAtrasado` interrompe `processar_pendentes` (os eventos posteriores ficam pendentes); a US12 deve tratar. `alunos_reconstruidos` fica 0 por enquanto.
- Nenhuma atribuicao de IA em commits, PR ou arquivos.
