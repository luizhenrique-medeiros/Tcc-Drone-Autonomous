import { Crosshair, MapPinned, Satellite } from 'lucide-react';
import { useMemo, useState } from 'react';
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

const projectPoints = (points: Coordinates[]): ProjectedPoint[] => {
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

const buildStaticMapUrl = (points: Coordinates[]) => {
  const center = points.reduce(
    (result, point) => ({
      latitude: result.latitude + point.latitude / points.length,
      longitude: result.longitude + point.longitude / points.length,
    }),
    { latitude: 0, longitude: 0 },
  );
  const params = new URLSearchParams({
    center: `${center.latitude},${center.longitude}`,
    zoom: points.length > 1 ? '16' : '19',
    size: '1000x520',
    scale: '2',
    maptype: 'satellite',
    key: appConfig.googleMapsKey,
  });
  if (points.length > 1) {
    params.append(
      'path',
      `color:0xff7a00ff|weight:5|${points
        .map((point) => `${point.latitude},${point.longitude}`)
        .join('|')}`,
    );
  }
  points.forEach((point, index) => {
    params.append(
      'markers',
      `color:${index === points.length - 1 ? 'orange' : 'blue'}|label:${
        index + 1
      }|${point.latitude},${point.longitude}`,
    );
  });
  return `https://maps.googleapis.com/maps/api/staticmap?${params.toString()}`;
};

export function SatelliteMap({
  points,
  title = 'Ponto final de entrega',
  height = 330,
  activeIndex,
}: SatelliteMapProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const projected = useMemo(() => projectPoints(points), [points]);
  const staticMapUrl = useMemo(() => buildStaticMapUrl(points), [points]);
  const showSatellite = Boolean(appConfig.googleMapsKey) && !imageFailed;
  const active = points[activeIndex ?? points.length - 1];

  return (
    <section className="map-panel" aria-label={title}>
      <div className="map-panel__toolbar">
        <div>
          <strong>{title}</strong>
          <span>
            {showSatellite
              ? 'Google Maps · satélite'
              : 'Fallback coordenado · sem imagem do provedor'}
          </span>
        </div>
        <span className={`map-source ${showSatellite ? '' : 'map-source--fallback'}`}>
          {showSatellite ? <Satellite size={16} /> : <Crosshair size={16} />}
          {showSatellite ? 'Satélite' : 'Coordenadas'}
        </span>
      </div>
      <div className="map-canvas" style={{ height }}>
        {showSatellite ? (
          <img
            src={staticMapUrl}
            alt={`Imagem de satélite com ${points.length} ponto(s) da missão`}
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="coordinate-map">
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
                  index === (activeIndex ?? projected.length - 1)
                    ? 'coordinate-map__point--active'
                    : ''
                }`}
                style={{ left: `${point.x}%`, top: `${point.y}%` }}
                title={point.label ?? `Ponto ${index + 1}`}
              >
                {index + 1}
              </span>
            ))}
            <div className="coordinate-map__notice">
              <MapPinned size={21} aria-hidden="true" />
              <div>
                <strong>Imagem de satélite indisponível</strong>
                <span>
                  O traçado abaixo é relativo. Use as coordenadas exatas e o Mission
                  Planner para a revisão operacional.
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
      {active ? (
        <div className="map-panel__coordinates mono">
          <span>LAT {formatCoordinate(active.latitude)}</span>
          <span>LNG {formatCoordinate(active.longitude)}</span>
          {active.label ? <span className="map-panel__label">{active.label}</span> : null}
        </div>
      ) : null}
    </section>
  );
}
