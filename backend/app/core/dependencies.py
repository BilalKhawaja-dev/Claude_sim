"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import jwt_validator
from app.models.database import async_session_factory


@dataclass
class User:
    """Authenticated user extracted from JWT claims."""

    sub: str
    email: str | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, closing it when the request finishes."""
    async with async_session_factory() as session:
        yield session


async def get_current_user(authorization: str = Header(default="")) -> User:
    """FastAPI dependency: extract Bearer token, validate via JWTValidator.

    Expects header in the form ``Authorization: Bearer <token>``.
    Returns a User with sub and email from the JWT claims.
    Raises 401 if the header is missing, malformed, or the token is invalid.

    Set env CLAUDE_SIM_SKIP_AUTH=true to bypass auth (dev mode).
    """
    import os
    if os.environ.get("CLAUDE_SIM_SKIP_AUTH", "").lower() == "true":
        return User(sub="dev-user", email="dev@claude-simulator.local")

    if not authorization or authorization.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    claims = jwt_validator.validate_token(token)

    return User(
        sub=claims["sub"],
        email=claims.get("email"),
    )
