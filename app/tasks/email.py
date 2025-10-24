"""Email tasks for async email sending."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def send_email(
    self, to_email: str, subject: str, html_content: str, text_content: str | None = None
) -> dict[str, str]:
    """
    Send an email asynchronously.

    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        text_content: Plain text content (optional)

    Returns:
        Dictionary with status and message
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email

        # Add plain text part
        if text_content:
            text_part = MIMEText(text_content, "plain")
            msg.attach(text_part)

        # Add HTML part
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Send email
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        return {"status": "success", "message": f"Email sent to {to_email}"}

    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2**self.request.retries)


@celery_app.task
def send_verification_email(to_email: str, token: str) -> dict[str, str]:
    """Send email verification link."""
    base_url = settings.get_cors_origins()[0]
    verification_link = f"{base_url}/verify-email?token={token}"

    html_content = f"""
    <html>
        <body>
            <h2>Verify Your Email</h2>
            <p>Thank you for registering! Please click the link below to verify your email address:</p>
            <p><a href="{verification_link}">Verify Email</a></p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
    </html>
    """

    text_content = f"Please verify your email by visiting: {verification_link}"

    return send_email(to_email, "Verify Your Email", html_content, text_content)


@celery_app.task
def send_password_reset_email(to_email: str, token: str) -> dict[str, str]:
    """Send password reset link."""
    base_url = settings.get_cors_origins()[0]
    reset_link = f"{base_url}/reset-password?token={token}"

    html_content = f"""
    <html>
        <body>
            <h2>Reset Your Password</h2>
            <p>You requested to reset your password. Click the link below to proceed:</p>
            <p><a href="{reset_link}">Reset Password</a></p>
            <p>If you didn't request this, please ignore this email.</p>
            <p>This link will expire in 1 hour.</p>
        </body>
    </html>
    """

    text_content = f"Reset your password by visiting: {reset_link}"

    return send_email(to_email, "Reset Your Password", html_content, text_content)


@celery_app.task
def send_welcome_email(to_email: str, name: str) -> dict[str, str]:
    """Send welcome email to new users."""
    html_content = f"""
    <html>
        <body>
            <h2>Welcome to {settings.APP_NAME}!</h2>
            <p>Hi {name},</p>
            <p>Thank you for joining us. We're excited to have you on board!</p>
            <p>Get started by exploring our platform and setting up your profile.</p>
        </body>
    </html>
    """

    text_content = f"Welcome to {settings.APP_NAME}, {name}!"

    return send_email(to_email, f"Welcome to {settings.APP_NAME}", html_content, text_content)
