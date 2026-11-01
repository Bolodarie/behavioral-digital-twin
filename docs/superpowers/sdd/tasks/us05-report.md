# US5 relatório: probabilidade de evasão

Status: DONE. Commit 5634fde "feat(gemeo): add dropout probability". PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/5

## Implementado
`gemeo/evasao.py`: `probabilidade_evasao(estado, agora) -> float`, pura; constantes B0=-2.0, W_ABANDONO=3.0, W_ERROS=1.5, W_DESEMPENHO=-2.0, W_INATIVIDADE=3.0, tetos 5 erros e 14 dias. Importa só `modelos`.
`tests/test_evasao.py`: 8 testes (fábrica local `estado(dias_inativo, **campos)`, `agora` fixo).

## TDD
RED: `$PY -m pytest tests/test_evasao.py -q` -> `ModuleNotFoundError: No module named 'gemeo.evasao'` (erro de coleta).
GREEN: mesmo comando -> `8 passed`. Suíte completa: `51 passed`.

## Arquivos
gemeo/evasao.py, tests/test_evasao.py (nenhum outro).

## Autorrevisão
Com os pesos sugeridos: ativo ~0,11 (< 0,3), sumido ~0,99 (> 0,7). z limitado a [-4, 5,5], então nunca satura em 0/1 exato. Entre os testes, a igualdade exata do teto (30 dias vs 14, erros 9 vs 5) é segura porque o termo vira o mesmo float. Teste de "agora anterior" usa dias_inativo=-2.

## Preocupações
Nenhuma.
