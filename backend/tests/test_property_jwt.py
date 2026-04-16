# Feature: claude-simulator, Property 23: JWT validation on every request
# Validates: Requirements 10.4, 10.5
"""
Property-based tests verifying that JWT validation correctly accepts valid
tokens and rejects expired or invalid tokens with 401 responses.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from jwt.algorithms import RSAAlgorithm

from app.core.auth import JWTValidator


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_auth.py)
# ---------------------------------------------------------------------------

ISSUER = "http://localhost:8080/realms/claude-simulator"
AUDIENCE = "claude-simulator-app"
KID = "test-kid"


def _generate_rsa_keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _build_jwks(private_key, kid: str = KID) -> dict:
    public_key = private_key.public_key()
    jwk = RSAAlgorithm.to_jwk(public_key, as_dict=True)
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return {"keys": [jwk]}


def _sign_token(private_key, claims: dict, kid: str = KID) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def _make_validator(jwks: dict) -> JWTValidator:
    v = JWTValidator(
        jwks_url="http://localhost:8080/realms/claude-simulator/protocol/openid-connect/certs",
        issuer=ISSUER,
        audience=AUDIENCE,
    )
    v._jwks_cache["jwks"] = jwks
    return v


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Generate plausible subject identifiers
sub_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-_"),
    min_size=1,
    max_size=64,
)

# Generate plausible email addresses
email_strategy = st.from_regex(
    r"[a-z][a-z0-9]{0,15}@[a-z]{2,10}\.[a-z]{2,4}", fullmatch=True
)

# Expiry offset in seconds from now (positive = future = valid)
valid_exp_offset = st.integers(min_value=30, max_value=3600)

# Expiry offset in seconds from now (negative = past = expired)
expired_exp_offset = st.integers(min_value=60, max_value=86400)

# Invalid issuer strings that differ from the expected issuer
invalid_issuer_strategy = st.text(min_size=5, max_size=100).filter(
    lambda s: s != ISSUER
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestJWTValidationProperty:
    """Property 23: JWT validation on every request."""

    @settings(max_examples=100, deadline=None)
    @given(
        sub=sub_strategy,
        email=email_strategy,
        exp_offset=valid_exp_offset,
    )
    def test_valid_tokens_grant_access(
        self, sub: str, email: str, exp_offset: int
    ) -> None:
        """**Validates: Requirements 10.4, 10.5**

        For any request with a valid JWT (correct issuer, audience, non-expired),
        the validator SHALL decode the token and return the claims, granting access.
        """
        private_key = _generate_rsa_keypair()
        jwks = _build_jwks(private_key)
        validator = _make_validator(jwks)

        now = int(time.time())
        claims = {
            "sub": sub,
            "email": email,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": now + exp_offset,
            "iat": now,
        }
        token = _sign_token(private_key, claims)

        result = validator.validate_token(token)
        assert result["sub"] == sub
        assert result["email"] == email

    @settings(max_examples=100, deadline=None)
    @given(
        sub=sub_strategy,
        exp_offset=expired_exp_offset,
    )
    def test_expired_tokens_return_401(
        self, sub: str, exp_offset: int
    ) -> None:
        """**Validates: Requirements 10.4, 10.5**

        For any request with an expired JWT (exp in the past), the validator
        SHALL raise an HTTPException with status code 401.
        """
        private_key = _generate_rsa_keypair()
        jwks = _build_jwks(private_key)
        validator = _make_validator(jwks)

        now = int(time.time())
        claims = {
            "sub": sub,
            "email": f"{sub}@test.com",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": now - exp_offset,  # in the past
            "iat": now - exp_offset - 300,
        }
        token = _sign_token(private_key, claims)

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_token(token)
        assert exc_info.value.status_code == 401

    @settings(max_examples=100, deadline=None)
    @given(
        sub=sub_strategy,
        bad_issuer=invalid_issuer_strategy,
    )
    def test_invalid_issuer_returns_401(
        self, sub: str, bad_issuer: str
    ) -> None:
        """**Validates: Requirements 10.4, 10.5**

        For any request with a JWT signed by a valid key but containing an
        incorrect issuer, the validator SHALL raise an HTTPException with
        status code 401.
        """
        private_key = _generate_rsa_keypair()
        jwks = _build_jwks(private_key)
        validator = _make_validator(jwks)

        now = int(time.time())
        claims = {
            "sub": sub,
            "email": f"{sub}@test.com",
            "iss": bad_issuer,  # wrong issuer
            "aud": AUDIENCE,
            "exp": now + 300,
            "iat": now,
        }
        token = _sign_token(private_key, claims)

        with pytest.raises(HTTPException) as exc_info:
            validator.validate_token(token)
        assert exc_info.value.status_code == 401
