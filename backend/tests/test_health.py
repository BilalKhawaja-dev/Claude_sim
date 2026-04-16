"""Tests for health check endpoint.

Validates: Requirements 11.1, 11.2, 11.5
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.api.health import _check_bedrock, _check_database, health_check
from app.models.schemas import HealthResponse


class TestCheckDatabase:
    """Tests for _check_database helper."""

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self) -> None:
        mock_db = AsyncMock()
        result = await _check_database(mock_db)
        assert result is True
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_exception(self) -> None:
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("connection refused")
        result = await _check_database(mock_db)
        assert result is False


class TestCheckBedrock:
    """Tests for _check_bedrock helper."""

    @patch("app.api.health.boto3")
    def test_returns_true_on_success(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        result = _check_bedrock()
        assert result is True
        mock_client.list_foundation_models.assert_called_once_with(maxResults=1)

    @patch("app.api.health.boto3")
    def test_returns_false_on_client_error(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.list_foundation_models.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "ListFoundationModels"
        )
        mock_boto3.client.return_value = mock_client
        result = _check_bedrock()
        assert result is False

    @patch("app.api.health.boto3")
    def test_returns_false_on_generic_exception(self, mock_boto3: MagicMock) -> None:
        mock_boto3.client.side_effect = Exception("network error")
        result = _check_bedrock()
        assert result is False


class TestHealthCheckEndpoint:
    """Tests for the GET /api/health endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.health._check_bedrock", return_value=True)
    @patch("app.api.health._check_database", new_callable=AsyncMock, return_value=True)
    async def test_returns_healthy_when_all_ok(
        self, mock_db_check: AsyncMock, mock_bedrock_check: MagicMock
    ) -> None:
        mock_db = AsyncMock()
        mock_response = MagicMock()

        result = await health_check(response=mock_response, db=mock_db)

        assert isinstance(result, HealthResponse)
        assert result.status == "healthy"
        assert result.database is True
        assert result.bedrock is True
        # status_code should NOT be set (stays default 200)
        mock_response.status_code.__eq__(200)

    @pytest.mark.asyncio
    @patch("app.api.health._check_bedrock", return_value=False)
    @patch("app.api.health._check_database", new_callable=AsyncMock, return_value=True)
    async def test_returns_unhealthy_when_bedrock_down(
        self, mock_db_check: AsyncMock, mock_bedrock_check: MagicMock
    ) -> None:
        mock_db = AsyncMock()
        mock_response = MagicMock()

        result = await health_check(response=mock_response, db=mock_db)

        assert result.status == "unhealthy"
        assert result.database is True
        assert result.bedrock is False
        assert mock_response.status_code == 503

    @pytest.mark.asyncio
    @patch("app.api.health._check_bedrock", return_value=True)
    @patch("app.api.health._check_database", new_callable=AsyncMock, return_value=False)
    async def test_returns_unhealthy_when_db_down(
        self, mock_db_check: AsyncMock, mock_bedrock_check: MagicMock
    ) -> None:
        mock_db = AsyncMock()
        mock_response = MagicMock()

        result = await health_check(response=mock_response, db=mock_db)

        assert result.status == "unhealthy"
        assert result.database is False
        assert result.bedrock is True
        assert mock_response.status_code == 503

    @pytest.mark.asyncio
    @patch("app.api.health._check_bedrock", return_value=False)
    @patch("app.api.health._check_database", new_callable=AsyncMock, return_value=False)
    async def test_returns_unhealthy_when_both_down(
        self, mock_db_check: AsyncMock, mock_bedrock_check: MagicMock
    ) -> None:
        mock_db = AsyncMock()
        mock_response = MagicMock()

        result = await health_check(response=mock_response, db=mock_db)

        assert result.status == "unhealthy"
        assert result.database is False
        assert result.bedrock is False
        assert mock_response.status_code == 503
