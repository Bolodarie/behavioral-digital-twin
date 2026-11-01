"""Contratos Pydantic entre as camadas: eventos e estados do gêmeo."""
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

IdTexto = Annotated[str, Field(min_length=1)]


class TipoEvento(str, Enum):
    EXERCICIO_INICIADO = "exercicio_iniciado"
    EXERCICIO_RESPONDIDO = "exercicio_respondido"
    EXERCICIO_ABANDONADO = "exercicio_abandonado"


class PayloadRespondido(BaseModel):
    """Payload de `exercicio_respondido`: tipos estritos, sem chaves extras."""

    model_config = ConfigDict(extra="forbid")

    acertou: StrictBool
    tempo_gasto_s: StrictInt = Field(gt=0)


class Evento(BaseModel):
    """Evento de um aluno; `occurred_at` sai sempre em UTC, com resolução de 1 s."""

    model_config = ConfigDict(extra="forbid")

    event_id: IdTexto
    student_id: IdTexto
    exercise_id: IdTexto
    topic: IdTexto
    event_type: TipoEvento
    occurred_at: datetime
    payload: dict[str, Any]

    @field_validator("occurred_at")
    @classmethod
    def _para_utc_sem_fracao(cls, valor: datetime) -> datetime:
        if valor.tzinfo is None or valor.utcoffset() is None:
            raise ValueError("occurred_at precisa ter fuso horário")
        try:
            return valor.astimezone(timezone.utc).replace(microsecond=0)
        except OverflowError:
            raise ValueError("occurred_at fora do intervalo suportado") from None

    @model_validator(mode="after")
    def _validar_payload(self) -> "Evento":
        if self.event_type is TipoEvento.EXERCICIO_RESPONDIDO:
            PayloadRespondido.model_validate(self.payload)
        elif self.payload:
            raise ValueError(f"payload de {self.event_type.value} deve ser vazio")
        return self

    @property
    def occurred_at_texto(self) -> str:
        return self.occurred_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def acertou(self) -> bool | None:
        if self.event_type is not TipoEvento.EXERCICIO_RESPONDIDO:
            return None
        return self.payload["acertou"]

    @property
    def tempo_gasto_s(self) -> int | None:
        if self.event_type is not TipoEvento.EXERCICIO_RESPONDIDO:
            return None
        return self.payload["tempo_gasto_s"]


class EstadoAluno(BaseModel):
    student_id: str
    velocidade_media_s: float | None
    taxa_abandono: float
    erros_seguidos: int
    desempenho_relativo: float
    respostas: int
    ultimo_evento_em: datetime
    ultimo_evento_id: str
    atualizado_em: datetime


class EstadoTopico(BaseModel):
    student_id: str
    topic_id: str
    rating_elo: float
    tentativas: int
    acertos: int
    atualizado_em: datetime


class EstadoExercicio(BaseModel):
    student_id: str
    exercise_id: str
    tentativas: int
    acertou_alguma_vez: bool


class EstadoAtualizado(BaseModel):
    """Resultado de aplicar um evento; `None` significa que aquela parte não mudou."""

    aluno: EstadoAluno
    topico: EstadoTopico | None = None
    exercicio: EstadoExercicio | None = None


class ResultadoIngestao(BaseModel):
    status: Literal["aceito", "duplicado", "rejeitado"]
    event_id: str | None = None
    motivo: str | None = None


class ExercicioRecomendado(BaseModel):
    id: str
    enunciado: str
    dificuldade: int


class Recomendacao(BaseModel):
    """Próximo exercício sugerido; sem nada a recomendar, tópico e exercício são `None`."""

    student_id: str
    topico: str | None
    exercicio: ExercicioRecomendado | None
    expectativa_acerto: float | None
    probabilidade_evasao: float
    motivo: str
