# Design system DEVcore

Este documento é a fonte de verdade visual para o aplicativo Flutter e o painel React. Novas cores, tamanhos, raios ou sombras só entram após verificar os tokens e componentes existentes.

Android e Web compartilham a mesma implementação Flutter em `mobile/`; não existe um segundo design system para o cliente Web. O painel React continua separado porque possui densidade e responsabilidade operacional diferentes.

## Referências medidas

As quatro imagens foram inspecionadas em 6 de agosto de 2026. Todas medem **1024 × 1536 px**, RGB 24 bits, proporção 2:3. São referências de alta densidade, não dimensões lógicas para widgets.

| Arquivo padronizado | Leitura visual | SHA-256 |
|---|---|---|
| `home.png` | banner 20% OFF, grade 2 colunas e navegação inferior | `382CABA80B224BFFEC1B97E2055849052056F4A05117B86AB4A8DBB17692E470` |
| `pagamento.png` | métodos selecionáveis, resumo e CTA laranja | `67EA4C610C4B5C198FC965B49CFBCF5A4486A184BB74D9C5578E856CC75A6B9E` |
| `detalhes-compra.png` | hero, informação comercial e avaliações | `1D6EE6C341AABF43103BFA44B4AFF53E4D5692148578C41843F7E5232BC36461` |
| `tela-login.png` | logotipo, campos largos, CTA azul e baixa densidade | `C64364AB4B35DD90D4A2E54C518321138455CDDAA6273DCBCA1D71F60091888B` |

Os originais ficam em `docs/design_reference/` apenas para comparação. Eles não podem ser usados como tela, background ou atalho para UI.

### Identidade geral

Fundo quase branco (`#FBFAFD` observado), cartões brancos, azul para navegação e ações gerais, laranja para promoção/compra contextual, grafite azulado para hierarquia, cinza azulado para apoio, verde para verificação e dourado para oferta/avaliação. A composição tem bastante respiro, bordas finas, raios de 12–24 e sombra muito suave.

### Login

- coluna central estreita, com aproximadamente 72% da largura da referência;
- marca centralizada acima do formulário e grande área em branco;
- campos com ícone à esquerda, rótulo e dica, borda cinza discreta;
- CTA azul largo; pixel interno medido próximo a `#3B79CB`;
- recuperação e cadastro são ações secundárias; erros precisam de contraste, não do cinza claro original.
- no Web, o bootstrap do Flutter injeta a viewport necessária; não adicionar uma meta manual duplicada ao `index.html`;
- o formulário usa largura máxima de 460, padding responsivo e nunca deve exigir rolagem horizontal.

### Home

- banner grande arredondado ocupa quase toda a largura e une azul, laranja e ilustração;
- seção “Talvez você se interesse” e grade 2 × 2 com mídia dominante;
- cartões têm borda mínima e título inferior; layout vira uma coluna em largura pequena/texto ampliado;
- barra inferior fixa tem quatro destinos (`Início`, `Buscar`, `Pedidos`, `Conta`), azul ativo medido em `#306BCE` e cinza inativo;
- promoção é dado acadêmico, não regra fixa da aplicação.
- em largura expandida, a navegação inferior vira `NavigationRail`; a grade usa de uma a quatro colunas conforme o espaço disponível.

### Detalhes do produto

- mídia hero edge-to-edge; abaixo, título, rating, preço e comerciante;
- cartão de informações usa linhas com ícone, depois descrição e divisores;
- resumo de avaliações combina número, estrelas e barras (dourado medido em `#FDBE26`);
- conteúdo é rolável. Loja, notas e comentário são fixtures, não fatos comerciais.

### Pagamento

- top bar com voltar e título central;
- métodos em cartões/linhas selecionáveis com indicador além da cor;
- referência mostra campos de cartão, mas **a implementação segura não os reproduz**: apenas escolhe `CREDIT_CARD_SIMULATED` ou `PIX_SIMULATED` e mostra aviso;
- resumo discrimina subtotal, entrega e desconto; CTA laranja em largura total;
- o azul de seleção observado é `#387EDB` e o teal do PIX `#47C1D0`.

## Tokens de cor

| Token | Valor | Uso |
|---|---|---|
| `brand.blue` | `#3478D4` | identidade e seleção não textual |
| `brand.blueAction` | `#2E68C2` | botão com texto branco e contraste AA |
| `brand.blueDark` | `#243247` | cabeçalho operacional |
| `brand.orange` | `#FF7A00` | destaque/promocional |
| `brand.orangeAction` | `#B84600` | CTA com texto branco; variante acessível |
| `surface.background` | `#FAFAFC` | canvas |
| `surface.card` | `#FFFFFF` | cartões/campos |
| `surface.subtle` | `#F3F6FB` | blocos secundários |
| `text.primary` | `#2D384C` | títulos/corpo principal |
| `text.secondary` | `#667085` | corpo secundário com contraste |
| `border.default` | `#E2E6EE` | bordas/divisores |
| `state.success` | `#258565` | sucesso e verificado |
| `state.warning` | `#9A6700` | texto de alerta; fundo claro separado |
| `state.error` | `#C73535` | erro/destrutivo |
| `state.info` | `#2E68C2` | informação |
| `rating.gold` | `#FFC028` | estrelas/barras não textuais |

`onBlue`, `onBlueAction`, `onOrangeAction` são brancos; `onOrange` é grafite. O laranja brilhante da referência não recebe texto branco pequeno porque não alcança contraste. Estados `hover`, `pressed`, `disabled`, `focus` e `selected` são derivados centralmente: hover -6% luminosidade, pressed -12%, disabled 38% opacidade sobre superfície e foco com anel azul de 3 px.

Status nunca usa a cor diretamente na feature. Um mapeamento semântico escolhe label, ícone e combinação de fundo/texto. Vermelho no admin é reservado a falha, rejeição, abortamento e destruição.

## Tipografia

A direção é uma sans geométrica arredondada. **Poppins** é a família alvo quando o arquivo licenciado for empacotado; até isso ocorrer, usa-se a pilha de sistema (`Roboto` no Android; `Inter, Segoe UI, sans-serif` no painel) sem download remoto. Não declarar um asset ausente como empacotado.

| Token | Tamanho lógico/linha | Peso |
|---|---|---|
| `display` | 40/48 | 700 |
| `headlineLarge` | 32/40 | 700 |
| `headlineMedium` | 28/36 | 650 |
| `titleLarge` | 24/32 | 650 |
| `titleMedium` | 20/28 | 600 |
| `bodyLarge` | 18/28 | 400 |
| `bodyMedium` | 16/24 | 400 |
| `bodySmall` | 14/20 | 400 |
| `labelLarge` | 16/20 | 600 |
| `labelMedium` | 14/18 | 600 |
| `caption` | 12/16 | 400 |
| `priceLarge` | 28/34 | 650 |

Escala do sistema permanece habilitada; nenhum container de texto tem altura fixa que corte 200% de zoom.

## Espaçamento, forma, sombra e movimento

- Espaçamento: `4, 8, 12, 16, 20, 24, 32, 40, 48` (`space1…space12`).
- Raios: `small=8`, `medium=12`, `large=16`, `xlarge=24`, `pill=999`.
- Ícones: `small=16`, `medium=20`, `large=24`, `xlarge=32`; alvo de toque mínimo 48.
- Sombras: `none`; `subtle=0 1 2 rgba(36,50,71,.06)`; `card=0 8 24 rgba(36,50,71,.08)`; `overlay=0 16 40 rgba(36,50,71,.16)`.
- Durações: rápida 120 ms, normal 200 ms, lenta 320 ms; respeitar redução de movimento.
- Breakpoints Flutter: compact `<360`, regular `360–599`, medium `600–839`, expanded `≥840`, com conteúdo global limitado a 1440; admin: compact `<768`, tablet `768–1199`, desktop `≥1200`.

## Componentes implementáveis e responsabilidade

Não é uma lista para gerar arquivos vazios. Um componente só existe quando é usado.

| Padrão | Flutter | React | Observação |
|---|---|---|---|
| estrutura | `AppScaffold`, `AppTopBar`, `AppBottomNavigation` | `AppShell`, `AdminSidebar`, `AdminTopBar`, `PageHeader` | densidade diferente |
| ação | `PrimaryButton`, `AccentButton`, `DangerButton` | `Button`, `IconButton`, `ConfirmDialog` | loading/disabled/idempotência |
| entrada | `AppTextField`, `AppPasswordField`, `SearchField` | `TextField`, `PasswordField`, `Select`, `Checkbox` | label/erro/foco |
| superfície | `AppCard`, `SelectableCard`, `ProductCard` | `Card`, `StatCard`, `DataTable` | não duplicar bordas |
| estado | `StatusPill`, `OrderCard`, `OrdersFilter`, `EmptyOrdersState`, `OrderProgressTimeline` | `StatusBadge`, `AlertBanner`, estados | texto + ícone + cor; status centralizado |
| avaliação | `RatingStars`, `RatingSummary`, `ReviewTile` | somente quando útil | dados demo |
| pagamento | `PaymentMethodTile`, `PriceSummaryCard` | não aplicável | sem campos bancários |
| localização | `LocationStepIndicator`, `SatelliteMapView`, `DeliveryPointSummaryCard` | `MapPanel`, `OrderSummaryCard` | regras ficam na feature |
| operação | `OrderItemTile`, `OrderPriceSummary`, `OrderDeliverySummary`, `OrderDateTimeline` | `MissionSummaryCard`, `VehicleHealthCard`, `AutomaticPreflightChecks`, `FlightAuthorizationPanel` | cliente detalhado; admin mais denso |
| diagnóstico | linhas responsivas na `RuntimeDiagnosticsScreen` | ferramentas equivalentes somente quando necessárias | somente debug; nunca exibir chave ou token |

Flutter centraliza padrões em `AppColors`, `AppTypography`, `AppSpacing`, `AppRadii`, `AppShadows`, `AppIconSizes`, `AppDurations`, `AppBreakpoints` e `AppTheme`. React usa CSS custom properties e componentes em `src/design-system`; features não criam cópias globais.

## Regras de composição

1. Procurar token e componente antes de criar estilo local.
2. Ampliar por propriedades/composição; não criar “mega componente” com toda a tela.
3. Regra de domínio fica em controller/service, nunca em widget visual.
4. Exceção de valor único deve ter motivo e virar token apenas após segundo uso real.
5. Componente novo ganha exemplo no catálogo e teste do comportamento relevante.
6. `DesignCatalogScreen` e `/design-system` aparecem somente em desenvolvimento/proteção adequada.
7. `RuntimeDiagnosticsScreen` e `/debug` aparecem somente em build debug e ambiente não hospedado; o diagnóstico segue tokens, quebra linhas longas e informa apenas presença de sessão.

Exemplo conceitual:

```dart
PrimaryButton(label: 'Entrar', isLoading: state.isSubmitting, onPressed: submit)
```

```tsx
<StatusBadge status={order.status} />
```

## Assets

- Referências: quatro PNGs listados acima, preservados apenas em documentação.
- Marca: o app reutiliza o PNG original e recorta em tempo de renderização somente o retângulo da marca, preservando os pixels e sem usar o restante da screenshot como interface. Uma tentativa generativa foi rejeitada por alterar o desenho e não integra o repositório.
- Produtos: `ProductArtwork` exibe `image_url` HTTP(S) real quando disponível e conserva a ilustração local como fallback de carregamento/erro/URL inválida; ambos usam texto alternativo/`semanticLabel` e não implicam disponibilidade real.
- Ícones: uma família coerente por plataforma; misturas precisam de revisão visual.
- Chaves e imagens privadas nunca entram no bundle ou no repositório.

## Diferenças permitidas

O mobile prioriza baixa densidade, gesto, bottom navigation e fluxo linear. O admin usa sidebar, tabelas, filtros, painéis lado a lado e confirmações reforçadas. Ambos compartilham cor, tipografia, raio, estado e tom da marca; o painel não imita uma tela de telefone.

## Responsividade e acessibilidade

- 48 × 48 mínimo para toque e 44 × 44 CSS mínimo no painel;
- deixar a viewport sob responsabilidade do bootstrap Flutter Web; uma meta manual duplicada gera aviso e deve permanecer ausente do `index.html`;
- ordem de foco previsível, `aria-label`/semantics, escape em modal e retorno do foco;
- contraste AA para texto; estrelas e chips têm label textual;
- mapa possui resumo textual de coordenadas e controles por teclado quando suportado;
- mapa real usa MapLibre com o estilo híbrido MapTiler e pino fixo no centro; o mapa recebe o gesto e o pino visual usa `IgnorePointer`;
- atribuição MapTiler/OpenStreetMap e logo oficial MapTiler permanecem visíveis/linkados, sem competir com o pino ou controles;
- telas de autenticação limitam o formulário a 460; produto/pagamento a 760; localização e lista de pedidos a 960; detalhes de pedido a 1120; a Home limita o canvas a 1440;
- o mapa interativo mede 430 em larguras menores e 520 a partir do breakpoint expanded, sem impor largura fixa;
- tabelas viram cartões/scroll controlado em tablet; grade mobile vira uma coluna se necessário;
- loading, vazio, erro e retry não dependem de cor; animações respeitam preferência reduzida.
- checks automáticos exibem texto, ícone e severidade `PASS`, `WARNING` ou `BLOCKING`; somente `BLOCKING` desabilita a autorização, e as três confirmações humanas permanecem visualmente separadas.

## Checklist visual

- [ ] tela construída com widgets/DOM, não screenshot;
- [ ] todos os valores recorrentes vêm de tokens;
- [ ] componente já existente foi reutilizado;
- [ ] loading, vazio, erro, disabled, focus e selected foram vistos;
- [ ] texto a 200% não corta nem sobrepõe;
- [ ] viewport compacta Web (inclusive 320/360/412 px) não tem overflow horizontal;
- [ ] desktop usa largura máxima, grade/rail adequados e não estica formulários indefinidamente;
- [ ] contraste e alvo de toque foram verificados;
- [ ] produto/pagamento são identificados como demonstração;
- [ ] confirmação laranja usa par de cores acessível;
- [ ] mapa final está no estilo híbrido MapTiler, com alternativa textual, atribuição e logo visíveis;
- [ ] golden/component test só muda após revisão consciente;
- [ ] captura final foi comparada manualmente com hierarquia, ritmo e composição das referências.

## Evidência visual desta rodada

A integração atual MapTiler/MapLibre ainda não recebeu revisão visual em browser ou Android. Os requests HTTP diretos de 2026-08-07 (estilo, pesquisa e reverse geocoding com HTTP 200) comprovam somente acesso aos endpoints, não layout, tiles, eventos, CORS/CSP, atribuição ou logo. A chave usada nesse ensaio foi exposta e deve ser rotacionada.

O admin aprovou lint, 33 testes e build, incluindo estados e desenho do mapa, mas isso não fecha o checklist visual. Seleção/pedido pela UI e recebimento autenticado no admin continuam pendentes de smoke manual com credenciais restritas. O pedido controlado criado diretamente pela API permanece apenas como dado de integração e não deve ser despachado.
