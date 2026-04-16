"""JWT validation against Keycloak JWKS endpoint."""

import time
from typing import Any

import httpx
import jwt
from cachetools import TTLCache
from fastapi import HTTPException, status

from app.core.config import settings


class JWTValidator:
    """Validates JWT access tokens against Keycloak JWKS endpoint.

    Caches JWKS keys with a TTL to avoid hitting Keycloak on every request.
    """

    def __init__(
        self,
        jwks_url: str | None = None,
        issuer: str | None = None,
        audience: str | None = None,
        cache_ttl: int = 300,
    ) -> None:
        base = settings.keycloak_url.rstrip("/")
        realm = settings.keycloak_realm
        self.jwks_url = jwks_url or f"{base}/realms/{realm}/protocol/openid-connect/certs"
        self.issuer = issuer or f"{base}/realms/{realm}"
        self.audience = audience or settings.keycloak_client_id
        # Cache: 1 entry (the full JWKS key set), refreshed every cache_ttl seconds
        self._jwks_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=4, ttl=cache_ttl)

    def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch JWKS from Keycloak, using cache when available."""
        cached = self._jwks_cache.get("jwks")
        if cached is not None:
            return cached

        try:
            resp = httpx.get(self.jwks_url, timeout=10)
            resp.raise_for_status()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to fetch JWKS keys",
            ) from exc

        jwks_data = resp.json()
        self._jwks_cache["jwks"] = jwks_data
        return jwks_data

    def _get_signing_key(self, token: str) -> jwt.algorithms.RSAAlgorithm:
        """Extract the signing key matching the token's kid from JWKS."""
        jwks_data = self._fetch_jwks()
        jwk_client_keys = jwt.PyJWKSet.from_dict(jwks_data)

        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.DecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token header",
            ) from exc

        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing kid header",
            )

        for key in jwk_client_keys.keys:
            if key.key_id == kid:
                return key.key

        # kid not found — maybe keys rotated; clear cache and retry once
        self._jwks_cache.pop("jwks", None)
        jwks_data = self._fetch_jwks()
        jwk_client_keys = jwt.PyJWKSet.from_dict(jwks_data)
        for key in jwk_client_keys.keys:
            if key.key_id == kid:
                return key.key

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signing key not found",
        )

    def validate_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT access token.

        Returns the claims dict on success, or raises HTTPException(401).
        """
        signing_key = self._get_signing_key(token)

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iss", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            ) from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc

        return claims


# Module-level singleton — lazily initialised on first import of get_current_user
jwt_validator = JWTValidator()
