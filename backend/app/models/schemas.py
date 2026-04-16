"""Pydantic request/response schemas for Claude Simulator API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ModelChoice(str, Enum):
    """Available model choices for chat inference."""

    SONNET = "sonnet"
    OPUS = "opus"


# --- Chat ---


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""

    message: str = Field(..., min_length=1)
    conversation_id: str
    model: ModelChoice = ModelChoice.SONNET
    image: str | None = None  # base64 encoded


# --- Conversations ---


class ConversationSummary(BaseModel):
    """Summary of a conversation for list views."""

    id: str
    title: str | None
    updated_at: datetime


class MessageResponse(BaseModel):
    """A single message within a conversation."""

    id: str
    role: str
    content: str
    has_image: bool
    created_at: datetime


class ConversationDetail(BaseModel):
    """Full conversation with message history."""

    id: str
    title: str | None
    messages: list[MessageResponse]


# --- Memory ---


class MemoryCreateRequest(BaseModel):
    """Request body for creating a user memory entry."""

    content: str = Field(..., min_length=1)


class MemoryUpdateRequest(BaseModel):
    """Request body for updating a user memory entry."""

    content: str = Field(..., min_length=1)


class UserMemoryEntry(BaseModel):
    """A user memory entry returned from the API."""

    id: str
    content: str
    created_at: datetime
    updated_at: datetime


# --- Images ---


class ImageGenRequest(BaseModel):
    """Request body for image generation."""

    prompt: str = Field(..., min_length=1)


class ImageGenResponse(BaseModel):
    """Response body for image generation."""

    image_data: str  # base64 PNG


# --- Health ---


class HealthResponse(BaseModel):
    """Response body for health check endpoint."""

    status: str
    database: bool
    bedrock: bool


# --- Errors ---


class ErrorResponse(BaseModel):
    """Structured error response for API errors."""

    error_code: str
    message: str
    details: dict | None = None
