"""Probabilidade de evasão (design, seção 7).

Função pura, calculada na leitura: o sinal mais forte (o aluno sumir) não gera
evento, então o valor não pode ser gravado na hora do evento. Sem banco e sem
relógio: `agora` é parâmetro.
"""

import math
from datetime import datetime

from modelos import EstadoAluno

B0 = -2.0
W_ABANDONO = 3.0
W_ERROS = 1.5
W_DESEMPENHO = -2.0
W_INATIVIDADE = 3.0

TETO_ERROS_SEGUIDOS = 5
TETO_DIAS_INATIVO = 14
SEGUNDOS_POR_DIA = 86400.0


def probabilidade_evasao(estado: EstadoAluno, agora: datetime) -> float:
    """Probabilidade (0 a 1, exclusivo) de o aluno abandonar o curso."""
    dias = max(0.0, (agora - estado.ultimo_evento_em).total_seconds() / SEGUNDOS_POR_DIA)
    z = (
        B0
        + W_ABANDONO * estado.taxa_abandono
        + W_ERROS * (min(estado.erros_seguidos, TETO_ERROS_SEGUIDOS) / TETO_ERROS_SEGUIDOS)
        + W_DESEMPENHO * estado.desempenho_relativo
        + W_INATIVIDADE * (min(dias, TETO_DIAS_INATIVO) / TETO_DIAS_INATIVO)
    )
    return 1.0 / (1.0 + math.exp(-z))
