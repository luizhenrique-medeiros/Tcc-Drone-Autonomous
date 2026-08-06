# ADR 0003 — Drone gateway separado

**Status:** aceito — 2026-08-06

## Contexto

MAVLink envolve portas locais, timeouts, reconexão e risco físico diferentes da API HTTP.

## Decisão

Executar `drone_gateway` como processo Python separado, autenticado na API e sem banco direto. Todo `pymavlink` fica nele, atrás de `VehicleGateway` com fake, SITL e real.

## Consequências

Testes HTTP não tocam hardware e o gateway pode ficar junto ao veículo. Há contrato/idempotência/reconciliação adicionais; o backend continua fonte de verdade de autorização e o ArduPilot do estado físico.
