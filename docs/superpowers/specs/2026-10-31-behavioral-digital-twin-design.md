# behavioral-digital-twin — Design

PoC de portfólio: pipeline de dados que transforma eventos de interação de alunos de álgebra (cursinho popular) em um **gêmeo digital** do aluno: um estado por aluno que é atualizado a cada evento e que alimenta uma API de recomendação. O foco é **engenharia de dados e desenho de back-end** (fluxo de informação, idempotência, ordenação, separação de camadas), não um produto.

Projeto **separado** da PoC `edu-agent-orchestrator` (repositório próprio, banco próprio, catálogo próprio). Uma ponte entre os dois (o assistente de chat consultando o gêmeo) fica só como passo futuro no README.

## 1. Objetivos, não-objetivos, anti-objetivos

**Objetivos**
- Mostrar um fluxo completo e legível: simular eventos → gravar bruto → processar → estado do gêmeo → recomendar.
- Mostrar decisões de engenharia de dados que importam: tabela de eventos brutos como fonte da verdade, idempotência por `event_id`, tratamento de evento atrasado/fora de ordem, atomicidade, reprocessamento do zero, separação entre **estado** (gravado) e **derivado do tempo** (calculado na leitura).
- Código modular, em camadas com dependência em uma direção, verificada por teste.

**Não-objetivos**
- Broker de mensagens real (Kafka, Redis Streams), processamento distribuído, streaming contínuo. Ficam no README como evolução.
- Modelo estatístico treinado, Bayesian Knowledge Tracing, dificuldade de exercício que evolui. Ficam no README como evolução.
- Autenticação, multiusuário, front-end, integração com o chat da PoC 1.

**Anti-objetivos (seria falha mesmo que "funcione")**
- Número no gêmeo que não se explica pelos eventos. Todo valor do gêmeo precisa ser reproduzível: apagar o gêmeo e reprocessar os eventos brutos tem que dar exatamente o mesmo estado.
- Jargão comercial na documentação ("plataforma inteligente", "hiperpersonalização" etc.). README e comentários em linguagem direta.
- Teste que só confirma o que o código já faz, sem apertar o comportamento (ver seção 9).

## 2. Fluxo de informação

```
simulador ──► ingestao ──► eventos_brutos ──► pipeline ──► gemeo (SQLite) ──► api ──► recomendacao
 (gera)       (valida,      (só inserção,     (consome     (estado por       (lê)    (escolhe o
              grava)         com status)       pendentes)   aluno e tópico)           próximo exercício)
```

1. **Ingestão:** o simulador produz eventos como dicionários (imita um produtor externo). `ingestao.receber` valida e grava em `eventos_brutos` com `status='pendente'`. Duplicado (`event_id` já existente) é ignorado; inválido é gravado como `rejeitado` com o motivo.
2. **Processamento:** o pipeline lê os pendentes em ordem `(occurred_at, event_id)` (o desempate por `event_id`, e não pela ordem de chegada, é o que torna o resultado independente da ordem em que os eventos chegaram), aplica cada um ao gêmeo e marca `processado`, tudo na mesma transação.
3. **Gêmeo:** estado por aluno e por aluno×tópico.
4. **Recomendação:** a API lê o gêmeo (somente leitura) e devolve o próximo exercício, com o motivo.

## 3. Estrutura e regra de dependência

```
behavioral-digital-twin/
├── modelos.py            # contratos Pydantic (Evento, estados, Recomendacao)
├── db.py                 # schema, abrir conexão (escrita e somente leitura), DEFAULT_DB_PATH
├── catalogo/             # tópicos e exercícios (dados + seed), sem lógica
├── ingestao/             # simulador.py, receber.py, simular.py (CLI de simulação)
├── pipeline/             # consumidor.py, executar.py (CLI de execução)
├── gemeo/                # elo.py, evasao.py, atualizacao.py, repositorio.py
├── recomendacao/         # escolher.py
├── api/                  # main.py (FastAPI)
├── tests/
└── docs/
```

Dependências permitidas (`X ──► Y` = X pode importar Y):

```
ingestao     ──► modelos, db, catalogo
pipeline     ──► gemeo, modelos, db, catalogo
gemeo        ──► modelos, db, catalogo
recomendacao ──► gemeo (só os módulos puros, como elo e evasao), modelos, catalogo
api          ──► recomendacao, gemeo, modelos, db
db           ──► catalogo
catalogo, modelos ──► (nada do projeto)
```

Proibido: `ingestao` importar `pipeline`/`gemeo`/`recomendacao`/`api`; `pipeline` importar `ingestao`/`recomendacao`/`api`; `gemeo` importar `ingestao`/`pipeline`/`recomendacao`/`api`; `api` importar `ingestao`/`pipeline`. Um teste via `ast` (incluindo `importlib` e `__import__`, como na PoC 1) falha se alguma fronteira for violada.

Lógica de domínio (`elo.py`, `evasao.py`, `atualizacao.py`, `recomendacao/escolher.py`) é **pura**: recebe estado e evento, devolve novo estado, sem SQL. Só `gemeo/repositorio.py` e `ingestao/receber.py` falam com o banco. O recomendador recebe os estados como argumentos; quem lê o banco (via `gemeo/repositorio.py`) e chama o recomendador é a API. A API não tem como disparar processamento: é só leitura, de propósito.

## 4. Eventos

Evento estruturado, tipos fechados:

| campo | tipo | observação |
|---|---|---|
| `event_id` | str | único; garante idempotência |
| `student_id` | str | |
| `exercise_id` | str | tem que existir no catálogo |
| `topic` | str | tem que ser o tópico do exercício no catálogo |
| `event_type` | enum | `exercicio_iniciado`, `exercicio_respondido`, `exercicio_abandonado` |
| `occurred_at` | datetime | ISO 8601 com fuso (sem fuso é rejeitado); qualquer deslocamento é convertido para UTC e a resolução é de 1 segundo (frações são descartadas); gravado como `YYYY-MM-DDTHH:MM:SSZ` (ordena como texto) |
| `payload` | objeto | `exercicio_respondido`: `acertou: bool`, `tempo_gasto_s: int > 0`, ambos com tipo estrito (`"true"`, `1`, `12.5`, `"30"` e `true` no lugar do inteiro são rejeitados) e sem chaves extras; os outros dois: vazio |

Campos extras no nível do evento e identificadores vazios também são rejeitados.

Os exemplos do pedido original mapeiam assim: `iniciou_exercicio_funcoes` → `exercicio_iniciado` com `topic=funcoes`; `errou_equacao_2_grau` → `exercicio_respondido` com `topic=equacao_2_grau`, `acertou=false`; `tempo_gasto_120s` → `tempo_gasto_s=120` no payload da resposta.

**Validação na ingestão** (estrutura + consistência com o catálogo): campos obrigatórios, tipos, payload conforme o tipo, `occurred_at` com fuso, `exercise_id` existente e `topic` batendo. Falha vira linha `rejeitado` (guarda o JSON bruto e o motivo; `event_id` pode ser nulo se o dado nem trouxe um). Não se exige que haja `exercicio_iniciado` antes de um `exercicio_respondido` (produtores reais perdem eventos). Reenviar, com o mesmo `event_id`, um evento que foi `rejeitado` conta como duplicado e é ignorado: a linha rejeitada fica como está (corrigir o produtor significa mandar um `event_id` novo).

## 5. Modelo de dados (SQLite)

Modo WAL, para a API ler enquanto o pipeline escreve. Pipeline e ingestão usam conexão de escrita; a API usa conexão **somente leitura** (`mode=ro`, via `Path.resolve().as_uri()`), como a PoC 1.

- `topicos(id, nome)` e `exercicios(id, topico_id, enunciado, dificuldade 1..5)` — catálogo.
- `eventos_brutos(seq PK autoincrement, event_id UNIQUE nulo-permitido, student_id, exercise_id, topic, event_type, occurred_at, payload_json, bruto_json NOT NULL, recebido_em, status 'pendente'|'processado'|'rejeitado', motivo_rejeicao, processado_em)` — só inserção de eventos; só `status`, `motivo_rejeicao` e `processado_em` são atualizados depois.
- `gemeo_topico(student_id, topic_id, rating_elo, tentativas, acertos, atualizado_em)`, PK `(student_id, topic_id)`.
- `gemeo_exercicio(student_id, exercise_id, tentativas, acertou_alguma_vez)`, PK `(student_id, exercise_id)` — para a recomendação não repetir o que já foi resolvido.
- `gemeo_aluno(student_id PK, velocidade_media_s nulo, taxa_abandono, erros_seguidos, desempenho_relativo, respostas, ultimo_evento_em, ultimo_evento_id, atualizado_em)` — `(ultimo_evento_em, ultimo_evento_id)` é a maior chave `(occurred_at, event_id)` já aplicada ao aluno; `atualizado_em` é igual a `ultimo_evento_em` (vem do horário do evento, nunca do relógio real, para o reprocessamento reproduzir o estado exato).

Todo timestamp é UTC em texto ISO 8601.

## 6. Pipeline

Funções públicas (em `pipeline/consumidor.py`), todas recebendo a conexão:

- `processar_evento(conn, event_id)` — atende o pedido original ("receber um evento novo e atualizar o gêmeo"). Evento já `processado` ou `rejeitado`: não faz nada.
- `processar_pendentes(conn) -> ResumoProcessamento` — laço do dia a dia: contagens de processados, rejeitados e alunos reconstruídos.
- `reconstruir_aluno(conn, student_id)` — apaga o gêmeo desse aluno e reaplica todos os eventos dele (que não estejam `rejeitado`) em ordem `(occurred_at, event_id)`.
- `reprocessar_tudo(conn)` — apaga todo o gêmeo, devolve os eventos não rejeitados a `pendente` e roda `processar_pendentes`.

Regras:
- **Atomicidade:** aplicar um evento ao gêmeo e marcá-lo `processado` acontece numa transação. Se algo falhar no meio, o evento continua `pendente` e o gêmeo não muda.
- **Dois tipos de falha, tratados de forma diferente:** (a) erro de domínio ligado ao evento (`EventoInvalido`, por exemplo exercício que sumiu do catálogo depois da ingestão) marca o evento `rejeitado` com o motivo, de forma permanente, e o lote segue; reconstruções e reprocessamentos não reaplicam eventos rejeitados. (b) Qualquer outra exceção (bug, banco indisponível) desfaz a transação daquele evento, ele continua `pendente` e a exceção sobe: não se engole erro inesperado.
- **Evento atrasado:** se a chave `(occurred_at, event_id)` de um pendente é menor que `(ultimo_evento_em, ultimo_evento_id)` do aluno (a comparação usa a chave completa, para tratar empate de horário), aplicá-lo "em cima" daria um Elo diferente do correto (o Elo depende da ordem). O pipeline então chama `reconstruir_aluno` para esse aluno. Propriedade verificável: processar os mesmos eventos em qualquer ordem de chegada resulta no mesmo gêmeo que processá-los em ordem.
- **Idempotência:** duplicado nunca entra (`event_id` único); reprocessar nunca duplica efeito.
- **Igualdade exata:** "mesmo estado" significa valores idênticos, não aproximados. Os mesmos cálculos, na mesma ordem, dão os mesmos `float`s, e o SQLite guarda `REAL` em 64 bits sem perda; nada é arredondado ao gravar. Os testes comparam com igualdade exata.

## 7. Gêmeo digital: cálculos

Constantes nomeadas no módulo dono, valores abaixo são o ponto de partida (o construtor pode ajustar, mantendo as propriedades da seção 9).

**Proficiência por tópico — Elo** (`gemeo/elo.py`). Rating inicial 1000 por aluno×tópico, criado na primeira resposta. Dificuldade `d ∈ 1..5` do exercício vira rating `800 + 100·(d−1)` (800 a 1200), fixo (não evolui). Expectativa de acerto `E = 1 / (1 + 10^((rating_exercicio − rating_aluno) / 400))`. A cada `exercicio_respondido`: `rating_aluno += K · (resultado − E)` com `resultado = 1` se acertou, `0` se errou, `K = 32`. O tempo gasto **não** entra na proficiência.

**Velocidade média** (`gemeo/atualizacao.py`): média móvel exponencial (α = 0,2) de `tempo_gasto_s`, só em `exercicio_respondido`, por aluno. Primeiro valor = o próprio tempo.

**Sinais de evasão**, atualizados por evento:
- `taxa_abandono`: média móvel exponencial (α = 0,2, inicial 0) de um indicador (1 em `exercicio_abandonado`, 0 em `exercicio_respondido`).
- `erros_seguidos`: contador, zera ao acertar, sobe ao errar.
- `desempenho_relativo`: média móvel exponencial (α = 0,2, inicial 0) de `resultado − E` por resposta (positivo = indo melhor que o esperado).
- `ultimo_evento_em`: atualizado por qualquer tipo de evento (o maior `occurred_at` visto para o aluno). `exercicio_iniciado` só atualiza esse campo (e cria a linha de `gemeo_aluno` se for o primeiro evento do aluno).
- `exercicio_abandonado` só mexe em `taxa_abandono` e `ultimo_evento_em`: não conta como erro (`erros_seguidos` e `desempenho_relativo` ficam como estavam) e não incrementa `respostas`, que conta apenas respostas.

**Probabilidade de evasão — calculada na leitura** (`gemeo/evasao.py`, função pura `probabilidade_evasao(estado_aluno, agora)`). Logística (sigmoide) sobre: `taxa_abandono` (+), `erros_seguidos` limitado a 5 (+), `desempenho_relativo` (−) e dias de inatividade `agora − ultimo_evento_em` limitado a 14 (+). Pesos em constantes nomeadas. `agora` vem de um relógio injetado (um `Callable[[], datetime]` passado à API), nunca de `datetime.now()` espalhado, para o teste ser determinístico. O motivo: o sinal mais forte de evasão (o aluno sumir) não gera evento, então esse valor não pode ser gravado na hora do evento.

Propriedades obrigatórias (testáveis): a probabilidade cresce com mais inatividade, mais abandono e mais erros seguidos, e cai com melhor desempenho relativo; fica em (0, 1). Com os pesos escolhidos, um aluno ativo, que acerta e não abandona, fica abaixo de 0,3; um aluno com muita inatividade, abandonos e erros fica acima de 0,7.

## 8. Recomendação e API

**Regra** (`recomendacao/escolher.py`, pura):
1. Tópico: o de menor rating do aluno; tópico ainda não tentado conta com o rating inicial (1000); empate vai para a ordem do catálogo. Só entram tópicos que ainda têm exercício não resolvido; se o aluno resolveu tudo, a resposta traz `exercicio: null` e motivo explicando. "Resolvido" significa "acertou pelo menos uma vez" (`acertou_alguma_vez`). O tópico mais fraco é escolhido mesmo que o que resta nele seja difícil: a regra é essa, de propósito.
2. Exercício: entre os do tópico que o aluno ainda não acertou, o que tem expectativa de acerto mais próxima do alvo; empate vai para o menor `id`.
3. Alvo: 0,70. Se a probabilidade de evasão passa de 0,60, o alvo sobe para 0,85 (exercício mais fácil para recuperar a confiança).
4. A resposta traz `motivo` em texto (ex.: "tópico mais fraco; risco de evasão alto, exercício mais fácil").

**API (FastAPI)** — só leitura, `create_app(db_path, agora)`:
- `GET /alunos/{student_id}/recomendacao` → `{student_id, topico, exercicio: {id, enunciado, dificuldade} | null, expectativa_acerto, probabilidade_evasao, motivo}`.
- `GET /alunos/{student_id}/gemeo` → ratings por tópico (com tentativas e acertos), velocidade média, probabilidade de evasão (calculada na hora), `ultimo_evento_em`.
- `GET /saude` → API e banco respondem.
- Aluno sem linha em `gemeo_aluno` (nenhum evento processado): `404`. Aluno que só tem `exercicio_iniciado` processados existe: `/gemeo` responde `200` com lista de ratings vazia e `/recomendacao` trata todos os tópicos como não tentados.
- A API recebe o relógio por `create_app(db_path, agora)`; o padrão é o relógio real (UTC). Para a demo, `uvicorn` lê a variável de ambiente `GEMEO_AGORA` (ISO 8601 UTC) que, se definida, fixa o relógio.
- Contratos de resposta em Pydantic (`modelos.py`).

## 9. Simulador

`ingestao/simulador.py`: função pura `simular(semente, n_alunos, inicio, dias, defeitos=False) -> Simulacao`, que devolve os eventos (dicionários) e as habilidades verdadeiras finais. Sem banco, sem relógio real: o tempo é simulado (`occurred_at` ao longo de `dias`, sem esperar).

- **Perfis:** `dedicado`, `irregular`, `desistente`. Cada aluno tem uma habilidade verdadeira por tópico (mesma escala do Elo, escondida do sistema) que **cresce devagar com a prática**.
- **Resposta:** probabilidade de acertar = expectativa do Elo (habilidade verdadeira contra rating do exercício) mais pequeno ruído. Tempo gasto depende do perfil e da dificuldade. Chance de abandonar um exercício depende do perfil.
- **Sessões:** `dedicado` estuda com frequência regular; `irregular` tem lacunas longas; `desistente` para de gerar eventos depois de certo ponto do período (produz o caso de evasão).
- **Semente fixa:** mesma semente e mesmos parâmetros geram exatamente os mesmos eventos.
- **Janela de tempo:** `inicio` é parâmetro obrigatório da função (puro, sem relógio real). Na CLI, o padrão é `inicio = agora − dias`, de modo que a simulação termina "agora" e a demo com relógio real mostra o `dedicado` ativo e o `desistente` sumido (inatividade alta). `--inicio` permite fixar a data, e junto com `GEMEO_AGORA` torna a demo e o README reproduzíveis.
- **Desempate de horários:** o simulador gera `event_id` únicos e não precisa evitar horários repetidos; o pipeline já desempata por `event_id`.
- **`defeitos=True`** (desligado por padrão): reenvia alguns eventos (duplicados), embaralha a ordem de alguns dentro de uma janela e inclui alguns eventos malformados, para exercitar idempotência, ordenação e rejeição.

CLI: `python -m ingestao.simular --semente 42 --alunos 12 --dias 42 [--defeitos] [--db data/gemeo.db]` grava via `ingestao.receber` e imprime um resumo (aceitos, duplicados, rejeitados). `python -m pipeline.executar [--reprocessar] [--db ...]` processa e imprime o resumo. API: `uvicorn api.main:app`.

## 10. Catálogo

Seed próprio do projeto: 4 tópicos de álgebra (por exemplo `funcoes`, `equacao_1_grau`, `equacao_2_grau`, `sistemas_lineares`) × 3 a 4 exercícios cada, dificuldade 1 a 5, enunciados em português do Brasil. Criado e populado automaticamente na primeira execução, de forma idempotente.

## 11. Testes

`pytest`, enxutos e por camada, com relógio injetado e semente fixa. Cobertura exigida:
- `elo`: fórmula (valores conferidos à mão), acerto em exercício difícil sobe mais que em fácil.
- `evasao`: as propriedades de monotonicidade e os dois limites da seção 7.
- `atualizacao`: cada tipo de evento atualiza só o que deve.
- `pipeline` (SQLite temporário): duplicado ignorado; **ordem de chegada embaralhada dá o mesmo gêmeo que ordem cronológica** (evento atrasado); falha no meio de um evento deixa o evento `pendente` e o gêmeo intacto; `reprocessar_tudo` reproduz exatamente o estado incremental; evento rejeitado não derruba o lote.
- `ingestao`: validação (fuso ausente, `tempo_gasto_s <= 0`, topic divergente do catálogo, exercício inexistente, payload errado para o tipo).
- `simulador`: mesma semente, mesmos eventos; **correlação de postos (Spearman) entre habilidade verdadeira e rating Elo final, por tópico, acima de um limiar** (mostra que o gêmeo converge).
- `recomendacao`: determinística; alvo sobe com evasão alta; tudo resolvido → `null`.
- `api` (`TestClient`): 404 para aluno desconhecido; formato das respostas; API usa conexão somente leitura (tentar escrever falha).
- `arquitetura`: o teste via `ast` da seção 3.

## 12. Ferramentas e entregáveis

- Python 3.10; `.venv` com `uv venv`; `requirements.txt` (`pydantic`, `fastapi`, `uvicorn`), `requirements-dev.txt` (`-r requirements.txt`, `pytest`, `httpx`); `pytest.ini`; `.gitignore` (`data/*.db`, `.venv/`, `.superpowers/`, caches).
- `README.md` em português: o que é, diagrama do fluxo, como rodar (simular → processar → API), tabela do modelo de dados, comparação "habilidade verdadeira × Elo estimado" gerada pelo simulador, e a seção "Evoluções possíveis" (broker de mensagens, BKT, dificuldade que evolui, modelo treinado com dados reais, ponte com o assistente da PoC 1).
- `CLAUDE.md` do projeto: regra de dependência, decisões que não se mudam sem conversar, comandos.
- Registro do processo versionado em `docs/superpowers/` (spec, plano, e o registro do fluxo de execução com subagentes), como na PoC 1.
- Idioma: interface, dados do seed e mensagens em português do Brasil; contratos entre camadas em Pydantic, nunca dicionários soltos (o simulador emite dicionários de propósito, porque imita um produtor externo; a ingestão os converte).

## 13. O que é escolha do construtor

Valores exatos de pesos da evasão (respeitando as propriedades), parâmetros dos perfis do simulador (frequência de sessão, taxas de abandono, ganho de habilidade, ruído, tempos), o limiar de correlação do teste do simulador (deve ser alto o bastante para falhar se o Elo estiver quebrado), texto dos enunciados do seed, nomes internos de funções auxiliares, formato do resumo impresso pelas CLIs.

## 14. Escolhas minhas (não discutidas com o Igor; conferir)

Estrutura de pastas e tabelas da seção 5, incluindo `gemeo_exercicio`; reconstrução do aluno no evento atrasado; `eventos_brutos` guardar também os rejeitados; validação toda na ingestão; modo WAL e API somente leitura; endpoints e formato das respostas; α = 0,2 das médias móveis e K = 32; limiar de evasão 0,60 e alvos 0,70/0,85; `desempenho_relativo` como sinal de tendência; nomes dos três tópicos e do catálogo; `desistente` parando no meio do período.

Resolvidas depois da leitura de um revisor independente (também escolhas minhas): ordem de processamento `(occurred_at, event_id)` em vez de `seq`, para o resultado não depender da ordem de chegada; erro de domínio rejeita de forma permanente, qualquer outra exceção deixa o evento pendente e sobe; abandono não conta como erro nem como resposta; aluno só com `exercicio_iniciado` existe (200, ratings vazios); reenvio de evento rejeitado com o mesmo `event_id` é ignorado; CLIs em `ingestao/simular.py` e `pipeline/executar.py` (sem `__main__`); o recomendador é puro e a API faz a leitura; igualdade exata nos testes de reprocessamento; relógio da demo fixável por `GEMEO_AGORA` e simulação terminando "agora" por padrão; "resolvido" = acertou ao menos uma vez.
