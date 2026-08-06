from pydantic import BaseModel


class PlaceSuggestion(BaseModel):
    place_id: str
    description: str
    main_text: str
    secondary_text: str


class GeocodedLocation(BaseModel):
    formatted_address: str
    latitude: float
    longitude: float
    place_id: str | None = None
