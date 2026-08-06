# ADR 0002 — PostgreSQL com PostGIS

**Status:** aceito — 2026-08-06

## Contexto

Pedidos e auditoria precisam de consistência, enquanto cobertura/distância dependem de coordenadas geográficas reais.

## Decisão

Usar um PostgreSQL com extensão PostGIS. Coordenada final é `geography(Point,4326)` e valores numéricos auxiliares são preservados para contrato/auditoria. Migrações Alembic criam schema e índice espacial quando consultado.

## Consequências

Distâncias são calculadas no servidor e dados permanecem transacionais. Testes de integração precisam de PostGIS; SQLite pode ser usado apenas para domínio que não finja validar geografia.
