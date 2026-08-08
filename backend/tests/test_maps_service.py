from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.modules.maps.service import (
    MapsNotConfiguredError,
    MapsProviderError,
    MapsQueryError,
    geocode,
    reverse_geocode,
    search_places,
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "sqlite+pysqlite:///:memory:",
        "jwt_secret": "test-secret-that-is-long-enough",
        "gateway_api_key": "test-gateway-key",
        "maptiler_server_api_key": "test-server-key",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _feature(
    *,
    feature_id: str = "poi.123",
    text: str = "Torre Eiffel",
    place_name: str = "Torre Eiffel, Paris, França",
    center: object = (2.2945, 48.8584),
) -> dict[str, object]:
    return {
        "id": feature_id,
        "type": "Feature",
        "text": text,
        "place_name": place_name,
        "center": center,
        "geometry": {"type": "Point", "coordinates": center},
    }


def test_search_uses_maptiler_autocomplete_and_parses_geojson() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.host == "api.maptiler.com"
        assert request.url.raw_path.split(b"?")[0] == b"/geocoding/Torre%20Eiffel.json"
        assert dict(request.url.params) == {
            "language": "pt",
            "limit": "5",
            "autocomplete": "true",
            "key": "test-server-key",
        }
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    _feature(),
                    {"type": "Feature", "text": "sem identificador"},
                    "entrada inválida",
                ],
                "attribution": "© MapTiler © OpenStreetMap contributors",
            },
        )

    async def scenario() -> list[dict[str, object]]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            suggestions = await search_places("  Torre Eiffel  ", _settings(), client)
        return [item.model_dump() for item in suggestions]

    assert asyncio.run(scenario()) == [
        {
            "place_id": "poi.123",
            "description": "Torre Eiffel, Paris, França",
            "main_text": "Torre Eiffel",
            "secondary_text": "Paris, França",
        }
    ]


def test_search_sends_optional_country_in_maptiler_format() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["country"] == "br"
        return httpx.Response(200, json={"type": "FeatureCollection", "features": []})

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            suggestions = await search_places(
                "Avenida Paulista",
                _settings(maps_search_country="BR"),
                client,
            )
        assert suggestions == []

    asyncio.run(scenario())


def test_search_permission_error_is_actionable_and_does_not_expose_key() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "denied"})

    async def scenario() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(MapsProviderError) as captured:
                await search_places("Torre Eiffel", _settings(), client)
        assert captured.value.__cause__ is None
        return str(captured.value)

    message = asyncio.run(scenario())
    assert "MapTiler" in message
    assert "HTTP 403" in message
    assert "test-server-key" not in message


def test_search_requires_configured_server_key() -> None:
    with pytest.raises(MapsNotConfiguredError, match="MapTiler"):
        asyncio.run(
            search_places(
                "Torre Eiffel",
                _settings(maptiler_server_api_key=None),
            )
        )


def test_search_rejects_malformed_feature_collection() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"type": "FeatureCollection", "features": {"unexpected": True}},
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(MapsProviderError, match="lista de resultados inválida"):
                await search_places("Torre Eiffel", _settings(), client)

    asyncio.run(scenario())


def test_geocode_address_uses_forward_search_without_country_when_blank() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path.split(b"?")[0] == b"/geocoding/Torre%20Eiffel.json"
        assert request.url.params["autocomplete"] == "false"
        assert request.url.params["limit"] == "1"
        assert "country" not in request.url.params
        return httpx.Response(
            200,
            json={"type": "FeatureCollection", "features": [_feature()]},
        )

    async def scenario() -> object:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await geocode("Torre Eiffel", None, _settings(), client)

    result = asyncio.run(scenario())
    assert result.formatted_address == "Torre Eiffel, Paris, França"
    assert result.latitude == 48.8584
    assert result.longitude == 2.2945
    assert result.place_id == "poi.123"


def test_geocode_resolves_maptiler_feature_id_and_falls_back_to_geometry() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/geocoding/poi.123.json"
        assert "country" not in request.url.params
        feature = _feature(center=None)
        feature["geometry"] = {"type": "Point", "coordinates": [2.2945, 48.8584]}
        return httpx.Response(
            200,
            json={"type": "FeatureCollection", "features": [feature]},
        )

    async def scenario() -> object:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await geocode(None, "poi.123", _settings(maps_search_country="BR"), client)

    result = asyncio.run(scenario())
    assert result.latitude == 48.8584
    assert result.longitude == 2.2945


def test_reverse_geocode_sends_longitude_before_latitude() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/geocoding/-46.58131,-23.11872.json"
        assert request.url.params["language"] == "pt"
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    _feature(
                        feature_id="address.456",
                        text="Rua de teste",
                        place_name="Rua de teste, Bragança Paulista, Brasil",
                        center=(-46.58131, -23.11872),
                    )
                ],
            },
        )

    async def scenario() -> object:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await reverse_geocode(-23.11872, -46.58131, _settings(), client)

    result = asyncio.run(scenario())
    assert result.latitude == -23.11872
    assert result.longitude == -46.58131


def test_geocode_rejects_provider_coordinates_outside_valid_range() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [_feature(center=(181, 91))],
            },
        )

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(MapsProviderError, match="sem coordenadas válidas"):
                await geocode("Torre Eiffel", None, _settings(), client)

    asyncio.run(scenario())


def test_search_rejects_whitespace_query_without_calling_maptiler() -> None:
    with pytest.raises(MapsQueryError, match="três caracteres"):
        asyncio.run(search_places("   ", _settings()))


def test_country_configuration_requires_iso_two_letter_code() -> None:
    with pytest.raises(ValueError, match="código ISO"):
        _settings(maps_search_country="BRA")


def test_server_key_configuration_rejects_full_url() -> None:
    with pytest.raises(ValueError, match="somente a chave"):
        _settings(maptiler_server_api_key="https://example.invalid/style.json?key=fake")
