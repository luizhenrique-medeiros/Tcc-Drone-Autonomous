import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SatelliteMap } from '../src/components/SatelliteMap';
import {
  appConfig,
  DEFAULT_MAPTILER_STYLE_URL,
  resolveMapTilerConfiguration,
} from '../src/services/config';

const maplibreMocks = vi.hoisted(() => {
  type Handler = () => void;

  const maps: MapMock[] = [];
  const markers: MarkerMock[] = [];

  class MapMock {
    handlers = new globalThis.Map<string, Set<Handler>>();
    layers = new Set<string>();
    sources = new globalThis.Map<string, { setData: ReturnType<typeof vi.fn> }>();
    options: Record<string, unknown>;

    addControl = vi.fn();
    addLayer = vi.fn((layer: { id: string }) => {
      this.layers.add(layer.id);
    });
    addSource = vi.fn((id: string) => {
      this.sources.set(id, { setData: vi.fn() });
    });
    fitBounds = vi.fn();
    getLayer = vi.fn((id: string) =>
      this.layers.has(id) ? { id } : undefined,
    );
    getSource = vi.fn((id: string) => this.sources.get(id));
    jumpTo = vi.fn();
    remove = vi.fn();
    resize = vi.fn();

    constructor(options: Record<string, unknown>) {
      this.options = options;
      maps.push(this);
    }

    on(event: string, handler: Handler) {
      const handlers = this.handlers.get(event) ?? new Set<Handler>();
      handlers.add(handler);
      this.handlers.set(event, handlers);
      return this;
    }

    once(event: string, handler: Handler) {
      return this.on(event, handler);
    }

    off(event: string, handler: Handler) {
      this.handlers.get(event)?.delete(handler);
      return this;
    }

    emit(event: string) {
      this.handlers.get(event)?.forEach((handler) => handler());
    }
  }

  class MarkerMock {
    element: HTMLElement;
    addTo = vi.fn(() => this);
    remove = vi.fn();
    setLngLat = vi.fn(() => this);

    constructor(options: { element: HTMLElement }) {
      this.element = options.element;
      markers.push(this);
    }
  }

  class LngLatBoundsMock {
    extend = vi.fn(() => this);
  }

  class NavigationControlMock {}

  return {
    LngLatBoundsMock,
    MapMock,
    MarkerMock,
    NavigationControlMock,
    maps,
    markers,
    setWorkerUrl: vi.fn(),
  };
});

vi.mock('maplibre-gl', () => ({
  LngLatBounds: maplibreMocks.LngLatBoundsMock,
  Map: maplibreMocks.MapMock,
  Marker: maplibreMocks.MarkerMock,
  NavigationControl: maplibreMocks.NavigationControlMock,
  setWorkerUrl: maplibreMocks.setWorkerUrl,
}));

const configuredStyleUrl = `${DEFAULT_MAPTILER_STYLE_URL}?key=browser-test`;
const originalMapConfig = {
  error: appConfig.mapTilerConfigError,
  styleUrl: appConfig.mapTilerStyleUrl,
};

const points = [
  { latitude: -23.11872, longitude: -46.58131, label: 'Origem' },
  { latitude: -23.1195, longitude: -46.5798, label: 'Destino' },
];

describe('configuração MapTiler', () => {
  it('exige uma chave separada e aceita o estilo híbrido oficial', () => {
    expect(resolveMapTilerConfiguration('', DEFAULT_MAPTILER_STYLE_URL)).toEqual({
      styleUrl: '',
      error: 'A chave web do MapTiler não foi configurada.',
    });

    const configuration = resolveMapTilerConfiguration(
      'browser-test',
      DEFAULT_MAPTILER_STYLE_URL,
    );
    const styleUrl = new URL(configuration.styleUrl);

    expect(configuration.error).toBeNull();
    expect(styleUrl.origin).toBe('https://api.maptiler.com');
    expect(styleUrl.pathname).toBe('/maps/hybrid-v4/style.json');
    expect(styleUrl.searchParams.get('key')).toBe('browser-test');
  });

  it('rejeita estilos fora do endpoint HTTPS do MapTiler', () => {
    expect(
      resolveMapTilerConfiguration(
        'browser-test',
        'https://maps.example.test/style.json',
      ),
    ).toEqual({
      styleUrl: '',
      error: 'A URL de estilo do MapTiler é inválida.',
    });
  });
});

describe('mapa operacional MapTiler', () => {
  beforeEach(() => {
    maplibreMocks.maps.length = 0;
    maplibreMocks.markers.length = 0;
    appConfig.mapTilerStyleUrl = configuredStyleUrl;
    appConfig.mapTilerConfigError = null;
  });

  afterEach(() => {
    appConfig.mapTilerStyleUrl = originalMapConfig.styleUrl;
    appConfig.mapTilerConfigError = originalMapConfig.error;
  });

  it('carrega o estilo, desenha rota e pontos e ajusta os limites', async () => {
    render(<SatelliteMap points={points} title="Rota de teste" />);

    expect(screen.getByText('Carregando mapa híbrido…')).toBeInTheDocument();
    expect(maplibreMocks.maps).toHaveLength(1);
    expect(maplibreMocks.maps[0].options).toMatchObject({
      attributionControl: { compact: true },
      dragPan: true,
      scrollZoom: true,
      style: configuredStyleUrl,
    });

    act(() => maplibreMocks.maps[0].emit('style.load'));

    await waitFor(() => {
      expect(screen.getByText('MapTiler · híbrido')).toBeInTheDocument();
      expect(maplibreMocks.maps[0].addSource).toHaveBeenCalledWith(
        'admin-mission-route',
        expect.objectContaining({ type: 'geojson' }),
      );
      expect(maplibreMocks.maps[0].fitBounds).toHaveBeenCalled();
      expect(maplibreMocks.markers).toHaveLength(2);
    });

    expect(screen.getByRole('link', { name: 'MapTiler' })).toHaveAttribute(
      'href',
      'https://www.maptiler.com/',
    );
    expect(screen.queryByTestId('coordinate-map-fallback')).not.toBeInTheDocument();
  });

  it('declara a falha do provedor e oferece nova tentativa', async () => {
    render(<SatelliteMap points={points} />);

    act(() => maplibreMocks.maps[0].emit('error'));

    expect(await screen.findByTestId('coordinate-map-fallback')).toBeInTheDocument();
    expect(
      screen.getByText(/MapTiler recusou ou interrompeu o carregamento do estilo/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Tentar carregar novamente' }),
    ).toBeInTheDocument();
  });

  it('centraliza um ponto único com zoom operacional', async () => {
    render(<SatelliteMap points={[points[0]]} />);

    act(() => maplibreMocks.maps[0].emit('style.load'));

    await waitFor(() => {
      expect(maplibreMocks.maps[0].jumpTo).toHaveBeenCalledWith({
        center: [points[0].longitude, points[0].latitude],
        zoom: 18,
      });
    });
    expect(maplibreMocks.maps[0].fitBounds).not.toHaveBeenCalled();
  });

  it('usa o fallback identificado quando a configuração está ausente', () => {
    appConfig.mapTilerStyleUrl = '';
    appConfig.mapTilerConfigError =
      'A chave web do MapTiler não foi configurada.';

    render(<SatelliteMap points={[points[0]]} />);

    expect(screen.getByTestId('coordinate-map-fallback')).toBeInTheDocument();
    expect(
      screen.getByText(/A chave web do MapTiler não foi configurada/),
    ).toBeInTheDocument();
    expect(maplibreMocks.maps).toHaveLength(0);
  });
});
