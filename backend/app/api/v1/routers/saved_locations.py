from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies import CustomerUser, DatabaseSession
from app.modules.idempotency.service import execute_idempotently
from app.modules.saved_locations.models import SavedLocation
from app.modules.saved_locations.schemas import (
    SavedLocationCreate,
    SavedLocationRead,
    SavedLocationUpdate,
)
from app.modules.saved_locations.service import (
    create_saved_location,
    delete_saved_location,
    get_owned_saved_location,
    list_saved_locations,
    update_saved_location,
)

router = APIRouter(prefix="/saved-locations", tags=["Localizações salvas"])


@router.get("", response_model=list[SavedLocationRead], summary="Listar localizações salvas")
def list_locations(
    session: DatabaseSession,
    customer: CustomerUser,
) -> list[SavedLocation]:
    return list_saved_locations(session, customer.id)


@router.post(
    "",
    response_model=SavedLocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Salvar localização do cliente",
)
def create_location(
    payload: SavedLocationCreate,
    session: DatabaseSession,
    customer: CustomerUser,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=200),
    ] = None,
) -> JSONResponse:
    def action() -> dict[str, object]:
        location = create_saved_location(session, customer.id, payload, commit=False)
        return SavedLocationRead.model_validate(location).model_dump(mode="json")

    result = execute_idempotently(
        session,
        user_id=customer.id,
        operation="saved-locations.create",
        key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        response_status=status.HTTP_201_CREATED,
        action=action,
    )
    return JSONResponse(
        content=result.body,
        status_code=result.status_code,
        headers={"Idempotency-Replayed": str(result.replayed).lower()},
    )


@router.get(
    "/{location_id}",
    response_model=SavedLocationRead,
    summary="Detalhar localização salva",
)
def get_location(
    location_id: UUID,
    session: DatabaseSession,
    customer: CustomerUser,
) -> SavedLocation:
    return get_owned_saved_location(session, location_id, customer.id)


@router.patch(
    "/{location_id}",
    response_model=SavedLocationRead,
    summary="Editar localização salva",
)
def update_location(
    location_id: UUID,
    payload: SavedLocationUpdate,
    session: DatabaseSession,
    customer: CustomerUser,
) -> SavedLocation:
    location = get_owned_saved_location(
        session,
        location_id,
        customer.id,
        for_update=True,
    )
    return update_saved_location(session, location, payload)


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir localização salva",
)
def delete_location(
    location_id: UUID,
    session: DatabaseSession,
    customer: CustomerUser,
) -> Response:
    location = get_owned_saved_location(
        session,
        location_id,
        customer.id,
        for_update=True,
    )
    delete_saved_location(session, location)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
