from fastapi import APIRouter, status

from app.api.dependencies import AppSettings, CurrentUser, DatabaseSession
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from app.modules.auth.service import login, register_customer
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["Autenticação"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cliente",
)
def register(payload: RegisterRequest, session: DatabaseSession) -> UserRead:
    return UserRead.model_validate(register_customer(session, payload))


@router.post("/login", response_model=TokenResponse, summary="Autenticar usuário")
def authenticate(
    payload: LoginRequest, session: DatabaseSession, settings: AppSettings
) -> TokenResponse:
    return login(session, payload, settings)


@router.get("/me", response_model=UserRead, summary="Obter usuário autenticado")
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
