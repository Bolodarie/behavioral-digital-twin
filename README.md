# behavioral-digital-twin

Pipeline de dados que transforma eventos de interação de alunos de álgebra (cursinho popular) em um **gêmeo digital** do aluno: um estado por aluno, atualizado a cada evento, que alimenta uma API que recomenda o próximo exercício.

É uma PoC de portfólio. O foco é **engenharia de dados e desenho de back-end** (fluxo da informação, idempotência, ordenação, evento atrasado, reprocessamento, separação de camadas), não um produto. Python 3.10, SQLite, Pydantic v2 e FastAPI; nada além disso.

A ideia central: a tabela de **eventos brutos é a fonte da verdade**, e o gêmeo é só uma consequência dela. Dá para apagar o gêmeo inteiro e reconstruí-lo, e o resultado é exatamente o mesmo, até o último bit dos números decimais.

Projeto separado da PoC `edu-agent-orchestrator` (assistente de chat de álgebra, repositório próprio). Uma ponte entre os dois está só nas [evoluções possíveis](#evoluções-possíveis).

Design completo: [`docs/superpowers/specs/2026-10-31-behavioral-digital-twin-design.md`](docs/superpowers/specs/2026-10-31-behavioral-digital-twin-design.md). Plano de implementação: [`docs/superpowers/plans/`](docs/superpowers/plans/).

## Fluxo

```
simulador ──► ingestao ──► eventos_brutos ──► pipeline ──► gemeo (SQLite) ──► api ──► recomendacao
 (gera)       (valida,      (só inserção,     (consome     (estado por       (lê)    (escolhe o
              grava)         com status)       pendentes)   aluno e tópico)           próximo exercício)
```

1. **Ingestão.** O simulador gera eventos como dicionários (imita um produtor externo). `ingestao.receber` valida e grava em `eventos_brutos` com `status = 'pendente'`. Evento com `event_id` repetido é ignorado; evento inválido é gravado como `rejeitado`, com o motivo.
2. **Processamento.** O pipeline lê os pendentes em ordem `(occurred_at, event_id)`, aplica cada um ao gêmeo e marca como `processado`, na mesma transação.
3. **Gêmeo.** Estado por aluno, por aluno×tópico e por aluno×exercício.
4. **Recomendação.** A API lê o gêmeo (somente leitura) e devolve o próximo exercício, com o motivo.

## Como rodar

Precisa de Python 3.10.

```bash
pip install -r requirements-dev.txt   # para só rodar a API basta o requirements.txt
pytest
```

O banco fica em `data/gemeo.db` (criado na primeira execução, já com o catálogo; não é versionado). Para usar outro arquivo, passe `--db` nos dois comandos de linha de comando e `GEMEO_DB` na API.

### 1. Simular e ingerir

```bash
python -m ingestao.simular --semente 42 --alunos 12 --dias 42 --inicio 2026-01-05T00:00:00Z --defeitos
```

```
aceitos: 1828
duplicados: 91
rejeitados: 10
```

`--defeitos` faz o simulador agir como um produtor imperfeito: reenvia eventos (duplicados), embaralha a ordem de chegada dentro de janelas e inclui 10 eventos malformados (2 de cada tipo: sem fuso horário, `tempo_gasto_s` zero, `acertou` como texto, sem `event_id`, exercício inexistente). Sem `--inicio`, a simulação termina "agora" (começa em `agora − dias`). Rodar de novo com os mesmos argumentos não duplica nada no gêmeo: os `event_id` saem da semente, então os eventos voltam como `duplicado` (os 2 sem `event_id` não têm como ser reconhecidos e são rejeitados de novo, ganhando novas linhas em `eventos_brutos`).

### 2. Processar

```bash
python -m pipeline.executar
```

```
processados: 1828
rejeitados: 0
alunos_reconstruidos: 0
```

Os 1828 eventos aceitos viram `processado`; os 10 inválidos continuam `rejeitado`, com o motivo. Rodar de novo não faz nada (`processados: 0`). `python -m pipeline.executar --reprocessar` apaga o gêmeo e reaplica tudo, e chega ao mesmo estado.

`alunos_reconstruidos` é 0 aqui porque todos os eventos chegaram antes do primeiro processamento: o pipeline já os lê em ordem cronológica, então a desordem de chegada não importa. A reconstrução só acontece quando um evento atrasado chega **depois** de o aluno já ter sido processado até um evento mais novo (ver [Pipeline](#pipeline-duplicado-atrasado-rejeitado-e-reprocessamento)).

### 3. Consultar a API

A demo fixa o relógio da API em `GEMEO_AGORA`, para a saída ser reproduzível. Sem ela, vale o relógio real (UTC) e, como os eventos simulados são de janeiro de 2026, todo mundo apareceria inativo há muito tempo.

```bash
GEMEO_AGORA=2026-02-16T00:00:00Z uvicorn api.main:app
```

Em outro terminal (`aluno-001` é `dedicado` e `aluno-003` é `desistente`; os perfis se alternam na ordem dos ids):

```bash
curl -s localhost:8000/saude
curl -s localhost:8000/alunos/aluno-001/gemeo | python -m json.tool --no-ensure-ascii
curl -s localhost:8000/alunos/aluno-003/recomendacao | python -m json.tool --no-ensure-ascii
```

```json
{"status":"ok"}
```

```json
{
    "student_id": "aluno-001",
    "ultimo_evento_em": "2026-02-15T09:18:21Z",
    "velocidade_media_s": 171.18928330984423,
    "probabilidade_evasao": 0.09324008771734077,
    "topicos": [
        {
            "topic_id": "equacao_1_grau",
            "rating_elo": 1032.4790537309045,
            "tentativas": 40,
            "acertos": 25
        },
        {
            "topic_id": "equacao_2_grau",
            "rating_elo": 961.9531700704651,
            "tentativas": 28,
            "acertos": 13
        },
        {
            "topic_id": "funcoes",
            "rating_elo": 1054.8343849440976,
            "tentativas": 38,
            "acertos": 24
        },
        {
            "topic_id": "sistemas_lineares",
            "rating_elo": 1032.2595816630076,
            "tentativas": 55,
            "acertos": 34
        }
    ]
}
```

```json
{
    "student_id": "aluno-003",
    "topico": "equacao_2_grau",
    "exercicio": {
        "id": "equacao_2_grau-1",
        "enunciado": "Resolva x² − 9 = 0.",
        "dificuldade": 1
    },
    "expectativa_acerto": 0.6756827075564164,
    "probabilidade_evasao": 0.8844192391204907,
    "motivo": "tópico mais fraco; risco de evasão alto, exercício mais fácil (cerca de 85% de chance de acerto)"
}
```

O `aluno-003` parou de estudar em 2026-01-20, mais de 26 dias antes do "agora" da demo: a probabilidade de evasão é 0,88, passa do limiar de 0,60 e o alvo sobe de 70% para 85% de chance de acerto. O rating dele em `equacao_2_grau` é 927,5, então nem o exercício mais fácil do catálogo (rating 800) chega a 85%: a expectativa é 0,68, a mais alta possível ali.

Outros resultados reais da mesma base: `/alunos/aluno-001/recomendacao` devolve `equacao_1_grau-4` (dificuldade 5, expectativa 0,28), porque o aluno já acertou 15 dos 16 exercícios do catálogo e esse é o único que falta; `/alunos/aluno-999/gemeo` responde `404` com `{"detail":"aluno nao encontrado"}`.

Se não for possível abrir porta ou usar `curl`, a mesma saída sai de `fastapi.testclient.TestClient(create_app(db_path, agora=...))`, que é como `tests/test_api.py` e `tests/test_ponta_a_ponta.py` chamam a API.

## Camadas e regra de dependência

```
behavioral-digital-twin/
├── modelos.py            # contratos Pydantic (Evento, estados, Recomendacao, respostas da API)
├── db.py                 # schema, abrir conexão (escrita e somente leitura), DEFAULT_DB_PATH
├── catalogo/             # 4 tópicos × 4 exercícios, só dados
├── ingestao/             # simulador.py, receber.py, simular.py (CLI)
├── pipeline/             # fila.py (SQL dos eventos), consumidor.py, executar.py (CLI)
├── gemeo/                # elo.py, evasao.py, atualizacao.py (puros), repositorio.py (SQL)
├── recomendacao/         # escolher.py (puro)
├── api/                  # main.py (FastAPI, só leitura)
├── scripts/              # comparar_habilidades.py
└── tests/
```

`X ──► Y` quer dizer que X pode importar Y:

```
ingestao     ──► modelos, db, catalogo
pipeline     ──► gemeo, modelos, db, catalogo
gemeo        ──► modelos, db, catalogo
recomendacao ──► gemeo (só módulos puros: elo, evasao), modelos, catalogo
api          ──► recomendacao, gemeo, modelos, db
db           ──► catalogo
catalogo, modelos ──► (nada do projeto)
```

Em particular: a ingestão não conhece o gêmeo (o simulador reimplementa a escala do Elo de propósito, para o gerador dos dados ser independente do estimador; um teste confere que as duas não divergem); o recomendador nunca importa `gemeo.repositorio` (quem lê o banco e chama o recomendador é a API); a API não importa `ingestao` nem `pipeline`, então **não tem como disparar processamento**: é só leitura.

A regra é verificada por `tests/test_arquitetura.py`, que lê os arquivos com `ast` (inclusive `importlib.import_module` e `__import__`) e falha se uma fronteira for cruzada. `tests/` e `scripts/` ficam de fora porque compõem camadas.

A lógica de domínio (`elo`, `evasao`, `atualizacao`, `recomendacao/escolher`) é pura: recebe estado e evento e devolve novo estado, sem SQL e sem relógio. Só `gemeo/repositorio.py`, `ingestao/receber.py` e `pipeline/fila.py` falam SQL.

## Modelo de dados

SQLite em modo WAL (a API lê enquanto o pipeline escreve). Pipeline e ingestão usam conexão de escrita; a API usa conexão somente leitura (`mode=ro`). As conexões são abertas em autocommit, com transações explícitas (`BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`). Todo horário é UTC, em texto `YYYY-MM-DDTHH:MM:SSZ` (ordena como texto), com resolução de 1 segundo.

| tabela | colunas | papel |
|---|---|---|
| `topicos` | `id`, `nome` | catálogo |
| `exercicios` | `id`, `topico_id`, `enunciado`, `dificuldade` (1 a 5) | catálogo |
| `eventos_brutos` | `seq`, `event_id` (único, pode ser nulo), `student_id`, `exercise_id`, `topic`, `event_type`, `occurred_at`, `payload_json`, `bruto_json`, `recebido_em`, `status` (`pendente`, `processado`, `rejeitado`), `motivo_rejeicao`, `processado_em` | **fonte da verdade**; guarda também o JSON cru e os rejeitados |
| `gemeo_topico` | `student_id`, `topic_id`, `rating_elo`, `tentativas`, `acertos`, `atualizado_em` | proficiência por aluno×tópico |
| `gemeo_exercicio` | `student_id`, `exercise_id`, `tentativas`, `acertou_alguma_vez` | para a recomendação não repetir o que já foi acertado |
| `gemeo_aluno` | `student_id`, `velocidade_media_s` (pode ser nulo), `taxa_abandono`, `erros_seguidos`, `desempenho_relativo`, `respostas`, `ultimo_evento_em`, `ultimo_evento_id`, `atualizado_em` | sinais por aluno |

`eventos_brutos` só recebe inserções de eventos; depois disso mudam apenas `status`, `motivo_rejeicao` e `processado_em`. O catálogo é fixo: ids `topico-n` (por exemplo `funcoes-1`), com `n` de 1 a 4 e dificuldades 1, 2, 3 e 5; tópicos `funcoes`, `equacao_1_grau`, `equacao_2_grau` e `sistemas_lineares`.

**Evento:** `event_id`, `student_id`, `exercise_id`, `topic`, `event_type` (`exercicio_iniciado`, `exercicio_respondido` ou `exercicio_abandonado`), `occurred_at` e `payload`. `occurred_at` é ISO 8601 com fuso: sem fuso é rejeitado, outros deslocamentos viram UTC e frações de segundo são descartadas. Só `exercicio_respondido` tem payload: `acertou` (booleano de verdade) e `tempo_gasto_s` (inteiro maior que zero), ambos com tipo estrito e sem chaves extras. A ingestão rejeita ainda campos extras, ids vazios, exercício fora do catálogo e `topic` diferente do tópico do exercício. Não se exige `exercicio_iniciado` antes da resposta: produtores reais perdem eventos.

`(ultimo_evento_em, ultimo_evento_id)` é a maior chave `(occurred_at, event_id)` já aplicada ao aluno. `atualizado_em` é sempre igual ao horário do evento, nunca ao relógio real.

## Como o gêmeo é calculado

As constantes ficam nomeadas no módulo que as usa.

**Proficiência por tópico: Elo** (`gemeo/elo.py`). Cada par aluno×tópico começa com rating 1000, criado na primeira resposta. A dificuldade `d` (1 a 5) do exercício vira um rating fixo `800 + 100·(d − 1)` (de 800 a 1200; a dificuldade não evolui). A cada `exercicio_respondido`:

```
E = 1 / (1 + 10^((rating_exercicio − rating_aluno) / 400))
rating_aluno += K · (resultado − E)        # K = 32; resultado = 1 se acertou, 0 se errou
```

Exemplo: aluno 1000 contra exercício de rating 1000 (`E = 0,5`): acertar vale +16 e errar vale −16. Contra exercício de rating 1200 (`E ≈ 0,24`): acertar vale cerca de +24. O tempo gasto **não** entra na proficiência.

**Velocidade média** (`gemeo/atualizacao.py`). Média móvel exponencial de `tempo_gasto_s`, só em `exercicio_respondido`, por aluno. O primeiro valor é o próprio tempo. Todas as médias móveis têm a forma `x_novo = x + ALFA · (alvo − x)` com `ALFA = 0,2`, sempre escrita desse jeito: outra forma algebricamente igual muda os últimos bits, e a igualdade exata depende disso.

**Sinais de evasão**, atualizados por evento:

| campo | regra |
|---|---|
| `taxa_abandono` | média móvel (inicial 0) de um indicador: 1 em `exercicio_abandonado`, 0 em `exercicio_respondido` |
| `erros_seguidos` | contador: sobe ao errar, zera ao acertar |
| `desempenho_relativo` | média móvel (inicial 0) de `resultado − E` por resposta (positivo = indo melhor que o esperado) |
| `respostas` | quantas respostas o aluno deu |
| `ultimo_evento_em` | maior `occurred_at` visto, de qualquer tipo de evento |

`exercicio_iniciado` só atualiza `ultimo_evento_em` (e cria a linha do aluno, se for o primeiro evento dele). `exercicio_abandonado` mexe só em `taxa_abandono` e `ultimo_evento_em`: não conta como erro nem como resposta.

**Probabilidade de evasão** (`gemeo/evasao.py`, função pura `probabilidade_evasao(estado, agora)`): sigmoide de uma soma ponderada.

```
z = −2,0
  + 3,0 · taxa_abandono
  + 1,5 · min(erros_seguidos, 5) / 5
  − 2,0 · desempenho_relativo
  + 3,0 · min(dias_sem_evento, 14) / 14
p = 1 / (1 + e^(−z))
```

`dias_sem_evento` é `agora − ultimo_evento_em` em dias (nunca negativo). A probabilidade cresce com abandono, erros seguidos e inatividade, cai com o desempenho relativo e fica sempre entre 0 e 1. Os pesos foram escolhidos à mão, não ajustados com dados: servem a duas propriedades testadas (aluno ativo que acerta e não abandona fica abaixo de 0,3; aluno com muita inatividade, abandonos e erros fica acima de 0,7).

### O que é guardado × o que é calculado na leitura

Tudo o que muda com um **evento** é guardado: ratings, velocidade, taxa de abandono, erros seguidos, desempenho relativo. A **probabilidade de evasão não é guardada**: é calculada a cada leitura da API, com o relógio injetado (`agora`).

O motivo: o sinal mais forte de evasão (o aluno sumir) não gera evento. Se o valor fosse gravado na hora do evento, um aluno que parou há um mês continuaria com a probabilidade de quando estudou pela última vez. Por isso o que se guarda é o horário do último evento, e a conta do tempo é feita na hora de ler. Efeito bom: o gêmeo gravado nunca depende do relógio, só dos eventos, e o reprocessamento reproduz o estado exato. O relógio só aparece nas bordas (CLIs e `create_app`) e, nos testes, é sempre injetado.

## Recomendação

`recomendacao/escolher.py`, função pura:

1. **Tópico:** o de menor rating do aluno. Tópico ainda não tentado conta com o rating inicial (1000); empate vai para a ordem do catálogo. Só entram tópicos que ainda têm exercício não resolvido ("resolvido" = acertou ao menos uma vez). O tópico mais fraco é escolhido mesmo que o que resta nele seja difícil: a regra é essa, de propósito.
2. **Exercício:** entre os que o aluno ainda não acertou nesse tópico, o de expectativa de acerto (a mesma `E` do Elo) mais próxima do alvo; empate vai para o menor `id`.
3. **Alvo:** 0,70. Se a probabilidade de evasão passa de 0,60, o alvo sobe para 0,85 (exercício mais fácil, para recuperar a confiança).
4. **`motivo`:** texto de duas partes separadas por `; `: a do tópico (`tópico mais fraco` ou `tópico ainda não tentado`) e a do alvo (`exercício com cerca de 70% de chance de acerto` ou `risco de evasão alto, exercício mais fácil (cerca de 85% de chance de acerto)`).
5. Se o aluno já acertou tudo, a resposta traz `topico: null`, `exercicio: null` e o motivo `todos os exercícios do catálogo já foram resolvidos`.

Endpoints (todos `GET`, somente leitura, respostas em Pydantic):

| rota | resposta |
|---|---|
| `/saude` | `{"status": "ok"}` |
| `/alunos/{student_id}/gemeo` | ratings por tópico (com tentativas e acertos), velocidade média, probabilidade de evasão (calculada na hora) e `ultimo_evento_em` |
| `/alunos/{student_id}/recomendacao` | `student_id`, `topico`, `exercicio {id, enunciado, dificuldade}`, `expectativa_acerto`, `probabilidade_evasao`, `motivo` |

Aluno sem nenhum evento processado: `404`. Aluno que só tem `exercicio_iniciado` existe: `/gemeo` responde `200` com a lista de ratings vazia e `/recomendacao` trata todos os tópicos como não tentados. Banco ausente ou que não abre: `503`.

## Pipeline: duplicado, atrasado, rejeitado e reprocessamento

Funções públicas em `pipeline/consumidor.py` (todas recebem a conexão):

- `processar_evento(conn, event_id)`: aplica um evento pendente. Devolve `"processado"`, `"rejeitado"` ou `"ignorado"` (já estava processado ou rejeitado).
- `processar_pendentes(conn)`: o laço do dia a dia; devolve as contagens de processados, rejeitados e alunos reconstruídos.
- `reconstruir_aluno(conn, student_id)`: apaga o gêmeo do aluno e reaplica todos os eventos dele que não estejam `rejeitado`, em ordem `(occurred_at, event_id)`, numa única transação.
- `reprocessar_tudo(conn)`: apaga todo o gêmeo, devolve os eventos não rejeitados a `pendente` e roda `processar_pendentes`.

**Duplicado.** `event_id` é único em `eventos_brutos`: o segundo envio é ignorado na ingestão (contado como `duplicado`) e nunca vira efeito no gêmeo. Reenviar um evento que foi rejeitado, com o mesmo `event_id`, também conta como duplicado: a linha rejeitada fica como está (corrigir o produtor significa mandar um `event_id` novo).

**Ordem.** Os pendentes são processados em ordem `(occurred_at, event_id)`. O desempate é pelo `event_id`, e não pela ordem de chegada (`seq`); é isso que torna o resultado independente da ordem em que os eventos chegaram.

**Atrasado.** O Elo depende da ordem das respostas. Se a chave `(occurred_at, event_id)` de um pendente é menor que `(ultimo_evento_em, ultimo_evento_id)` do aluno (a comparação usa a chave completa, para tratar horário igual), aplicá-lo "em cima" daria um rating diferente do correto. Então o pipeline chama `reconstruir_aluno` para esse aluno e refaz o estado na ordem certa. Isso só acontece quando o atrasado chega depois de um evento mais novo do mesmo aluno já ter sido processado. `processar_evento` isolado, nesse caso, levanta `EventoAtrasado` e deixa o evento pendente; quem trata é `processar_pendentes`.

**Rejeitado.** Há dois tipos de falha, tratados de forma diferente. (a) Erro de domínio ligado ao evento (`EventoInvalido`, por exemplo um exercício que sumiu do catálogo depois da ingestão): desfaz a transação do evento, marca-o `rejeitado` com o motivo, de forma permanente, e o lote segue; reconstruções e reprocessamentos não reaplicam eventos rejeitados. (b) Qualquer outra exceção (bug, banco indisponível): desfaz a transação daquele evento, ele continua `pendente` e a exceção sobe. Erro inesperado não é engolido.

**Atomicidade.** Aplicar um evento ao gêmeo e marcá-lo `processado` é uma transação só. Se algo falha no meio, o evento continua `pendente` e o gêmeo não muda.

**Reprocessamento completo.** `reprocessar_tudo` (CLI: `--reprocessar`) apaga o gêmeo e refaz tudo a partir de `eventos_brutos`.

**Garantia de exatidão.** Os mesmos eventos, em qualquer ordem de chegada, resultam em um gêmeo **idêntico**: mesmos valores, não valores próximos. As mesmas contas na mesma ordem dão os mesmos `float`s de 64 bits; o SQLite guarda `REAL` em 64 bits sem perda; nada é arredondado ao gravar; `atualizado_em` e `ultimo_evento_em` vêm do horário do evento. Os testes (`tests/test_reconstrucao.py` e `tests/test_ponta_a_ponta.py`) comparam com igualdade exata, inclusive o gêmeo gerado com `--defeitos` (duplicados, desordem e malformados) contra o gerado sem defeitos.

## Habilidade verdadeira × Elo estimado

O simulador dá a cada aluno uma habilidade verdadeira por tópico (na mesma escala do Elo, escondida do sistema), que cresce 2 pontos a cada exercício respondido. `python -m scripts.comparar_habilidades` (padrões: semente 42, 12 alunos, 42 dias, início 2026-01-05) simula, ingere num banco temporário, processa e compara com o rating Elo final do gêmeo. Abaixo, só os quatro alunos `dedicado` (os que mais praticam); o script imprime as 48 linhas, de todos os perfis.

```
aluno      perfil      topico             verdadeira       elo tentativas
aluno-001  dedicado    equacao_1_grau         1030.9    1032.5         40
aluno-001  dedicado    equacao_2_grau         1000.7     962.0         28
aluno-001  dedicado    funcoes                 996.9    1054.8         38
aluno-001  dedicado    sistemas_lineares      1116.3    1032.3         55
aluno-004  dedicado    equacao_1_grau         1130.2    1197.1         36
aluno-004  dedicado    equacao_2_grau         1086.7    1140.9         42
aluno-004  dedicado    funcoes                1133.3    1014.4         32
aluno-004  dedicado    sistemas_lineares      1043.8     967.6         34
aluno-007  dedicado    equacao_1_grau          996.1     884.7         26
aluno-007  dedicado    equacao_2_grau          986.5     994.5         39
aluno-007  dedicado    funcoes                1015.4     970.3         43
aluno-007  dedicado    sistemas_lineares      1061.8     993.3         48
aluno-010  dedicado    equacao_1_grau          989.9     934.3         40
aluno-010  dedicado    equacao_2_grau          968.5     952.2         27
aluno-010  dedicado    funcoes                 924.6    1045.9         27
aluno-010  dedicado    sistemas_lineares       979.3     872.9         43
```

E a correlação de postos (Spearman) por tópico, como o script imprime:

```
Spearman por topico (alunos com >= 5 tentativas; minimo de 6 alunos):
  equacao_1_grau     +0.467  (9 alunos)
  equacao_2_grau     +0.345  (10 alunos)
  funcoes            +0.050  (9 alunos)
  sistemas_lineares  +0.467  (10 alunos)
```

**Como ler com honestidade.** O Elo estimado acompanha a habilidade verdadeira, mas com erro grande: nas linhas acima a diferença chega a 100 pontos ou mais, mesmo com 30 a 50 respostas. É esperado: cada resposta é um acerto ou erro sorteado, a habilidade verdadeira muda enquanto o aluno pratica, e o rating Elo é uma estimativa que oscila a cada resposta (com `K = 32` ele nunca fica parado). Cada correlação por tópico vem de 9 ou 10 alunos, e com amostra tão pequena o número varia muito (`funcoes` dá +0,05, praticamente nada, nesta semente). **Esta tabela, sozinha, não prova que o Elo converge.**

A evidência que o projeto assume está em `tests/test_ponta_a_ponta.py`: uma turma de 40 alunos (semente 42, fixa de propósito: o teste é determinístico, não um sorteio que "costuma passar") precisa de correlação agregada dos pares aluno×tópico de pelo menos 0,35 e de pelo menos 0,20 em cada tópico. Medido (semente 42 e 1 a 7, o menor valor), o agregado dá 0,416 e o menor por tópico 0,232; os limiares ficam abaixo disso e acima do que um Elo defeituoso produz (expectativa invertida, dificuldade ignorada, `K` zero ou negativo). Um controle com ratings embaralhados confirma que o limiar agregado não é trivial. Ver também as [limitações](#limitações-conhecidas).

## Limitações conhecidas

- **Reprocessamento completo não é invisível para a API.** `reprocessar_tudo` confirma (commit) o reinício (gêmeo apagado, eventos devolvidos a `pendente`) e depois reaplica os eventos um a um. Enquanto roda, a API pode ver um gêmeo parcial (alunos com estado até certo ponto, outros ainda sem estado, que respondem `404`). Se for interrompido, o gêmeo fica como um prefixo consistente dos eventos e `python -m pipeline.executar` (sem `--reprocessar`) termina o serviço.
- **Uma linha pendente irreconstruível derruba a fila inteira.** Se existir uma linha `pendente` com `payload_json` corrompido (só acontece se alguém inserir na mão, passando por fora da ingestão, que valida tudo), `listar_pendentes` falha para a fila inteira e nada é processado até a linha ser corrigida ou removida. Na reconstrução de um aluno, uma linha assim é marcada `rejeitado` e a reconstrução segue; na lista de pendentes não há esse tratamento.
- **A reconstrução reescreve `processado_em`.** Reaplicar os eventos de um aluno (evento atrasado ou `reconstruir_aluno`) renova o `processado_em` de todos os eventos reaplicados. O estado do gêmeo não é afetado, só esse carimbo.
- **`/saude` só confere que o arquivo abre como SQLite.** Um arquivo SQLite que não é o banco do gêmeo (sem as tabelas) responde `200` em `/saude` e `500` em `/alunos/{id}/gemeo`. Já arquivo ausente ou que não abre responde `503`.
- **Simulação com poucos dias pode não gerar nada.** Com `--dias` muito pequeno o simulador pode gerar zero evento (por exemplo, `--semente 5 --alunos 1 --dias 1`; a CLI imprime `aceitos: 0`). Além disso, o `desistente` só estuda nos primeiros 40% do período, em dias inteiros: com `--dias 2` ou menos ele não gera evento nenhum.
- **Correlação por tópico é ruidosa.** Com cerca de 10 alunos por tópico (12 alunos no total), o Spearman por tópico varia muito. O teste de convergência junta mais alunos (40) e fixa a semente 42.
- **`eventos_brutos` só cresce.** Eventos nunca são apagados nem alterados; depois da inserção só `status`, `motivo_rejeicao` e `processado_em` mudam. Não há rotina de limpeza.
- **Resolução de 1 segundo.** `occurred_at` perde frações de segundo; eventos do mesmo aluno no mesmo segundo são ordenados por `event_id`, não pela ordem em que aconteceram de fato.
- **Um aviso de terceiros na suíte.** `pytest` imprime um aviso de depreciação do Starlette sobre o uso de `httpx` no `TestClient`. Vem das bibliotecas, não deste código, e não afeta o resultado.
- **É uma PoC.** Sem autenticação, sem broker, uma única base SQLite; o catálogo é pequeno e fixo.

## Evoluções possíveis

- **Broker de mensagens** (Kafka, Redis Streams ou similar) no lugar da chamada direta a `receber`: o produtor publica e um consumidor grava em `eventos_brutos`. O resto (idempotência por `event_id`, ordem por `(occurred_at, event_id)`, reconstrução do aluno) já serve para entrega "pelo menos uma vez", em qualquer ordem.
- **Bayesian Knowledge Tracing (BKT)** ou outro modelo de conhecimento no lugar do Elo, mantendo a mesma interface pura de `atualizacao.py`.
- **Dificuldade que evolui:** hoje a dificuldade do exercício é fixa; ela poderia ser reestimada a partir das respostas de todos os alunos (o Elo já é o formato natural para isso).
- **Modelo treinado com dados reais** para a evasão, no lugar dos pesos escolhidos à mão; o simulador ficaria só como ponto de partida e de teste.
- **Ponte com o assistente de chat da PoC `edu-agent-orchestrator`:** o assistente consultaria `/alunos/{id}/gemeo` e `/alunos/{id}/recomendacao` para responder com base no que o aluno já sabe.
- **Reprocessamento sem janela de gêmeo parcial**, por exemplo construindo o novo gêmeo em tabelas à parte e trocando no fim.

## Licença

Ver [`LICENSE`](LICENSE).
