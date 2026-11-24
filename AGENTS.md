# Instruções do repositório

As instruções completas e vigentes para agentes estão em
[`AGENTS_atualizado.md`](AGENTS_atualizado.md). Leia esse arquivo integralmente
antes de modificar o projeto.

Em especial, `mobile/` é uma única aplicação Flutter para Android e Web; o
painel `admin_web/` permanece uma aplicação separada.

A plataforma alvo de voo é PX4 com QGroundControl. A migração está em
andamento: consulte `docs/MIGRACAO_PX4_QGROUNDCONTROL.md`, preserve os
bloqueios de segurança existentes e não trate funcionalidades ainda não
validadas como implementadas.

O painel administrativo pode solicitar upload, armamento normal e início de missão por ações explícitas e separadas do operador autenticado, via gateway. O site não realiza checks de aptidão de voo. O PX4 decide se aceita os comandos, com proteções nativas preservadas; o QGroundControl permanece disponível. Valide SITL e hardware antes de habilitar comandos reais.
