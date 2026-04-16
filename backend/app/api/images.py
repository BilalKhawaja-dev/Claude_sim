"""Image generation and upload validation endpoints.

Validates: Requirements 8.1, 8.2, 8.5, 8.6, 9.1, 9.2, 9.5
"""

import base64
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.core.dependencies import User, get_current_user
from app.models.schemas import ImageGenRequest, ImageGenResponse
from app.services.bedrock import BedrockError, BedrockService

logger = logging.getLogger(__name__)

router = APIRouter()

_bedrock = BedrockService()

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_image_upload(content_type: str | None, size: int) -> None:
    """Validate an uploaded image's format and size.

    Args:
        content_type: The MIME type of the uploaded file.
        size: The file size in bytes.

    Raises:
        HTTPException: 400 if the file format is unsupported or exceeds 5 MB.
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_FILE",
                "message": (
                    f"Unsupported image format: {content_type}. "
                    f"Accepted formats: PNG, JPEG, GIF, WebP."
                ),
            },
        )

    if size > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "INVALID_FILE",
                "message": (
                    f"File size {size} bytes exceeds the 5 MB limit."
                ),
            },
        )


def encode_image_for_bedrock(image_bytes: bytes, media_type: str) -> dict:
    """Encode image bytes as a base64 Bedrock multimodal content block.

    Args:
        image_bytes: Raw image bytes.
        media_type: MIME type of the image.

    Returns:
        A dict suitable for inclusion in an Anthropic messages content array.
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": b64,
        },
    }


@router.post("/api/images/generate", response_model=ImageGenResponse)
async def generate_image(
    request: ImageGenRequest,
    user: User = Depends(get_current_user),
) -> ImageGenResponse:
    """Generate an image via Bedrock Titan Image Generator and return base64 PNG."""
    try:
        image_bytes = await _bedrock.generate_image(request.prompt)
    except BedrockError as exc:
        logger.error("Image generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": exc.error_code,
                "message": exc.message,
            },
        ) from exc

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return ImageGenResponse(image_data=image_b64)


@router.post("/api/images/upload")
async def upload_image(
    file: UploadFile,
    user: User = Depends(get_current_user),
) -> dict:
    """Validate and accept an image upload, returning base64-encoded data.

    This endpoint validates format and size, then returns the image
    as base64 for inclusion in chat messages.
    """
    # Read file content to determine actual size
    content = await file.read()
    validate_image_upload(file.content_type, len(content))

    b64 = base64.b64encode(content).decode("utf-8")
    return {
        "image_data": b64,
        "content_type": file.content_type,
        "size": len(content),
    }
