# ADR 0001 — Monólito modular

**Status:** aceito — 2026-08-06

## Contexto

O TCC precisa integrar domínio transacional, equipe pequena e implantação local, sem justificar complexidade distribuída.

## Decisão

FastAPI é um único deploy com módulos de autenticação, usuários, produtos, pontos, pedidos, aprovações, missões, veículos, telemetria e eventos. Dependências seguem direção router → service → repository/model. O gateway é exceção operacional descrita no ADR 0003.

## Consequências

Transações e desenvolvimento ficam simples; limites ainda são testáveis. Escala independente, broker e tolerância distribuída não são objetivos. Redis, Celery, MQTT, Kubernetes e decomposição em microsserviços exigem novo ADR e necessidade comprovada.
