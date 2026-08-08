from __future__ import annotations

import math
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.exceptions import DomainError, NotFoundError
from app.modules.maps.schemas import GeocodedLocation, PlaceSuggestion


class MapsNotConfiguredError(DomainError):
    status_code = 503
    code = "MAPS_NOT_CONFIGURED"


class MapsProviderError(DomainError):
    status_code = 502
    code = "MAPS_PROVIDER_ERROR"


class MapsQueryError(DomainError):
    status_code = 422
    code = "MAPS_QUERY_INVALID"


_MAPTILER_GEOCODING_BASE_URL = "https://api.maptiler.com/geocoding"


def _api_key(settings: Settings) -> str:
    if not settings.maptiler_server_api_key:
        raise MapsNotConfiguredError("A chave de servidor do MapTiler não foi configurada")
    return settings.maptiler_server_api_key


async def _maptiler_get(
    search_term: str,
    params: dict[str, str],
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> dict[str, object]:
    encoded_term = quote(search_term, safe=",")
    query = {**params, "key": _api_key(settings)}
    owns_client = client is None
    request_client = client or httpx.AsyncClient(timeout=8.0)
    try:
        response = await request_client.get(
            f"{_MAPTILER_GEOCODING_BASE_URL}/{encoded_term}.json",
            params=query,
        )
        response.raise_for_status()
        data: object = response.json()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 403:
            detail = (
                "O MapTiler recusou a consulta (HTTP 403). Verifique se a chave existe, "
                "está ativa e permite requisições do backend."
            )
        elif status_code == 429:
            detail = "O limite de consultas do MapTiler foi atingido (HTTP 429)"
        else:
            detail = f"O MapTiler recusou a consulta (HTTP {status_code})"
        raise MapsProviderError(detail) from None
    except (httpx.HTTPError, ValueError):
        raise MapsProviderError("Falha ao consultar o MapTiler") from None
    finally:
        if owns_client:
            await request_client.aclose()

    if not isinstance(data, dict):
        raise MapsProviderError("O MapTiler retornou uma resposta inválida")
    response_type = data.get("type")
    if response_type is not None and response_type != "FeatureCollection":
        raise MapsProviderError("O MapTiler retornou um GeoJSON inválido")
    return data


def _features(data: dict[str, object]) -> list[object]:
    raw_features = data.get("features")
    if not isinstance(raw_features, list):
        raise MapsProviderError("O MapTiler retornou uma lista de resultados inválida")
    return raw_features


def _non_empty_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _coordinate_pair(value: object) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise MapsProviderError("O MapTiler retornou coordenadas ausentes")
    raw_longitude, raw_latitude = value[0], value[1]
    if isinstance(raw_longitude, bool) or isinstance(raw_latitude, bool):
        raise MapsProviderError("O MapTiler retornou coordenadas inválidas")
    try:
        longitude = float(raw_longitude)
        latitude = float(raw_latitude)
    except (TypeError, ValueError):
        raise MapsProviderError("O MapTiler retornou coordenadas inválidas") from None
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise MapsProviderError("O MapTiler retornou coordenadas fora da faixa válida")
    return latitude, longitude


def _feature_coordinates(feature: dict[str, object]) -> tuple[float, float]:
    candidates: list[object] = [feature.get("center")]
    geometry = feature.get("geometry")
    if isinstance(geometry, dict):
        candidates.append(geometry.get("coordinates"))
    for candidate in candidates:
        try:
            return _coordinate_pair(candidate)
        except MapsProviderError:
            continue
    raise MapsProviderError("O MapTiler retornou um resultado sem coordenadas válidas")


def _parse_geocoded_feature(raw_feature: object) -> GeocodedLocation:
    if not isinstance(raw_feature, dict):
        raise MapsProviderError("O MapTiler retornou um resultado inválido")
    formatted_address = _non_empty_string(raw_feature.get("place_name"))
    if not formatted_address:
        formatted_address = _non_empty_string(raw_feature.get("text"))
    if not formatted_address:
        raise MapsProviderError("O MapTiler retornou um resultado sem endereço")
    latitude, longitude = _feature_coordinates(raw_feature)
    feature_id = _non_empty_string(raw_feature.get("id"))
    return GeocodedLocation(
        formatted_address=formatted_address,
        latitude=latitude,
        longitude=longitude,
        place_id=feature_id or None,
    )


def _secondary_text(main_text: str, description: str) -> str:
    prefix = f"{main_text}, "
    if main_text and description.startswith(prefix):
        return description[len(prefix) :]
    return "" if description == main_text else description


async def search_places(
    query: str,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> list[PlaceSuggestion]:
    normalized_query = query.strip()
    if len(normalized_query) < 3:
        raise MapsQueryError("A pesquisa deve conter ao menos três caracteres")
    if len(normalized_query) > 200:
        raise MapsQueryError("A pesquisa deve conter no máximo 200 caracteres")

    params = {"language": "pt", "limit": "5", "autocomplete": "true"}
    if settings.maps_search_country:
        params["country"] = settings.maps_search_country.lower()
    data = await _maptiler_get(normalized_query, params, settings, client)

    suggestions: list[PlaceSuggestion] = []
    for raw_feature in _features(data):
        if not isinstance(raw_feature, dict):
            continue
        feature_id = _non_empty_string(raw_feature.get("id"))
        main_text = _non_empty_string(raw_feature.get("text"))
        description = _non_empty_string(raw_feature.get("place_name")) or main_text
        if not feature_id or not description:
            continue
        main_text = main_text or description
        suggestions.append(
            PlaceSuggestion(
                place_id=feature_id,
                description=description,
                main_text=main_text,
                secondary_text=_secondary_text(main_text, description),
            )
        )
    return suggestions


async def geocode(
    address: str | None,
    place_id: str | None,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> GeocodedLocation:
    normalized_address = address.strip() if address else None
    normalized_place_id = place_id.strip() if place_id else None
    if bool(normalized_address) == bool(normalized_place_id):
        raise MapsQueryError("Informe exatamente um dos parâmetros: address ou place_id")
    search_term = normalized_place_id or normalized_address or ""
    if len(search_term) < 3 or len(search_term) > 300:
        raise MapsQueryError("O endereço ou identificador deve conter entre 3 e 300 caracteres")

    params = {"language": "pt", "limit": "1", "autocomplete": "false"}
    if normalized_address and settings.maps_search_country:
        params["country"] = settings.maps_search_country.lower()
    data = await _maptiler_get(search_term, params, settings, client)
    features = _features(data)
    if not features:
        raise NotFoundError("Endereço não encontrado")
    return _parse_geocoded_feature(features[0])


def _format_coordinate(value: float) -> str:
    formatted = f"{value:.8f}".rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


async def reverse_geocode(
    latitude: float,
    longitude: float,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> GeocodedLocation:
    if (
        isinstance(latitude, bool)
        or isinstance(longitude, bool)
        or not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise MapsQueryError("Latitude ou longitude fora da faixa válida")
    search_term = f"{_format_coordinate(longitude)},{_format_coordinate(latitude)}"
    data = await _maptiler_get(
        search_term,
        {"language": "pt", "limit": "1"},
        settings,
        client,
    )
    features = _features(data)
    if not features:
        raise NotFoundError("Não foi encontrada referência textual para o ponto")
    return _parse_geocoded_feature(features[0])
