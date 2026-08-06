# DevCore Admin Web

Painel operacional separado para aprovação humana de pedidos, revisão de missões e autorização reforçada de voo. A interface nunca conversa diretamente com Pixhawk/MAVLink: todas as ações passam pela API autenticada.

## Executar

```powershell
Copy-Item .env.example .env.local
npm install
npm run dev
```

Por padrão o painel usa `http://localhost:8000/api/v1`. Para explorar a interface sem backend, defina `VITE_DEMO_MODE=true`. O modo demonstração é identificado em todas as telas e não se apresenta como integração real. Credenciais locais do modo demo: `admin@devcore.local` e `demo-admin`.

O token Bearer, quando necessário, fica apenas em `sessionStorage` e é apagado ao sair/fechar a sessão. A configuração também aceita autenticação por cookie HTTP-only (`credentials: include`) se o backend adotá-la. Em produção, aplique CSP, HTTPS e restrinja CORS.

## Mapas

`VITE_GOOGLE_MAPS_BROWSER_API_KEY` habilita a imagem de satélite. A chave deve ser do tipo navegador, restrita por origem e por API. Sem chave, ou em caso de falha do provedor, o painel mantém coordenadas, waypoints e um diagrama geográfico acessível; ele não finge que esse fallback é uma imagem de satélite.

## Validação

```powershell
npm run lint
npm run test
npm run build
```

O catálogo visual existe em `/design-system` somente no servidor de desenvolvimento e não entra nas rotas de produção.

## Container

O `Dockerfile` gera os assets com Node e os publica pelo Nginx na porta 80, com fallback de SPA e `/health`. As variáveis `VITE_*` são incorporadas no build; alterá-las exige reconstruir a imagem.
