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

O painel usa MapLibre GL JS com o estilo vetorial híbrido do MapTiler. O mapa é interativo, permite pan/zoom, desenha a rota e seus pontos e ajusta a câmera ao conjunto de coordenadas. Não é usado `iframe` nem Static Maps. O worker ESM do MapLibre 6 é importado com `?worker&url`; mantenha esse pipeline do Vite para gerar um worker autocontido com MIME JavaScript correto.

Configure no `.env.local`:

```dotenv
MAPTILER_WEB_API_KEY=sua_chave_web
MAPTILER_STYLE_URL=https://api.maptiler.com/maps/hybrid-v4/style.json
```

A chave é incorporada ao bundle web e, portanto, deve ser tratada como chave pública de navegador: restrinja-a aos domínios autorizados no painel do MapTiler e rotacione-a se for exposta. Mantenha a chave fora de `MAPTILER_STYLE_URL`; a aplicação acrescenta o parâmetro ao carregar o estilo. As atribuições do estilo continuam visíveis pelo controle nativo do MapLibre e o logo oficial linkado do MapTiler é exibido para atender ao plano Free.

Enquanto o estilo carrega, o painel informa o estado. Sem configuração, com coordenadas inválidas, após timeout ou erro do provedor, ele mantém coordenadas, waypoints e um diagrama geográfico acessível; o fallback é identificado e nunca se apresenta como mapa carregado.

## Validação

```powershell
npm run lint
npm run test
npm run build
```

O catálogo visual existe em `/design-system` somente no servidor de desenvolvimento e não entra nas rotas de produção.

## Container

O `Dockerfile` gera os assets com Node e os publica pelo Nginx na porta 80, com fallback de SPA e `/health`. `VITE_*`, `MAPTILER_WEB_API_KEY` e `MAPTILER_STYLE_URL` são incorporadas no build; alterá-las exige reconstruir a imagem. Exemplo:

```powershell
docker build `
  --build-arg MAPTILER_WEB_API_KEY=$env:MAPTILER_WEB_API_KEY `
  --build-arg MAPTILER_STYLE_URL=https://api.maptiler.com/maps/hybrid-v4/style.json `
  -t devcore-admin-web .
```
