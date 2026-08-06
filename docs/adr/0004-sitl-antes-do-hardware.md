# ADR 0004 — SITL antes do hardware

**Status:** aceito — 2026-08-06

## Contexto

Falhas de protocolo/estado não devem ser descobertas primeiro com motores e carga reais.

## Decisão

Todo fluxo MAVLink passa por fake e ArduPilot SITL antes de Pixhawk. Depois, a progressão é comunicação, bancada sem hélices, motores sem hélices, voo manual, missão curta e somente então entrega/retorno.

## Consequências

O cronograma inclui suites distintas e evidências. SITL permanece contingência de demo, mas não prova Pixhawk nem resultado final real.
