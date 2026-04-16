"""Unit tests for JWT validation middleware and get_current_user dependency."""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException

from app.core.auth import JWTValidator
from app.core.dependencies import User, get_current_user


# ---------------------------------------------------------------------------
# Helpers: generate an RSA key pair and build a minimal JWKS response
# ---------------------------------------------------------------------------

def _generate_rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key


def _build_jwks(private_key, kid: str = "test-kid") -> dict:
    """Build a JWKS dict from an RSA private key."""
    from jwt.algorithms import RSAAlgorithm

    public_key = private_key.public_key()
    jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


def _sign_token(private_key, claims: dict, kid: str = "test-kid") -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def rsa_key():
    return _generate_rsa_keypair()


@pytest.fixture()
def jwks(rsa_key):
    return _build_jwks(rsa_key)


@pytest.fixture()
def validator(jwks):
    """JWTValidator with JWKS pre-loaded in cache (no HTTP calls)."""
    v = JWTValidator(
        jwks_url="http://localhost:8080/realms/claude-simulator/protocol/openid-connect/certs",
        issuer="http://localhost:8080/realms/claude-simulator",
        audience="claude-simulator-app",
    )
    v._jwks_cache["jwks"] = jwks
    return v


def _valid_claims(extra: dict | None = None) -> dict:
    now = int(time.time())
    claims = {
        "sub": "user-123",
        "email": "user@example.com",
        "iss": "http://localhost:8080/realms/claude-simulator",
        "aud": "claude-simulator-app",
        "exp": now + 300,
        "iat": now,
    }
    if extra:
        claims.update(extra)
    return claims


# ---------------------------------------------------------------------------
# JWTValidator tests
# ---------------------------------------------------------------------------

class TestJWTValidator:
    def test_valid_token(self, validator, rsa_key):
        token = _sign_token(rsa_key, _valid_claims())
        claims = validator.validate_token(token)
        assert claims["sub"] == "user-123"
        assert claims["email"] == "user@example.com"

    def test_expired_token_returns_401(self, validator, rsa_key):
        expired_claims = _valid_claims({"exp": int(time.time()) - 60})
        token = _sign_token(rsa_key, expired_claims)
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_wrong_issuer_returns_401(self, validator, rsa_key):
        bad_claims = _valid_claims({"iss": "http://evil.example.com"})
        token = _sign_token(rsa_key, bad_claims)
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_token(token)
        assert exc_info.value.status_code == 401

    def test_wrong_audience_returns_401(self, validator, rsa_key):
        bad_claims = _valid_claims({"aud": "wrong-client"})
        token = _sign_token(rsa_key, bad_claims)
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_token(token)
        assert exc_info.value.status_code == 401

    def test_missing_kid_returns_401(self, validator, rsa_key):
        token = jwt.encode(_valid_claims(), rsa_key, algorithm="RS256")
        # Remove kid from header by encoding without headers kwarg — PyJWT
        # still adds kid if the key has one, so we craft manually
        token_no_kid = jwt.encode(
            _valid_claims(), rsa_key, algorithm="RS256", headers={"alg": "RS256"}
        )
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_token(token_no_kid)
        assert exc_info.value.status_code == 401

    def test_unknown_kid_clears_cache_and_retries(self, rsa_key, jwks):
        """When kid doesn't match, validator clears cache and re-fetches JWKS."""
        v = JWTValidator(
            jwks_url="http://localhost:8080/realms/claude-simulator/protocol/openid-connect/certs",
            issuer="http://localhost:8080/realms/claude-simulator",
            audience="claude-simulator-app",
        )
        v._jwks_cache["jwks"] = jwks

        token = _sign_token(rsa_key, _valid_claims(), kid="unknown-kid")

        # The re-fetch will also return the same JWKS (no match), so 401
        with patch("app.core.auth.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = jwks
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            with pytest.raises(HTTPException) as exc_info:
                v.validate_token(token)
            assert exc_info.value.status_code == 401
            assert "Signing key not found" in exc_info.value.detail

    def test_jwks_fetch_failure_returns_401(self):
        v = JWTValidator(
            jwks_url="http://localhost:8080/realms/claude-simulator/protocol/openid-connect/certs",
            issuer="http://localhost:8080/realms/claude-simulator",
            audience="claude-simulator-app",
        )
        with patch("app.core.auth.httpx.get", side_effect=Exception("connection refused")):
            with pytest.raises(HTTPException) as exc_info:
                v.validate_token("some.fake.token")
            assert exc_info.value.status_code == 401

    def test_garbage_token_returns_401(self, validator):
        with pytest.raises(HTTPException) as exc_info:
            validator.validate_token("not-a-jwt")
        assert exc_info.value.status_code == 401

    def test_jwks_caching(self, rsa_key, jwks):
        """Second call should use cached JWKS, not fetch again."""
        v = JWTValidator(
            jwks_url="http://localhost:8080/realms/claude-simulator/protocol/openid-connect/certs",
            issuer="http://localhost:8080/realms/claude-simulator",
            audience="claude-simulator-app",
        )
        with patch("app.core.auth.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = jwks
            mock_resp.raise_for_status = MagicMock()
            mock_get.return_value = mock_resp

            token = _sign_token(rsa_key, _valid_claims())
            v.validate_token(token)
            v.validate_token(token)

            # Only one HTTP call — second used cache
            assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# get_current_user dependency tests
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_valid_bearer_token(self, rsa_key, jwks):
        token = _sign_token(rsa_key, _valid_claims())
        with patch("app.core.dependencies.jwt_validator") as mock_v:
            mock_v.validate_token.return_value = {
                "sub": "user-123",
                "email": "user@example.com",
            }
            user = await get_current_user(f"Bearer {token}")
            assert isinstance(user, User)
            assert user.sub == "user-123"
            assert user.email == "user@example.com"

    @pytest.mark.asyncio
    async def test_missing_bearer_prefix(self):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Token abc123")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_token(self):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Bearer ")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_email_in_claims(self, rsa_key):
        token = _sign_token(rsa_key, _valid_claims())
        with patch("app.core.dependencies.jwt_validator") as mock_v:
            mock_v.validate_token.return_value = {"sub": "user-456"}
            user = await get_current_user(f"Bearer {token}")
            assert user.sub == "user-456"
            assert user.email is None
