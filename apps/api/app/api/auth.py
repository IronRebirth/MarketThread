from datetime import timedelta
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db.models.user import User
from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_user_by_email(
    email: str,
    session: AsyncSession,
) -> User | None:
    """Find a user by normalized email address."""

    result = await session.execute(
        select(User).where(User.email == email.lower()),
    )

    return result.scalar_one_or_none()


def _validate_cookie_origin(request: Request) -> None:
    """Reject cross-origin state-changing requests using cookie authentication."""

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Cookie-authenticated state-changing requests require "
                "an Origin header."
            ),
        )

    settings = get_settings()
    allowed_origins = {
        item.strip()
        for item in settings.cors_allowed_origins.split(",")
        if item.strip()
    }

    if origin not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin authentication request is not allowed.",
        )


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: DatabaseSession,
) -> User:
    """Resolve and validate the authenticated user from bearer or cookie auth."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    settings = get_settings()
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    using_cookie_auth = token is None and cookie_token is not None

    if using_cookie_auth:
        _validate_cookie_origin(request)

    token = token or cookie_token

    if token is None:
        raise credentials_exception

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        token_type = payload.get("typ")
        token_session_version = payload.get("sv")

        if (
            not isinstance(subject, str)
            or token_type != ACCESS_TOKEN_TYPE
            or not isinstance(token_session_version, int)
        ):
            raise credentials_exception

        user_id = UUID(subject)
    except jwt.PyJWTError:
        raise credentials_exception from None
    except (TypeError, ValueError):
        raise credentials_exception from None

    user = await session.get(User, user_id)

    if (
        user is None
        or not user.is_active
        or user.session_version != token_session_version
    ):
        raise credentials_exception

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: UserCreate,
    session: DatabaseSession,
) -> User:
    """Create a new user account."""

    email = payload.email.lower()

    existing_user = await get_user_by_email(email, session)

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    settings = get_settings()
    admin_emails = {
        item.strip().lower()
        for item in settings.admin_emails.split(",")
        if item.strip()
    }

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        is_active=True,
        role="admin" if email in admin_emails else "user",
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@router.post("/login", response_model=UserRead)
async def login(
    payload: LoginRequest,
    response: Response,
    session: DatabaseSession,
) -> User:
    """Authenticate a user and establish a secure browser session."""

    user = await get_user_by_email(payload.email.lower(), session)

    if user is None or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    settings = get_settings()
    access_token = create_access_token(
        subject=str(user.id),
        session_version=user.session_version,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )

    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    response: Response,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> None:
    """Invalidate the current user's active access tokens and cookie."""

    current_user.session_version += 1
    await session.commit()

    settings = get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
    )


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: CurrentUser) -> User:
    """Return the currently authenticated user."""

    return current_user
