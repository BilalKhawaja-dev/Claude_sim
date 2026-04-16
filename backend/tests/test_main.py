"""Unit tests for the main application entry point.

Tests auth middleware, startup/shutdown lifecycle, and background task management.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from httpx import ASGITransport, AsyncClient

from app.main import app, _PUBLIC_PATHS, _background_tasks


# ---------------------------------------------------------------------------
# Auth middleware tests
# ---------------------------------------------------------------------------

class TestAuthMiddleware:
    """Test JWT auth middleware on protected and public routes."""

    @pytest.mark.asyncio
    async def test_public_health_endpoint_no_auth_required(self):
        """GET /api/health should be accessible without auth."""
        with patch("app.api.health._check_database", new_callable=AsyncMock, return_value=True), \
             patch("app.api.health._check_bedrock", return_value=True):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_public_metrics_endpoint_no_auth_required(self):
        """GET /metrics should be accessible without auth."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/metrics")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_public_docs_endpoint_no_auth_required(self):
        """GET /docs should be accessible without auth."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/docs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_endpoint_returns_401_without_token(self):
        """Protected endpoints should return 401 when no auth header is sent."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/conversations")
        assert resp.status_code == 401
        assert "authorization" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_protected_endpoint_returns_401_with_invalid_token(self):
        """Protected endpoints should return 401 for an invalid JWT."""
        with patch("app.main.jwt_validator") as mock_validator:
            mock_validator.validate_token.side_effect = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/conversations",
                    headers={"Authorization": "Bearer bad.token.here"},
                )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_passes_with_valid_token(self):
        """Protected endpoints should pass auth middleware with a valid JWT.

        We mock both the middleware-level and dependency-level validators,
        plus the DB session to avoid needing a real database.
        """
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

        with patch("app.main.jwt_validator") as mock_validator, \
             patch("app.core.dependencies.jwt_validator") as mock_dep_validator, \
             patch("app.core.dependencies.async_session_factory") as mock_factory:
            mock_validator.validate_token.return_value = {
                "sub": "user-1",
                "email": "u@example.com",
            }
            mock_dep_validator.validate_token.return_value = {
                "sub": "user-1",
                "email": "u@example.com",
            }
            # Mock the DB session context manager
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/conversations",
                    headers={"Authorization": "Bearer valid.jwt.token"},
                )
            # Should NOT be 401 — auth middleware passed
            assert resp.status_code != 401

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_returns_401(self):
        """Auth header with wrong scheme (e.g. 'Token') should be rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/conversations",
                headers={"Authorization": "Token some-token"},
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_token_returns_401(self):
        """Bearer with empty token should be rejected."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/conversations",
                headers={"Authorization": "Bearer "},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Lifespan / background task tests
# ---------------------------------------------------------------------------

class TestLifecycle:
    """Test startup and shutdown lifecycle behaviour."""

    @pytest.mark.asyncio
    async def test_background_tasks_created_on_startup(self):
        """The lifespan should create idle-checker and expiry-job tasks."""
        from app.main import lifespan

        _background_tasks.clear()

        mock_conn = AsyncMock()
        mock_engine = AsyncMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        with patch("app.main.engine", mock_engine):
            async with lifespan(app):
                assert len(_background_tasks) == 2
                task_names = {t.get_name() for t in _background_tasks}
                assert "idle-checker" in task_names
                assert "expiry-job" in task_names

        # After exiting lifespan, tasks should be cleared
        assert len(_background_tasks) == 0

    @pytest.mark.asyncio
    async def test_shutdown_disposes_engine(self):
        """The lifespan shutdown should dispose the DB engine."""
        from app.main import lifespan

        _background_tasks.clear()

        mock_conn = AsyncMock()
        mock_engine = AsyncMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        with patch("app.main.engine", mock_engine):
            async with lifespan(app):
                pass  # startup runs

        # engine.dispose() should have been called during shutdown
        mock_engine.dispose.assert_awaited_once()
