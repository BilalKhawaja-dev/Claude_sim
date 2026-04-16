"""SES email service for sending session summary emails with retry logic."""

import asyncio
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Retry delays in seconds for exponential backoff
RETRY_DELAYS = [1, 2, 4]
MAX_RETRIES = 3


class EmailError(Exception):
    """Raised when email sending fails after all retries."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class EmailService:
    """Send HTML emails via AWS SES with retry and exponential backoff."""

    def __init__(self) -> None:
        self._client = boto3.client(
            "ses",
            region_name=settings.ses_region,
        )

    async def send_session_summary(
        self, summary: str, conversation_title: str
    ) -> None:
        """Send an HTML email with the session summary via SES.

        Retries up to 3 times with exponential backoff (1s, 2s, 4s) on failure.

        Args:
            summary: The plain-text summary content.
            conversation_title: Title of the conversation for the email subject.

        Raises:
            EmailError: If sending fails after all retry attempts.
        """
        subject = f"Session Summary: {conversation_title}"
        html_body = self._format_html(summary, conversation_title)

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                await self._send_email(subject, html_body)
                logger.info(
                    "Session summary email sent for '%s' on attempt %d",
                    conversation_title,
                    attempt + 1,
                )
                return
            except ClientError as exc:
                last_error = exc
                logger.warning(
                    "SES send failed for '%s' (attempt %d/%d): %s",
                    conversation_title,
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    await asyncio.sleep(delay)

        raise EmailError(
            f"Failed to send email after {MAX_RETRIES} attempts: {last_error}"
        )

    async def _send_email(self, subject: str, html_body: str) -> None:
        """Send a single email via SES. Runs the blocking boto3 call in a thread.

        Args:
            subject: Email subject line.
            html_body: HTML content of the email.

        Raises:
            ClientError: On SES API failure.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.send_email(
                Source=settings.ses_sender_email,
                Destination={"ToAddresses": [settings.ses_recipient_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            ),
        )

    @staticmethod
    def _format_html(summary: str, conversation_title: str) -> str:
        """Format the summary as a styled HTML email body.

        Args:
            summary: Plain-text summary content.
            conversation_title: Title shown in the email header.

        Returns:
            An HTML string for the email body.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        # Escape basic HTML entities in user content
        safe_title = (
            conversation_title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        safe_summary = (
            summary.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

        return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
  <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 24px; border-radius: 12px 12px 0 0;">
    <h1 style="color: #fff; margin: 0; font-size: 20px;">Claude Simulator</h1>
    <p style="color: #e0e7ff; margin: 8px 0 0; font-size: 14px;">Session Summary</p>
  </div>
  <div style="background: #fff; border: 1px solid #e5e7eb; border-top: none; padding: 24px; border-radius: 0 0 12px 12px;">
    <h2 style="margin: 0 0 8px; font-size: 16px; color: #1f2937;">{safe_title}</h2>
    <p style="margin: 0 0 16px; font-size: 12px; color: #6b7280;">{timestamp}</p>
    <div style="background: #f9fafb; border-radius: 8px; padding: 16px; line-height: 1.6; font-size: 14px;">
      {safe_summary}
    </div>
  </div>
  <p style="text-align: center; font-size: 11px; color: #9ca3af; margin-top: 16px;">
    Sent by Claude Simulator &middot; Automated session summary
  </p>
</body>
</html>"""
