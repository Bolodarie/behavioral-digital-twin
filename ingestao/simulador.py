"""Simulador de eventos de alunos (design, seção 9). Função pura.

Sem banco, sem arquivo e sem relógio real: o tempo é simulado a partir de
`inicio`. Mesma semente e mesmos argumentos geram exatamente os mesmos eventos,
inclusive os `event_id` (UUIDs sorteados da própria semente).

A escala do Elo é reimplementada aqui de propósito: o processo que gera os
dados não pode depender do estimador (`gemeo.elo`). O teste
`test_escala_igual_a_do_elo` garante que as duas não divergem.

Todos os eventos válidos saem de um único fluxo `random.Random(semente)`.
Qualquer aleatoriedade extra (por exemplo, defeitos nos dados) deve usar outro
fluxo, para nunca alterar os eventos válidos.
"""
import copy
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from catalogo import EXERCICIOS, TOPICO_IDS, ExercicioCatalogo

PERFIS = ("dedicado", "irregular", "desistente")

ESCALA = 400.0
RUIDO_ACERTO = 0.05
PROB_MIN, PROB_MAX = 0.02, 0.98
GANHO_POR_RESPOSTA = 2.0  # pontos de habilidade por exercício respondido

# Por perfil: chance de estudar num dia ativo, exercícios por dia, chance de
# abandonar um exercício e fator multiplicador do tempo gasto.
_PROB_DIA_ATIVO = {"dedicado": 0.85, "desistente": 0.8}
_EXERCICIOS_POR_DIA = {"dedicado": (3, 6), "irregular": (2, 4), "desistente": (2, 5)}
_PROB_ABANDONO = {"dedicado": 0.05, "irregular": 0.15, "desistente": 0.40}
_FATOR_TEMPO = {"dedicado": 0.9, "irregular": 1.1, "desistente": 1.3}
_FRACAO_DESISTENTE = 0.4  # para de estudar depois de 40% do período
_SESSAO_IRREGULAR = (1, 2)  # dias seguidos de estudo
_LACUNA_IRREGULAR = (4, 7)  # dias seguidos sem estudar


@dataclass(frozen=True)
class Simulacao:
    eventos: list[dict]
    habilidades_iniciais: dict[str, dict[str, float]]
    habilidades_finais: dict[str, dict[str, float]]
    perfis: dict[str, str]


def rating_do_exercicio(dificuldade: int) -> float:
    """Rating 800..1200 de um exercício de dificuldade 1..5."""
    if not 1 <= dificuldade <= 5:
        raise ValueError(f"dificuldade fora de 1..5: {dificuldade}")
    return 800.0 + 100.0 * (dificuldade - 1)


def probabilidade_base(habilidade: float, rating_exercicio: float) -> float:
    """Chance de acerto sem ruído: habilidade verdadeira contra o exercício."""
    return 1.0 / (1.0 + 10 ** ((rating_exercicio - habilidade) / ESCALA))


def _texto(instante: datetime) -> str:
    return instante.strftime("%Y-%m-%dT%H:%M:%SZ")


def _novo_id(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _dias_de_estudo(perfil: str, dias: int, rng: random.Random) -> list[int]:
    """Índices dos dias (0..dias-1) em que o aluno estuda."""
    if perfil == "dedicado":
        return [d for d in range(dias) if rng.random() < _PROB_DIA_ATIVO[perfil]]
    if perfil == "desistente":
        limite = int(dias * _FRACAO_DESISTENTE)
        return [d for d in range(limite) if rng.random() < _PROB_DIA_ATIVO[perfil]]
    ativos: list[int] = []
    dia = rng.randint(0, 2)
    while dia < dias:
        sessao = rng.randint(*_SESSAO_IRREGULAR)
        ativos.extend(d for d in range(dia, dia + sessao) if d < dias)
        dia += sessao + rng.randint(*_LACUNA_IRREGULAR)
    return ativos


def _escolher_exercicio(habilidades: dict[str, float], rng: random.Random) -> ExercicioCatalogo:
    """Sorteia um tópico e, nele, um exercício perto do nível atual do aluno."""
    topico = rng.choice(TOPICO_IDS)
    candidatos = [e for e in EXERCICIOS if e.topico_id == topico]
    pesos = [
        1.0 / (1.0 + ((rating_do_exercicio(e.dificuldade) - habilidades[topico]) / 150.0) ** 2)
        for e in candidatos
    ]
    return rng.choices(candidatos, weights=pesos, k=1)[0]


def _evento(
    rng: random.Random,
    aluno: str,
    exercicio: ExercicioCatalogo,
    tipo: str,
    instante: datetime,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_id": _novo_id(rng),
        "student_id": aluno,
        "exercise_id": exercicio.id,
        "topic": exercicio.topico_id,
        "event_type": tipo,
        "occurred_at": _texto(instante),
        "payload": payload,
    }


def _simular_aluno(
    rng: random.Random,
    aluno: str,
    perfil: str,
    habilidades: dict[str, float],
    inicio: datetime,
    dias: int,
) -> list[dict[str, Any]]:
    """Gera os eventos de um aluno e atualiza `habilidades` (que só crescem)."""
    eventos: list[dict[str, Any]] = []
    for dia in _dias_de_estudo(perfil, dias, rng):
        instante = inicio + timedelta(days=dia, seconds=8 * 3600 + rng.randint(0, 10 * 3600))
        for _ in range(rng.randint(*_EXERCICIOS_POR_DIA[perfil])):
            exercicio = _escolher_exercicio(habilidades, rng)
            eventos.append(_evento(rng, aluno, exercicio, "exercicio_iniciado", instante, {}))
            base = (45 + 45 * exercicio.dificuldade) * _FATOR_TEMPO[perfil]
            if rng.random() < _PROB_ABANDONO[perfil]:
                duracao = max(1, int(base * rng.uniform(0.1, 0.5)))
                instante += timedelta(seconds=duracao)
                eventos.append(_evento(rng, aluno, exercicio, "exercicio_abandonado", instante, {}))
            else:
                duracao = max(1, int(base * rng.uniform(0.6, 1.6)))
                instante += timedelta(seconds=duracao)
                p = probabilidade_base(
                    habilidades[exercicio.topico_id], rating_do_exercicio(exercicio.dificuldade)
                )
                p = min(PROB_MAX, max(PROB_MIN, p + rng.uniform(-RUIDO_ACERTO, RUIDO_ACERTO)))
                payload = {"acertou": rng.random() < p, "tempo_gasto_s": duracao}
                eventos.append(
                    _evento(rng, aluno, exercicio, "exercicio_respondido", instante, payload)
                )
                habilidades[exercicio.topico_id] += GANHO_POR_RESPOSTA
            instante += timedelta(seconds=rng.randint(5, 60))
    return eventos


# Defeitos (pós-processamento sobre a lista válida, com fluxo próprio de sorteio).
_FRACAO_DUPLICADOS = 0.05
_JANELA_DESORDEM = 20  # eventos por janela embaralhável
_PROB_JANELA_EMBARALHADA = 0.25
_MALFORMADOS_POR_TIPO = 2


def _malformado(tipo: str, id_novo: str, instante: str) -> dict[str, Any]:
    """Evento quebrado de um jeito específico, com `event_id` que não colide."""
    dado = {
        "event_id": id_novo,
        "student_id": "aluno-001",
        "exercise_id": EXERCICIOS[0].id,
        "topic": EXERCICIOS[0].topico_id,
        "event_type": "exercicio_respondido",
        "occurred_at": instante,
        "payload": {"acertou": True, "tempo_gasto_s": 60},
    }
    if tipo == "sem_fuso":
        dado["occurred_at"] = instante.removesuffix("Z")
    elif tipo == "tempo_zero":
        dado["payload"] = {"acertou": True, "tempo_gasto_s": 0}
    elif tipo == "acertou_texto":
        dado["payload"] = {"acertou": "sim", "tempo_gasto_s": 60}
    elif tipo == "sem_event_id":
        del dado["event_id"]
    elif tipo == "exercicio_inexistente":
        dado["exercise_id"] = "inexistente-99"
    else:
        raise ValueError(f"tipo de defeito desconhecido: {tipo}")
    return dado


_TIPOS_MALFORMADOS = (
    "sem_fuso",
    "tempo_zero",
    "acertou_texto",
    "sem_event_id",
    "exercicio_inexistente",
)


def _aplicar_defeitos(
    validos: list[dict[str, Any]], semente: int, inicio: datetime
) -> list[dict[str, Any]]:
    """Devolve a lista como um produtor com defeitos a enviaria ("ordem de chegada").

    Os eventos válidos não são alterados: só ganham cópias (duplicados), mudam de
    posição dentro de janelas e recebem, entre eles, eventos malformados. Todo
    sorteio vem de um fluxo derivado da semente, separado do dos eventos válidos.
    """
    rng = random.Random(f"defeitos-{semente}")
    chegada = list(validos)

    if chegada:  # duplicados: o mesmo dict reenviado logo depois do original
        n_dup = max(1, round(len(validos) * _FRACAO_DUPLICADOS))
        for i in sorted(rng.sample(range(len(validos)), min(n_dup, len(validos))), reverse=True):
            chegada.insert(rng.randint(i + 1, len(chegada)), copy.deepcopy(validos[i]))

    for ini in range(0, len(chegada), _JANELA_DESORDEM):  # desordem dentro de janelas
        if rng.random() < _PROB_JANELA_EMBARALHADA:
            janela = chegada[ini : ini + _JANELA_DESORDEM]
            rng.shuffle(janela)
            chegada[ini : ini + _JANELA_DESORDEM] = janela
    primeira: dict[str, int] = {}  # posição da 1ª chegada de cada event_id
    for pos, e in enumerate(chegada):
        primeira.setdefault(e["event_id"], pos)
    if len(validos) > 1 and sorted(primeira, key=primeira.get) == [
        e["event_id"] for e in validos
    ]:
        # nenhuma janela mudou a ordem: troca as duas primeiras chegadas (garantia)
        a, b = sorted(primeira.values())[:2]
        chegada[a], chegada[b] = chegada[b], chegada[a]

    instante = _texto(inicio)
    for tipo in _TIPOS_MALFORMADOS:
        for _ in range(_MALFORMADOS_POR_TIPO):
            dado = _malformado(tipo, _novo_id(rng), instante)
            chegada.insert(rng.randint(0, len(chegada)), dado)
    return chegada


def simular(
    semente: int, n_alunos: int, inicio: datetime, dias: int, defeitos: bool = False
) -> Simulacao:
    """Simula `n_alunos` alunos ao longo de `dias` dias a partir de `inicio`.

    Com `defeitos=True`, `eventos` sai como um produtor imperfeito o enviaria
    (duplicados, ordem embaralhada e malformados); os eventos válidos são os mesmos.
    """
    if inicio.tzinfo is None or inicio.utcoffset() is None:
        raise ValueError("inicio precisa ter fuso horário")
    if n_alunos < 1:
        raise ValueError("n_alunos deve ser >= 1")
    if dias < 1:
        raise ValueError("dias deve ser >= 1")

    inicio = inicio.astimezone(timezone.utc).replace(microsecond=0)
    rng = random.Random(semente)  # único fluxo dos eventos válidos
    eventos: list[dict[str, Any]] = []
    iniciais: dict[str, dict[str, float]] = {}
    finais: dict[str, dict[str, float]] = {}
    perfis: dict[str, str] = {}

    for i in range(n_alunos):
        aluno = f"aluno-{i + 1:03d}"
        perfil = PERFIS[i % len(PERFIS)]
        nivel = rng.uniform(850.0, 1050.0)
        habilidades = {t: nivel + rng.uniform(-60.0, 60.0) for t in TOPICO_IDS}
        perfis[aluno] = perfil
        iniciais[aluno] = dict(habilidades)
        eventos.extend(_simular_aluno(rng, aluno, perfil, habilidades, inicio, dias))
        finais[aluno] = habilidades

    eventos.sort(key=lambda e: (e["occurred_at"], e["event_id"]))
    if defeitos:
        eventos = _aplicar_defeitos(eventos, semente, inicio)
    return Simulacao(
        eventos=eventos,
        habilidades_iniciais=iniciais,
        habilidades_finais=finais,
        perfis=perfis,
    )
