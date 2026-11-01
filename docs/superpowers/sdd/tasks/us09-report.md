# US9 Simulador - relatório

## Implementado
`ingestao/simulador.py`: `PERFIS`, `Simulacao` (dataclass congelada), `simular(semente, n_alunos, inicio, dias)`, `rating_do_exercicio`, `probabilidade_base` (escala do Elo reimplementada, sem importar `gemeo`). Importa só `catalogo`.
- Eventos válidos saem de um único `random.Random(semente)`; `event_id` = UUID v4 construído de `getrandbits(128)` (sem `uuid4()`). Docstring do módulo registra que aleatoriedade extra (defeitos, US10) deve usar outro fluxo (R3). `defeitos` não foi implementado.
- Perfis em rodízio. dedicado: dia ativo com p=0.85, 3-6 exercícios/dia, abandono 5%. irregular: sessões de 1-2 dias, lacunas de 4-7 dias, 2-4 exercícios/dia, abandono 15%. desistente: p=0.8 só nos primeiros int(0.4*dias) dias, 2-5 exercícios/dia, abandono 40%.
- Tempo = (45+45*dificuldade)*fator_perfil*U(0.6,1.6) s (>=1); `iniciado` sempre >=1 s antes do encerramento. Acerto: probabilidade_base + U(-0.05,0.05), limitado a [0.02,0.98]. Habilidade +2.0 por resposta (só cresce). Escolha do exercício favorece rating próximo da habilidade.
- ValueError: `inicio` sem fuso, `n_alunos<1`, `dias<1`.

## Testes
`tests/test_simulador.py`: 31 testes (testes comportamentais parametrizados em sementes 42, 7, 2026; reprodutibilidade/semente diferente em 42). Todos passam.
Robustez: rodei temporariamente a suíte com 300 sementes (2704 testes): todos passaram. Voltei para 3 sementes.
Suíte completa: 104 passed.

## TDD
RED: `pytest tests/test_simulador.py -q` -> `ImportError: cannot import name 'simulador' from 'ingestao'` (collection error).
GREEN: `pytest tests/test_simulador.py -q` -> `31 passed in 0.22s`; `pytest -q` -> `104 passed`.
(Testes e implementação foram para o mesmo commit.)

## Arquivos
ingestao/simulador.py, tests/test_simulador.py.

## Autorrevisão / preocupações
- Para `dias` pequeno (ex.: 1-2), o desistente não gera eventos (int(0.4*dias)=0); aceitável.
- Eventos de um dia ficam dentro do dia (início 8h-18h + <1h), então a janela e o limite do desistente valem para qualquer `inicio` UTC; `inicio` é normalizado para UTC sem microssegundos.
- Sem preocupações abertas.

PR: https://github.com/Bolodarie/behavioral-digital-twin/pull/8
