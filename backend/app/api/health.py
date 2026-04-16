"""Health check and metrics endpoints.

Validates: Requirements 11.1, 11.2, 11.5
"""

import logging

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db
from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


async def _check_database(db: AsyncSession) -> bool:
    """Check database connectivity by executing a simple query."""
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False


def _check_bedrock() -> bool:
    """Check Bedrock availability by listing foundation models."""
    try:
        client = boto3.client("bedrock", region_name=settings.bedrock_region)
        client.list_foundation_models(byProvider="Anthropic")
        return True
    except (ClientError, Exception):
        logger.exception("Bedrock health check failed")
        return False


@router.get("/api/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Check DB connectivity and Bedrock availability.

    Returns 200 if both are healthy, 503 otherwise.
    """
    db_ok = await _check_database(db)
    bedrock_ok = _check_bedrock()

    healthy = db_ok and bedrock_ok

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if healthy else "unhealthy",
        database=db_ok,
        bedrock=bedrock_ok,
    )
