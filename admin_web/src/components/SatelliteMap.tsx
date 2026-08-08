import 'maplibre-gl/dist/maplibre-gl.css';

import { Crosshair, LoaderCircle, MapPinned, Satellite } from 'lucide-react';
import * as maplibregl from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import type {
  GeoJSONSource,
  Map as MapLibreMap,
  Marker,
} from 'maplibre-gl';
import { useEffect, useMemo, useRef, useState } from 'react';
import { appConfig, type Coordinates } from '../services';
import { formatCoordinate } from '../utils/format';

interface SatelliteMapProps {
  points: Coordinates[];
  title?: string;
  height?: number;
  activeIndex?: number;
}

interface ProjectedPoint extends Coordinates {
  x: number;
  y: number;
}

type MapStatus = 'fallback' | 'loading' | 'ready' | 'error';

const ROUTE_SOURCE_ID = 'admin-mission-route';
const ROUTE_LAYER_ID = 'admin-mission-route-line';
const MAP_LOAD_TIMEOUT_MS = 15_000;
const MAPTILER_LOGO_URL = 'https://api.maptiler.com/resources/logo.svg';

const isValidCoordinate = (point: Coordinates) =>
  Number.isFinite(point.latitude) &&
  Number.isFinite(point.longitude) &&
  point.latitude >= -90 &&
  point.latitude <= 90 &&
  point.longitude >= -180 &&
  point.longitude <= 180;

const projectPoints = (points: Coordinates[]): ProjectedPoint[] => {
  if (points.length === 0) {
    return [];
  }

  const latitudes = points.map((point) => point.latitude);
  const longitudes = points.map((point) => point.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLng = Math.min(...longitudes);
  const maxLng = Math.max(...longitudes);
  const latRange = Math.max(maxLat - minLat, 0.0002);
  const lngRange = Math.max(maxLng - minLng, 0.0002);
  return points.map((point) => ({
    ...point,
    x: 10 + ((point.longitude - minLng) / lngRange) * 80,
    y: 90 - ((point.latitude - minLat) / latRange) * 80,
  }));
};

const buildRouteData = (
  points: Coordinates[],
): Parameters<GeoJSONSource['setData']>[0] => ({
  type: 'FeatureCollection',
  features:
    points.length > 1
      ? [
          {
            type: 'Feature',
            properties: {},
            geometry: {
              type: 'LineString',
              coordinates: points.map((point) => [
                point.longitude,
                point.latitude,
              ]),
            },
          },
        ]
      : [],
});

const syncRoute = (map: MapLibreMap, points: Coordinates[]) => {
  const routeData = buildRouteData(points);
  const existingSource = map.getSource(ROUTE_SOURCE_ID) as
    | GeoJSONSource
    | undefined;

  if (existingSource) {
    existingSource.setData(routeData);
  } else {
    map.addSource(ROUTE_SOURCE_ID, {
      type: 'geojson',
      data: routeData,
    });
  }

  if (!map.getLayer(ROUTE_LAYER_ID)) {
    map.addLayer({
      id: ROUTE_LAYER_ID,
      type: 'line',
      source: ROUTE_SOURCE_ID,
      layout: {
        'line-cap': 'round',
        'line-join': 'round',
      },
      paint: {
        'line-color': '#ff7a00',
        'line-opacity': 0.95,
        'line-width': 4,
      },
    });
  }
};

const replaceMarkers = (
  map: MapLibreMap,
  existingMarkers: Marker[],
  points: Coordinates[],
  activeIndex: number,
) => {
  existingMarkers.forEach((marker) => marker.remove());

  return points.map((point, index) => {
    const markerElement = document.createElement('span');
    markerElement.className = `maplibre-point-marker ${
      index === activeIndex ? 'maplibre-point-marker--active' : ''
    }`;
    markerElement.textContent = String(index + 1);
    markerElement.title = point.label ?? `Ponto ${index + 1}`;
    markerElement.setAttribute(
      'aria-label',
      `${markerElement.title}: latitude ${formatCoordinate(
        point.latitude,
      )}, longitude ${formatCoordinate(point.longitude)}`,
    );

    return new maplibregl.Marker({ element: markerElement, anchor: 'center' })
      .setLngLat([point.longitude, point.latitude])
      .addTo(map);
  });
};

const fitMapToPoints = (map: MapLibreMap, points: Coordinates[]) => {
  if (points.length === 1) {
    map.jumpTo({
      center: [points[0].longitude, points[0].latitude],
      zoom: 18,
    });
    return;
  }

  const bounds = new maplibregl.LngLatBounds();
  points.forEach((point) => bounds.extend([point.longitude, point.latitude]));
  map.fitBounds(bounds, {
    duration: 0,
    maxZoom: 18,
    padding: 48,
  });
};

interface CoordinateFallbackProps {
  points: Coordinates[];
  activeIndex: number;
  reason: string;
  onRetry?: () => void;
}

function CoordinateFallback({
  points,
  activeIndex,
  reason,
  onRetry,
}: CoordinateFallbackProps) {
  const projected = useMemo(() => projectPoints(points), [points]);

  return (
    <div className="coordinate-map" data-testid="coordinate-map-fallback">
      <div className="coordinate-map__grid" aria-hidden="true" />
      {projected.length > 1 ? (
        <svg
          className="coordinate-map__route"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <polyline
            points={projected.map((point) => `${point.x},${point.y}`).join(' ')}
          />
        </svg>
      ) : null}
      {projected.map((point, index) => (
        <span
          key={`${point.latitude}-${point.longitude}-${index}`}
          className={`coordinate-map__point ${
            index === activeIndex ? 'coordinate-map__point--active' : ''
          }`}
          style={{ left: `${point.x}%`, top: `${point.y}%` }}
          title={point.label ?? `Ponto ${index + 1}`}
        >
          {index + 1}
        </span>
      ))}
      <div className="coordinate-map__notice" role="status">
        <MapPinned size={21} aria-hidden="true" />
        <div>
          <strong>Mapa híbrido indisponível</strong>
          <span>
            {reason} O traçado exibido é relativo; confirme as coordenadas exatas no
            Mission Planner.
          </span>
          {onRetry ? (
            <button type="button" onClick={onRetry}>
              Tentar carregar novamente
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function SatelliteMap({
  points,
  title = 'Ponto final de entrega',
  height = 330,
  activeIndex,
}: SatelliteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const latestPointsRef = useRef(points);
  const [providerFailure, setProviderFailure] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const coordinatesAreValid =
    points.length > 0 && points.every(isValidCoordinate);
  const canLoadMap =
    Boolean(appConfig.mapTilerStyleUrl) && coordinatesAreValid;
  const [status, setStatus] = useState<MapStatus>(
    canLoadMap ? 'loading' : 'fallback',
  );
  const resolvedActiveIndex = Math.min(
    Math.max(activeIndex ?? points.length - 1, 0),
    Math.max(points.length - 1, 0),
  );
  const active = points[resolvedActiveIndex];
  const coordinateFailure =
    points.length === 0
      ? 'Nenhuma coordenada foi recebida.'
      : !coordinatesAreValid
        ? 'A rota contém coordenadas inválidas.'
        : null;
  const fallbackReason =
    appConfig.mapTilerConfigError ??
    coordinateFailure ??
    providerFailure ??
    'O provedor não concluiu o carregamento.';

  latestPointsRef.current = points;

  useEffect(() => {
    const container = containerRef.current;
    const styleUrl = appConfig.mapTilerStyleUrl;

    if (!container || !canLoadMap || !styleUrl) {
      setProviderFailure(null);
      setStatus('fallback');
      return;
    }

    setProviderFailure(null);
    setStatus('loading');

    const startingPoint = latestPointsRef.current[0];
    let map: MapLibreMap;
    try {
      maplibregl.setWorkerUrl(maplibreWorkerUrl);
      map = new maplibregl.Map({
        attributionControl: { compact: true },
        center: [startingPoint.longitude, startingPoint.latitude],
        container,
        dragPan: true,
        scrollZoom: true,
        style: styleUrl,
        zoom: latestPointsRef.current.length > 1 ? 15 : 18,
      });
      map.addControl(
        new maplibregl.NavigationControl({ showCompass: false }),
        'top-right',
      );
    } catch {
      setProviderFailure(
        'O navegador não conseguiu inicializar o renderizador do mapa.',
      );
      setStatus('error');
      return;
    }

    mapRef.current = map;
    let disposed = false;
    let failed = false;
    const failMap = (reason: string) => {
      if (disposed || failed) {
        return;
      }
      failed = true;
      window.clearTimeout(loadTimeout);
      setProviderFailure(reason);
      setStatus('error');
    };
    const handleLoad = () => {
      if (disposed || failed) {
        return;
      }
      window.clearTimeout(loadTimeout);
      map.resize();
      setStatus('ready');
    };
    const handleError = () => {
      failMap('O MapTiler recusou ou interrompeu o carregamento do estilo.');
    };
    const loadTimeout = window.setTimeout(() => {
      failMap('O carregamento do MapTiler excedeu o tempo limite.');
    }, MAP_LOAD_TIMEOUT_MS);

    map.once('style.load', handleLoad);
    map.on('error', handleError);

    return () => {
      disposed = true;
      window.clearTimeout(loadTimeout);
      map.off('style.load', handleLoad);
      map.off('error', handleError);
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      if (mapRef.current === map) {
        mapRef.current = null;
      }
      map.remove();
    };
  }, [canLoadMap, retryToken]);

  useEffect(() => {
    const map = mapRef.current;
    if (status !== 'ready' || !map || !coordinatesAreValid) {
      return;
    }

    try {
      syncRoute(map, points);
      markersRef.current = replaceMarkers(
        map,
        markersRef.current,
        points,
        resolvedActiveIndex,
      );
      fitMapToPoints(map, points);
    } catch {
      setProviderFailure('O mapa carregou, mas não conseguiu representar a rota.');
      setStatus('error');
    }
  }, [coordinatesAreValid, points, resolvedActiveIndex, status]);

  const isMapVisible = status === 'loading' || status === 'ready';
  const statusLabel =
    status === 'ready'
      ? 'MapTiler · híbrido'
      : status === 'loading'
        ? 'MapTiler · carregando'
        : 'Fallback coordenado · mapa indisponível';

  return (
    <section className="map-panel" aria-label={title}>
      <div className="map-panel__toolbar">
        <div>
          <strong>{title}</strong>
          <span aria-live="polite">{statusLabel}</span>
        </div>
        <span
          className={`map-source ${
            isMapVisible ? '' : 'map-source--fallback'
          }`}
        >
          {status === 'ready' ? (
            <Satellite size={16} />
          ) : status === 'loading' ? (
            <LoaderCircle className="map-loading-icon" size={16} />
          ) : (
            <Crosshair size={16} />
          )}
          {status === 'ready'
            ? 'Híbrido'
            : status === 'loading'
              ? 'Carregando'
              : 'Coordenadas'}
        </span>
      </div>
      <div className="map-canvas" style={{ height }}>
        <div
          ref={containerRef}
          className={`maplibre-host ${isMapVisible ? '' : 'maplibre-host--hidden'}`}
          data-testid="maplibre-map"
          aria-label={`${title} no mapa híbrido`}
          aria-hidden={!isMapVisible}
        />
        {status === 'loading' ? (
          <div className="map-loading" role="status">
            <LoaderCircle className="map-loading-icon" size={24} />
            <span>Carregando mapa híbrido…</span>
          </div>
        ) : null}
        {!isMapVisible ? (
          <CoordinateFallback
            points={points.filter(isValidCoordinate)}
            activeIndex={resolvedActiveIndex}
            reason={fallbackReason}
            onRetry={
              status === 'error'
                ? () => setRetryToken((current) => current + 1)
                : undefined
            }
          />
        ) : null}
        {isMapVisible ? (
          <a
            className="maptiler-logo"
            href="https://www.maptiler.com/"
            target="_blank"
            rel="noreferrer"
            aria-label="MapTiler"
          >
            <img src={MAPTILER_LOGO_URL} alt="MapTiler" />
          </a>
        ) : null}
      </div>
      {active ? (
        <div className="map-panel__coordinates mono">
          <span>LAT {formatCoordinate(active.latitude)}</span>
          <span>LNG {formatCoordinate(active.longitude)}</span>
          {active.label ? (
            <span className="map-panel__label">{active.label}</span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
