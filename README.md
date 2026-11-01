# behavioral-digital-twin

Pipeline de dados que transforma eventos de interação de alunos de álgebra (cursinho popular) em um gêmeo digital do aluno: um estado por aluno, atualizado a cada evento, que alimenta uma API de recomendação do próximo exercício. O foco é engenharia de dados e separação de camadas (eventos brutos como fonte da verdade, idempotência, evento atrasado, reprocessamento), não um produto. Python 3.10, SQLite, Pydantic e FastAPI. Este README é um rascunho; a versão final vem no fim do projeto.

```bash
pip install -r requirements-dev.txt
pytest
```

Design completo: `docs/superpowers/specs/2026-10-31-behavioral-digital-twin-design.md`.
