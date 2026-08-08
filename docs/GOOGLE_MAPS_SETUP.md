# Google Maps — documento legado

O projeto deixou de usar Google Maps em 7 de agosto de 2026. A integração vigente usa MapTiler com renderização MapLibre no Flutter Android/Web e no painel administrativo, além da Search API do MapTiler no backend.

Consulte [Configuração do MapTiler](MAPTILER_SETUP.md) e [Integração de mapas](MAPS_INTEGRATION.md).

As antigas variáveis `GOOGLE_MAPS_*`, os loaders da Maps JavaScript API, `google_maps_flutter`, Places API, Geocoding API do Google e Maps Static não devem ser reintroduzidos. Este arquivo é mantido apenas para não quebrar referências históricas externas.
