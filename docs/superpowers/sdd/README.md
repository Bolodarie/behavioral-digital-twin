# Registro da execução com subagentes

Esta pasta guarda como o projeto foi construído: cada história de usuário (US) do plano `docs/superpowers/plans/2026-11-01-behavioral-digital-twin.md` foi feita por um subagente próprio, revisada por outro, e entrou na `main` por um Pull Request.

## O que tem aqui

- `ledger.md`: o diário do controlador. Tem a tabela de conferência feita antes de começar, cada rodada de revisão e correção, os achados menores adiados e as decisões tomadas pelo caminho (`Ruling R1` a `R14`).
- `tasks/usNN-brief.md`: o pedido que cada subagente recebeu (restrições globais do plano, decisões de planejamento e o texto da US).
- `tasks/usNN-report.md`: o relatório que cada subagente escreveu (o que fez, testes, evidência de TDD, preocupações). Quando houve rodada de correção, o relatório da correção está no fim do mesmo arquivo.
- `tasks/final-fix-brief.md` e `tasks/final-fix-report.md`: a onda única de correções que veio da revisão final do projeto inteiro.

Os diffs entregues aos revisores não foram copiados: estão no histórico do git e nos PRs.

## Como o fluxo funcionou

Para cada US: um worktree próprio a partir da `main`, um subagente implementador (TDD, commits pequenos, PR para a `main`), um revisor de tarefa (conformidade com o pedido e qualidade), até cinco rodadas de correção com re-revisão escopada, e então o merge com *squash*. Até três subagentes trabalharam ao mesmo tempo, sempre em USs que mexem em arquivos diferentes.

| Onda | USs |
|---|---|
| 1 | US1 |
| 2 | US2, US3, US4 |
| 3 | US5, US6, US7 |
| 4 | US8, US9, US13 |
| 5 | US10, US11, US14 |
| 6 | US12 |
| 7 | US15 |
| 8 | US16 |

(Dois desvios do plano, registrados no ledger: a US15 passou a depender da US12, porque o teste de igualdade exata com defeitos precisa da reconstrução de eventos atrasados; e a US14 montou seu banco de teste direto pelo domínio, sem depender do pipeline, que ainda não estava na `main`.)

Pull Requests: US1 #1, US2 #2, US4 #3, US3 #4, US5 #5, US6 #6, US7 #7, US9 #8, US8 #9, US13 #10, US14 #11, US10 #12, US11 #13, US12 #14, US15 #15, US16 #16, onda de correções da revisão final #17.

Rodadas de correção: US2, US3, US6 e US8 precisaram de uma; a US15 precisou de duas; as outras dez USs passaram na primeira revisão. A revisão final do projeto inteiro (modelo mais capaz) devolveu "com correções", sem nada crítico, e as correções entraram numa única onda (#17), também revisada.

Os subagentes implementadores não tiveram permissão para abrir o PR (ou para enviar a branch) nas USs 12, 15 e 16 e na onda final. Nesses casos, o Igor autorizou explicitamente que o controlador abrisse os PRs.

Modelos usados: implementadores e revisores de tarefa em `sonnet` (a US4, só com fórmulas, em `haiku`; re-revisões pequenas em `haiku`; a revisão da US12 em `opus`); revisão final do projeto em `fable`.
