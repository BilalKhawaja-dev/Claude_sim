# Feature: claude-simulator, Property 16: Email retry with exponential backoff
# Validates: Requirements 6.4
"""
Property-based test verifying that EmailService retries up to 3 times with
exponential backoff on failure, stops retrying after 3 failures (raising
EmailError), and stops retrying immediately on success.

For any email send failure, the Email_Service SHALL retry up to 3 times,
with each retry delay being greater than the previous delay (exponential
backoff pattern). After 3 failures, the operation SHALL stop retrying and
report failure.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.email import EmailError, EmailService, MAX_RETRIES, RETRY_DELAYS

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty summary text
summary_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=300,
).filter(lambda s: s.strip())

# Non-empty conversation title
title_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# The attempt index (0-based) at which the send succeeds.
# 0 = first attempt succeeds, 1 = second attempt succeeds, 2 = third attempt succeeds.
success_attempt_st = st.integers(min_value=0, max_value=MAX_RETRIES - 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ServiceUnavailable", "Message": "SES down"}},
        "SendEmail",
    )


def _create_email_service() -> tuple[EmailService, MagicMock]:
    """Create an EmailService with a mocked SES client."""
    with patch("app.services.email.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        service = EmailService()
    return service, mock_client


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestPropertyEmailRetryExponentialBackoff:
    """**Validates: Requirements 6.4**"""

    @given(summary=summary_st, title=title_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_all_failures_raises_email_error_after_max_retries(
        self, summary: str, title: str
    ) -> None:
        """After MAX_RETRIES failures, the operation SHALL stop retrying and
        report failure by raising EmailError."""
        service, mock_client = _create_email_service()
        mock_client.send_email.side_effect = _make_client_error()

        with patch("app.services.email.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(EmailError):
                await service.send_session_summary(summary, title)

        # Exactly MAX_RETRIES send attempts
        assert mock_client.send_email.call_count == MAX_RETRIES

    @given(summary=summary_st, title=title_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_retry_delays_are_strictly_increasing(
        self, summary: str, title: str
    ) -> None:
        """Each retry delay SHALL be greater than the previous delay
        (exponential backoff pattern)."""
        service, mock_client = _create_email_service()
        mock_client.send_email.side_effect = _make_client_error()

        sleep_delays: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_delays.append(delay)

        with patch("app.services.email.asyncio.sleep", side_effect=capture_sleep):
            with pytest.raises(EmailError):
                await service.send_session_summary(summary, title)

        # There should be (MAX_RETRIES - 1) sleeps (between attempts)
        assert len(sleep_delays) == MAX_RETRIES - 1

        # Each delay must be strictly greater than the previous
        for i in range(1, len(sleep_delays)):
            assert sleep_delays[i] > sleep_delays[i - 1], (
                f"Delay {i} ({sleep_delays[i]}) is not greater than "
                f"delay {i-1} ({sleep_delays[i-1]})"
            )

    @given(summary=summary_st, title=title_st, success_at=success_attempt_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_success_at_any_attempt_stops_retrying(
        self, summary: str, title: str, success_at: int
    ) -> None:
        """On success at any attempt, no further retries SHALL happen."""
        service, mock_client = _create_email_service()

        # Build side effects: fail `success_at` times, then succeed
        side_effects: list = [_make_client_error() for _ in range(success_at)]
        side_effects.append({"MessageId": "ok"})
        mock_client.send_email.side_effect = side_effects

        with patch("app.services.email.asyncio.sleep", new_callable=AsyncMock):
            # Should NOT raise
            await service.send_session_summary(summary, title)

        # Exactly (success_at + 1) attempts: the failures plus the success
        assert mock_client.send_email.call_count == success_at + 1

    @given(summary=summary_st, title=title_st)
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_retry_delays_match_configured_backoff(
        self, summary: str, title: str
    ) -> None:
        """The retry delays SHALL match the configured RETRY_DELAYS constants
        and those constants SHALL exhibit exponential backoff (each > previous)."""
        # Verify the configured constants themselves are strictly increasing
        for i in range(1, len(RETRY_DELAYS)):
            assert RETRY_DELAYS[i] > RETRY_DELAYS[i - 1]

        service, mock_client = _create_email_service()
        mock_client.send_email.side_effect = _make_client_error()

        sleep_delays: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_delays.append(delay)

        with patch("app.services.email.asyncio.sleep", side_effect=capture_sleep):
            with pytest.raises(EmailError):
                await service.send_session_summary(summary, title)

        # Delays used must match the configured RETRY_DELAYS (minus the last
        # attempt which doesn't sleep after failure)
        expected_delays = RETRY_DELAYS[: MAX_RETRIES - 1]
        assert sleep_delays == expected_delays
