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

O painel aprova o pedido, gera a missão e disponibiliza o arquivo `.plan` por pedido e revisão. O operador abre e revisa o plano no QGroundControl e usa esse aplicativo para todas as ações na Pixhawk. O PX4 mantém suas proteções nativas.

Site e gateway acompanham passivamente a telemetria. Não habilite envio de comandos, consultas ativas, transferências de missão ou alteração de parâmetros pelo gateway real. Exportação independe da aeronave e não confirma upload, voo ou entrega. Comandos legados ficam isolados em testes.
