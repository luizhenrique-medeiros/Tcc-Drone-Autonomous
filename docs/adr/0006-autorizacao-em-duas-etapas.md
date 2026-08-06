# ADR 0006 — Autorização em duas etapas

**Status:** aceito — 2026-08-06

## Contexto

Aceitar um pedido comercial/acadêmico não significa que rota, veículo, área e condições estejam prontos para voar.

## Decisão

Separar:

1. decisão do pedido: aprovar/rejeitar com motivo e auditoria;
2. autorização do voo: após missão versionada/revisada, saúde recente, checklist e área controlada.

São endpoints, registros e botões distintos. A autorização expira, é de uso único, pertence a uma versão e é consumida atomicamente pelo gateway.

## Consequências

O fluxo ganha etapas e estados adicionais, mas impede upload/execução por aprovação acidental. Alterar missão ou estado crítico exige nova autorização; testes cobrem replay e concorrência.
