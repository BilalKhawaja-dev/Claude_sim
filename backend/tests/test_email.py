"""Unit tests for the EmailService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.email import EmailError, EmailService, MAX_RETRIES, RETRY_DELAYS


@pytest.fixture
def email_service():
    """Create an EmailService with a mocked SES client."""
    with patch("app.services.email.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        service = EmailService()
        yield service, mock_client


@pytest.mark.asyncio
async def test_send_session_summary_success(email_service):
    """Email sends successfully on first attempt."""
    service, mock_client = email_service
    mock_client.send_email.return_value = {"MessageId": "test-id"}

    await service.send_session_summary(
        summary="Test summary content",
        conversation_title="Test Conversation",
    )

    mock_client.send_email.assert_called_once()
    call_kwargs = mock_client.send_email.call_args
    message = call_kwargs.kwargs.get("Message") or call_kwargs[1].get("Message")
    assert "Test Conversation" in message["Subject"]["Data"]


@pytest.mark.asyncio
async def test_send_session_summary_retry_then_success(email_service):
    """Email fails twice then succeeds on third attempt."""
    service, mock_client = email_service
    error = ClientError(
        {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
        "SendEmail",
    )
    mock_client.send_email.side_effect = [error, error, {"MessageId": "ok"}]

    with patch("app.services.email.asyncio.sleep", new_callable=AsyncMock):
        await service.send_session_summary(
            summary="Retry test", conversation_title="Retry Conv"
        )

    assert mock_client.send_email.call_count == 3


@pytest.mark.asyncio
async def test_send_session_summary_all_retries_fail(email_service):
    """Email fails all 3 attempts and raises EmailError."""
    service, mock_client = email_service
    error = ClientError(
        {"Error": {"Code": "ServiceUnavailable", "Message": "SES down"}},
        "SendEmail",
    )
    mock_client.send_email.side_effect = error

    with patch("app.services.email.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(EmailError, match="Failed to send email after 3 attempts"):
            await service.send_session_summary(
                summary="Fail test", conversation_title="Fail Conv"
            )

    assert mock_client.send_email.call_count == MAX_RETRIES


@pytest.mark.asyncio
async def test_html_formatting(email_service):
    """HTML email body contains the summary and title."""
    service, mock_client = email_service
    mock_client.send_email.return_value = {"MessageId": "test-id"}

    await service.send_session_summary(
        summary="Key topics discussed:\n- Item one\n- Item two",
        conversation_title="My Chat",
    )

    call_args = mock_client.send_email.call_args
    message = call_args.kwargs.get("Message") or call_args[1].get("Message")
    html_body = message["Body"]["Html"]["Data"]
    assert "My Chat" in html_body
    assert "Key topics discussed:" in html_body
    assert "<br>" in html_body  # newlines converted


@pytest.mark.asyncio
async def test_html_escapes_special_chars():
    """HTML formatting escapes <, >, & in user content."""
    html = EmailService._format_html(
        summary="Use <script> & 'alert'",
        conversation_title="Title with <b>bold</b>",
    )
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
    assert "<script>" not in html
    assert "<b>bold</b>" not in html


def test_retry_delays_config():
    """Verify retry delay constants match spec (1s, 2s, 4s)."""
    assert RETRY_DELAYS == [1, 2, 4]
    assert MAX_RETRIES == 3
