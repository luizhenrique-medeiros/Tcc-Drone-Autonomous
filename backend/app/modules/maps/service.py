from __future__ import annotations

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


def _api_key(settings: Settings) -> str:
    if not settings.google_maps_server_api_key:
        raise MapsNotConfiguredError("A chave de servidor do Google Maps não foi configurada")
    return settings.google_maps_server_api_key


async def _google_get(path: str, params: dict[str, str], settings: Settings) -> dict[str, object]:
    params["key"] = _api_key(settings)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"https://maps.googleapis.com{path}", params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise MapsProviderError("Falha ao consultar o provedor de mapas") from exc
    status = data.get("status")
    if status == "ZERO_RESULTS":
        return data
    if status != "OK":
        raise MapsProviderError(f"O provedor de mapas retornou o estado {status}")
    return data


async def search_places(query: str, settings: Settings) -> list[PlaceSuggestion]:
    data = await _google_get(
        "/maps/api/place/autocomplete/json",
        {
            "input": query,
            "components": f"country:{settings.maps_search_country.lower()}",
            "language": "pt-BR",
        },
        settings,
    )
    suggestions: list[PlaceSuggestion] = []
    for prediction in data.get("predictions", []):
        formatting = prediction.get("structured_formatting", {})
        suggestions.append(
            PlaceSuggestion(
                place_id=prediction["place_id"],
                description=prediction["description"],
                main_text=formatting.get("main_text", prediction["description"]),
                secondary_text=formatting.get("secondary_text", ""),
            )
        )
    return suggestions


async def geocode(
    address: str | None, place_id: str | None, settings: Settings
) -> GeocodedLocation:
    if bool(address) == bool(place_id):
        raise MapsQueryError("Informe exatamente um dos parâmetros: address ou place_id")
    query = {"language": "pt-BR"}
    if place_id:
        query["place_id"] = place_id
    else:
        query["address"] = address or ""
        query["components"] = f"country:{settings.maps_search_country}"
    data = await _google_get(
        "/maps/api/geocode/json",
        query,
        settings,
    )
    results = data.get("results", [])
    if not results:
        raise NotFoundError("Endereço não encontrado")
    result = results[0]
    location = result["geometry"]["location"]
    return GeocodedLocation(
        formatted_address=result["formatted_address"],
        latitude=location["lat"],
        longitude=location["lng"],
        place_id=result.get("place_id"),
    )


async def reverse_geocode(
    latitude: float, longitude: float, settings: Settings
) -> GeocodedLocation:
    data = await _google_get(
        "/maps/api/geocode/json",
        {"latlng": f"{latitude},{longitude}", "language": "pt-BR"},
        settings,
    )
    results = data.get("results", [])
    if not results:
        raise NotFoundError("Não foi encontrada referência textual para o ponto")
    result = results[0]
    location = result["geometry"]["location"]
    return GeocodedLocation(
        formatted_address=result["formatted_address"],
        latitude=location["lat"],
        longitude=location["lng"],
        place_id=result.get("place_id"),
    )
