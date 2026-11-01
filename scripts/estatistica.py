"""Estatística à mão (sem numpy/scipy) para os scripts e testes."""
import math
from collections.abc import Sequence


def _postos(valores: Sequence[float]) -> list[float]:
    """Postos 1..n; valores empatados recebem a média dos postos que ocupam."""
    ordem = sorted(range(len(valores)), key=lambda i: valores[i])
    postos = [0.0] * len(valores)
    i = 0
    while i < len(ordem):
        j = i
        while j + 1 < len(ordem) and valores[ordem[j + 1]] == valores[ordem[i]]:
            j += 1
        medio = (i + j) / 2 + 1
        for k in range(i, j + 1):
            postos[ordem[k]] = medio
        i = j + 1
    return postos


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Correlação de Spearman: Pearson dos postos, com postos médios nos empates."""
    if len(xs) != len(ys):
        raise ValueError("as duas series precisam ter o mesmo tamanho")
    if len(xs) < 2:
        raise ValueError("a correlacao precisa de ao menos 2 pontos")
    rx, ry = _postos(xs), _postos(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var_x = sum((a - mx) ** 2 for a in rx)
    var_y = sum((b - my) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        raise ValueError("serie constante: correlacao indefinida")
    return cov / math.sqrt(var_x * var_y)
