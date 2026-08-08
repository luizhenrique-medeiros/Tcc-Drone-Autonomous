from fastapi import APIRouter, Query

from app.api.dependencies import AppSettings, CurrentUser
from app.modules.maps.schemas import GeocodedLocation, PlaceSuggestion
from app.modules.maps.service import geocode, reverse_geocode, search_places

router = APIRouter(prefix="/maps", tags=["Mapas"])


@router.get(
    "/places/search",
    response_model=list[PlaceSuggestion],
    summary="Pesquisar regiões aproximadas pelo MapTiler",
)
async def places_search(
    settings: AppSettings,
    _user: CurrentUser,
    query: str = Query(alias="q", min_length=3, max_length=200),
) -> list[PlaceSuggestion]:
    return await search_places(query, settings)


@router.get("/geocode", response_model=GeocodedLocation, summary="Geocodificar endereço")
async def geocode_address(
    settings: AppSettings,
    _user: CurrentUser,
    address: str | None = Query(default=None, min_length=3, max_length=300),
    place_id: str | None = Query(default=None, min_length=3, max_length=300),
) -> GeocodedLocation:
    return await geocode(address, place_id, settings)


@router.get(
    "/reverse-geocode",
    response_model=GeocodedLocation,
    summary="Obter endereço apenas como referência textual",
)
async def reverse_geocode_point(
    settings: AppSettings,
    _user: CurrentUser,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
) -> GeocodedLocation:
    return await reverse_geocode(latitude, longitude, settings)
