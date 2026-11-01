# US7 Repositório do gêmeo: relatório

Status: DONE. PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/7

## Implementado
`gemeo/repositorio.py` com ler_aluno, ler_topicos (ordenado por topic_id), ler_topico, ler_exercicio, ler_exercicios_resolvidos, salvar (upsert via ON CONFLICT das linhas não nulas), apagar_aluno, apagar_tudo. Usa as tabelas reais gemeo_aluno/gemeo_topico/gemeo_exercicio de db.py. Datas: strftime/strptime `%Y-%m-%dT%H:%M:%SZ` com tzinfo UTC; floats passados direto (REAL de 8 bytes, sem arredondar). Nenhuma função faz commit ou abre transação.

## Testes
`tests/test_repositorio.py`: 10 testes (os 8 pedidos + velocidade_media_s None + ordenação de ler_topicos). Suíte completa: 75 passed.

## TDD
- RED: `$PY -m pytest tests/test_repositorio.py -q` -> `ImportError: cannot import name 'repositorio' from 'gemeo'` (erro de coleta).
- GREEN: mesmo comando -> `10 passed`; suíte `-q` -> `75 passed`.

## Arquivos
gemeo/repositorio.py, tests/test_repositorio.py (apenas esses).

## Autorrevisão
Sem problemas. `salvar` fora de uma transação explícita executa até 3 statements em autocommit (não atômico); o pipeline (US11) deve chamá-lo dentro de BEGIN IMMEDIATE, como previsto. A branch está atrás da main (US5 já integrada); o diff do PR contém só os 2 arquivos novos.

## Commits
test: add twin repository tests; feat: add twin repository
