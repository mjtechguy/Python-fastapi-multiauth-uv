"""Integration tests for email functionality."""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.email import (
    send_email,
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)


class TestEmailFunctionality:
    """Test email sending and templates."""

    @pytest.fixture
    def mock_smtp(self):
        """Mock SMTP server for email testing."""
        with patch("app.tasks.email.smtplib.SMTP") as mock_smtp_class:
            mock_server = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_server
            yield mock_server

    async def test_send_email_success(self, mock_smtp):
        """Test successful email sending."""
        result = send_email(
            to_email="test@example.com",
            subject="Test Subject",
            html_content="<p>Test HTML</p>",
            text_content="Test Text",
        )

        assert result["status"] == "success"
        assert "test@example.com" in result["message"]

        # Verify SMTP methods were called
        mock_smtp.starttls.assert_called_once()
        mock_smtp.send_message.assert_called_once()

    async def test_send_email_with_auth(self, mock_smtp):
        """Test email sending with SMTP authentication."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.gmail.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user@example.com"
            mock_settings.SMTP_PASSWORD = "password123"
            mock_settings.SMTP_FROM = "noreply@example.com"

            send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

            # Verify login was called with credentials
            mock_smtp.login.assert_called_once_with("user@example.com", "password123")

    async def test_send_email_html_only(self, mock_smtp):
        """Test email with HTML content only (no text)."""
        result = send_email(
            to_email="test@example.com",
            subject="HTML Only",
            html_content="<h1>HTML Email</h1>",
        )

        assert result["status"] == "success"
        mock_smtp.send_message.assert_called_once()

    async def test_send_email_smtp_failure(self, mock_smtp):
        """Test email sending with SMTP failure."""
        mock_smtp.send_message.side_effect = smtplib.SMTPException(
            "SMTP connection failed"
        )

        with pytest.raises(Exception):
            send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

    async def test_send_email_connection_error(self, mock_smtp):
        """Test email sending with connection error."""
        mock_smtp.starttls.side_effect = smtplib.SMTPServerDisconnected(
            "Connection lost"
        )

        with pytest.raises(Exception):
            send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

    async def test_send_verification_email(self, mock_smtp):
        """Test verification email template."""
        token = "test_verification_token_123"

        result = send_verification_email(
            to_email="newuser@example.com", token=token
        )

        assert result["status"] == "success"
        mock_smtp.send_message.assert_called_once()

        # Get the sent message
        sent_message = mock_smtp.send_message.call_args[0][0]

        # Verify email contains verification link
        email_body = str(sent_message)
        assert token in email_body
        assert "verify-email" in email_body.lower()
        assert "Verify" in email_body

    async def test_send_verification_email_content(self, mock_smtp):
        """Test verification email contains required elements."""
        token = "abc123token"

        send_verification_email(to_email="test@example.com", token=token)

        sent_message = mock_smtp.send_message.call_args[0][0]
        email_body = str(sent_message)

        # Check for required content
        assert "Verify Your Email" in email_body
        assert token in email_body
        assert "verify-email?token=" in email_body

        # Should have both HTML and text parts
        assert "text/plain" in email_body or "text/html" in email_body

    async def test_verification_email_uses_base_url_from_settings(self, mock_smtp):
        """
        Regression test: Verify that verification emails use base URL from settings.

        Before fix: Used settings.CORS_ORIGINS[0] (string indexing on comma-separated string)
        After fix: Uses settings.get_cors_origins()[0] (properly parsed list)
        """
        token = "test_token_base_url"

        send_verification_email(to_email="test@example.com", token=token)

        sent_message = mock_smtp.send_message.call_args[0][0]
        email_body = str(sent_message)

        # Should contain the verification URL with base URL from settings
        # After fix, this should work correctly with get_cors_origins()
        assert "verify-email?token=" in email_body
        assert token in email_body

    async def test_send_password_reset_email(self, mock_smtp):
        """Test password reset email template."""
        token = "reset_token_xyz789"

        result = send_password_reset_email(to_email="user@example.com", token=token)

        assert result["status"] == "success"
        mock_smtp.send_message.assert_called_once()

        sent_message = mock_smtp.send_message.call_args[0][0]
        email_body = str(sent_message)

        # Verify email contains reset link
        assert token in email_body
        assert "reset-password" in email_body.lower()
        assert "Reset" in email_body

    async def test_send_password_reset_email_content(self, mock_smtp):
        """Test password reset email contains required elements."""
        token = "reset789"

        send_password_reset_email(to_email="test@example.com", token=token)

        sent_message = mock_smtp.send_message.call_args[0][0]
        email_body = str(sent_message)

        # Check for required content
        assert "Reset Your Password" in email_body
        assert token in email_body
        assert "reset-password?token=" in email_body
        assert "expire" in email_body.lower()  # Should mention expiration

    async def test_password_reset_email_uses_base_url_from_settings(self, mock_smtp):
        """
        Regression test: Verify that password reset emails use base URL from settings.

        Before fix: Used settings.CORS_ORIGINS[0] (string indexing)
        After fix: Uses settings.get_cors_origins()[0] (properly parsed)
        """
        token = "reset_token_base_url"

        send_password_reset_email(to_email="test@example.com", token=token)

        sent_message = mock_smtp.send_message.call_args[0][0]
        email_body = str(sent_message)

        # Should contain the reset URL with base URL from settings
        assert "reset-password?token=" in email_body
        assert token in email_body

    async def test_send_welcome_email(self, mock_smtp):
        """Test welcome email template."""
        result = send_welcome_email(to_email="newuser@example.com", name="John Doe")

        assert result["status"] == "success"
        mock_smtp.send_message.assert_called_once()

        sent_message = mock_smtp.send_message.call_args[0][0]
        email_body = str(sent_message)

        # Verify email contains user name
        assert "John Doe" in email_body
        assert "Welcome" in email_body

    async def test_email_recipients(self, mock_smtp):
        """Test that emails are sent to correct recipients."""
        test_email = "recipient@example.com"

        send_email(
            to_email=test_email,
            subject="Test",
            html_content="<p>Test</p>",
        )

        sent_message = mock_smtp.send_message.call_args[0][0]
        assert sent_message["To"] == test_email

    async def test_email_subject_lines(self, mock_smtp):
        """Test that email subject lines are correctly set."""
        custom_subject = "Custom Test Subject Line"

        send_email(
            to_email="test@example.com",
            subject=custom_subject,
            html_content="<p>Test</p>",
        )

        sent_message = mock_smtp.send_message.call_args[0][0]
        assert sent_message["Subject"] == custom_subject

    async def test_email_from_address(self, mock_smtp):
        """Test that emails have correct FROM address."""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SMTP_FROM = "noreply@mycompany.com"
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_PORT = 587

            send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>",
            )

            sent_message = mock_smtp.send_message.call_args[0][0]
            assert sent_message["From"] == "noreply@mycompany.com"

    async def test_multiple_emails_sent(self, mock_smtp):
        """Test sending multiple emails in sequence."""
        emails = [
            "user1@example.com",
            "user2@example.com",
            "user3@example.com",
        ]

        for email in emails:
            send_email(
                to_email=email,
                subject="Bulk Test",
                html_content="<p>Test</p>",
            )

        # Verify all emails were sent
        assert mock_smtp.send_message.call_count == 3

    async def test_email_html_escaping(self, mock_smtp):
        """Test that HTML content is properly handled."""
        html_with_special_chars = """
        <html>
            <body>
                <h1>Test & Verification</h1>
                <p>Price: $100 < $200</p>
                <p>Quote: "Hello"</p>
            </body>
        </html>
        """

        result = send_email(
            to_email="test@example.com",
            subject="HTML Test",
            html_content=html_with_special_chars,
        )

        assert result["status"] == "success"

    async def test_email_with_unicode_characters(self, mock_smtp):
        """Test emails with unicode characters."""
        unicode_content = """
        <html>
            <body>
                <p>Héllo Wörld! 你好 🎉</p>
            </body>
        </html>
        """

        result = send_email(
            to_email="test@example.com",
            subject="Ünicode Tëst ✨",
            html_content=unicode_content,
        )

        assert result["status"] == "success"

    async def test_verification_email_token_uniqueness(self, mock_smtp):
        """Test that verification emails include unique tokens."""
        token1 = "token_abc_123"
        token2 = "token_xyz_789"

        send_verification_email(to_email="user1@example.com", token=token1)
        send_verification_email(to_email="user2@example.com", token=token2)

        # Get both sent messages
        call1 = mock_smtp.send_message.call_args_list[0][0][0]
        call2 = mock_smtp.send_message.call_args_list[1][0][0]

        email1_body = str(call1)
        email2_body = str(call2)

        # Each email should contain its own token
        assert token1 in email1_body
        assert token1 not in email2_body
        assert token2 in email2_body
        assert token2 not in email1_body

    async def test_password_reset_email_token_uniqueness(self, mock_smtp):
        """Test that password reset emails include unique tokens."""
        token1 = "reset_token_1"
        token2 = "reset_token_2"

        send_password_reset_email(to_email="user1@example.com", token=token1)
        send_password_reset_email(to_email="user2@example.com", token=token2)

        call1 = mock_smtp.send_message.call_args_list[0][0][0]
        call2 = mock_smtp.send_message.call_args_list[1][0][0]

        email1_body = str(call1)
        email2_body = str(call2)

        assert token1 in email1_body
        assert token2 in email2_body


class TestEmailWithRealCredentials:
    """
    Optional tests that use real SMTP credentials.

    These tests are skipped by default and only run when SMTP settings are configured.
    To run these tests, ensure your .env file has valid SMTP credentials.
    """

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-email-tests", default=False),
        reason="Real email tests require --run-email-tests flag",
    )
    async def test_send_real_verification_email(self):
        """
        Test sending a real verification email.

        To run: pytest tests/integration/test_email.py --run-email-tests

        NOTE: This requires valid SMTP credentials in your .env file.
        """
        from app.core.config import settings

        # Only run if SMTP is configured
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            pytest.skip("SMTP not configured")

        token = "test_token_real_email"
        test_recipient = settings.SMTP_USER  # Send to yourself

        result = send_verification_email(to_email=test_recipient, token=token)

        assert result["status"] == "success"

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-email-tests", default=False),
        reason="Real email tests require --run-email-tests flag",
    )
    async def test_send_real_password_reset_email(self):
        """
        Test sending a real password reset email.

        To run: pytest tests/integration/test_email.py --run-email-tests
        """
        from app.core.config import settings

        if not settings.SMTP_HOST or not settings.SMTP_USER:
            pytest.skip("SMTP not configured")

        token = "test_reset_token_real"
        test_recipient = settings.SMTP_USER

        result = send_password_reset_email(to_email=test_recipient, token=token)

        assert result["status"] == "success"


def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--run-email-tests",
        action="store_true",
        default=False,
        help="Run tests that send real emails (requires SMTP credentials)",
    )
