# ADR 0005 — Painel administrativo separado

**Status:** aceito — 2026-08-06

## Contexto

Operação precisa de mapa, tabela, saúde, checklist e ações críticas que não pertencem ao app do cliente nem a páginas improvisadas da API.

## Decisão

Criar aplicação React/TypeScript/Vite separada, consumindo a mesma API e protegida por `ADMIN`. Ela compartilha tokens da marca, mas usa densidade desktop/tablet e componentes operacionais.

## Consequências

Há build/deploy/testes próprios e CORS a configurar. Nenhuma segurança depende da UI; o backend verifica papel e estado. O app Flutter continua sem ações administrativas.
