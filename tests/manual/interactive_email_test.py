#!/usr/bin/env python3
"""
Interactive Email Delivery Tester

This script guides you through testing all email functionality including:
- Verification emails
- Password reset emails
- Welcome emails
- Notification emails

Usage:
    python tests/manual/interactive_email_test.py [--email your@email.com]
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

console = Console()


class EmailTester:
    """Interactive email delivery tester."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.test_email = None
        self.access_token = None

    def log_result(self, test_name: str, status: str, message: str, details: dict | None = None):
        """Log test result."""
        self.results.append({
            "test": test_name,
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat(),
        })

    async def check_server(self) -> bool:
        """Check if server is running."""
        console.print("\n[bold blue]Step 1:[/bold blue] Checking if server is running...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/health")
                if response.status_code == 200:
                    console.print("[green]✓[/green] Server is running!")
                    self.log_result("Server Check", "PASS", "Server is accessible")
                    return True
        except Exception as e:
            console.print(f"[red]✗[/red] Cannot connect to server: {e}")
            self.log_result("Server Check", "FAIL", str(e))
            return False

    def check_smtp_config(self) -> bool:
        """Check SMTP configuration."""
        console.print("\n[bold blue]Step 2:[/bold blue] Checking SMTP configuration...")

        required_vars = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL"]
        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            console.print(f"[yellow]⚠[/yellow] Missing SMTP configuration: {', '.join(missing)}")
            console.print("\n[yellow]For testing, you can use:[/yellow]")
            console.print("  - Gmail: smtp.gmail.com:587 (requires app password)")
            console.print("  - Mailtrap: smtp.mailtrap.io:2525 (for testing)")
            console.print("  - SendGrid: smtp.sendgrid.net:587")

            use_mock = Confirm.ask("\nContinue with mock email (no actual delivery)?", default=True)
            if use_mock:
                console.print("[yellow]Running in MOCK mode - emails won't be delivered[/yellow]")
                self.log_result("SMTP Config", "SKIP", "Using mock mode")
                return True
            self.log_result("SMTP Config", "FAIL", f"Missing: {missing}")
            return False

        console.print("[green]✓[/green] SMTP configured!")
        self.log_result("SMTP Config", "PASS", "All variables present")
        return True

    async def test_verification_email(self):
        """Test email verification flow."""
        console.print("\n[bold blue]Test 1:[/bold blue] Email Verification")

        # Register new user
        test_email = self.test_email or Prompt.ask("\nEnter email to test", default="test@example.com")
        self.test_email = test_email

        console.print(f"\n[yellow]Registering user: {test_email}[/yellow]")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/register",
                    json={
                        "email": test_email,
                        "password": "TestPassword123!",
                        "full_name": "Test User",
                    }
                )

                if response.status_code in [200, 201]:
                    console.print("[green]✓[/green] User registered!")
                    data = response.json()

                    # Ask user to check email
                    panel = Panel(
                        f"""[bold yellow]MANUAL VERIFICATION:[/bold yellow]

1. Check your inbox at: [blue]{test_email}[/blue]

2. Look for email with subject: [bold]"Verify Your Email"[/bold]

3. Verify you received the email

4. Check that the email contains:
   - Welcome message
   - Verification link/token
   - Professional formatting
   - Correct sender info

5. Click the verification link (or copy the token)
""",
                        title="📧 Email Verification",
                        border_style="yellow"
                    )
                    console.print(panel)

                    received = Prompt.ask(
                        "\nDid you receive the verification email?",
                        choices=["yes", "no"],
                        default="no"
                    )

                    if received == "yes":
                        self.log_result("Verification Email", "PASS", "Email received")

                        # Test verification
                        token = Prompt.ask("\nEnter verification token from email")
                        verify_response = await client.get(
                            f"{self.base_url}/api/v1/auth/verify-email",
                            params={"token": token}
                        )

                        if verify_response.status_code == 200:
                            console.print("[green]✓[/green] Email verified successfully!")
                            self.log_result("Email Verification", "PASS", "Verification successful")
                        else:
                            console.print(f"[red]✗[/red] Verification failed: {verify_response.status_code}")
                            self.log_result("Email Verification", "FAIL", "Verification failed")
                    else:
                        self.log_result("Verification Email", "FAIL", "Email not received")
                        console.print("[red]✗[/red] Email not received - check SMTP config")

                elif response.status_code == 400 and "already registered" in response.text.lower():
                    console.print("[yellow]⚠[/yellow] Email already registered - skipping registration test")
                    self.log_result("Verification Email", "SKIP", "Email already registered")
                else:
                    console.print(f"[red]✗[/red] Registration failed: {response.status_code}")
                    self.log_result("Verification Email", "FAIL", f"Status {response.status_code}")

        except Exception as e:
            console.print(f"[red]✗[/red] Error: {e}")
            self.log_result("Verification Email", "FAIL", str(e))

    async def test_password_reset_email(self):
        """Test password reset email."""
        console.print("\n[bold blue]Test 2:[/bold blue] Password Reset Email")

        test_email = self.test_email or Prompt.ask("\nEnter email to test", default="test@example.com")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/forgot-password",
                    json={"email": test_email}
                )

                if response.status_code == 200:
                    console.print("[green]✓[/green] Password reset requested!")

                    panel = Panel(
                        f"""[bold yellow]MANUAL VERIFICATION:[/bold yellow]

1. Check your inbox at: [blue]{test_email}[/blue]

2. Look for email with subject: [bold]"Reset Your Password"[/bold]

3. Verify email contains:
   - Clear instructions
   - Reset link/token
   - Security notice
   - Expiration info

4. Click the reset link
""",
                        title="🔒 Password Reset",
                        border_style="yellow"
                    )
                    console.print(panel)

                    received = Prompt.ask(
                        "\nDid you receive the password reset email?",
                        choices=["yes", "no"],
                        default="no"
                    )

                    if received == "yes":
                        self.log_result("Password Reset Email", "PASS", "Email received")

                        # Test reset
                        token = Prompt.ask("\nEnter reset token from email")
                        new_password = "NewPassword123!"

                        reset_response = await client.post(
                            f"{self.base_url}/api/v1/auth/reset-password",
                            json={
                                "token": token,
                                "new_password": new_password
                            }
                        )

                        if reset_response.status_code == 200:
                            console.print("[green]✓[/green] Password reset successful!")
                            self.log_result("Password Reset", "PASS", "Reset successful")
                        else:
                            console.print(f"[red]✗[/red] Reset failed: {reset_response.status_code}")
                            self.log_result("Password Reset", "FAIL", "Reset failed")
                    else:
                        self.log_result("Password Reset Email", "FAIL", "Email not received")

        except Exception as e:
            console.print(f"[red]✗[/red] Error: {e}")
            self.log_result("Password Reset Email", "FAIL", str(e))

    async def test_welcome_email(self):
        """Test welcome email (if implemented)."""
        console.print("\n[bold blue]Test 3:[/bold blue] Welcome Email")

        console.print("[yellow]Creating new user to trigger welcome email...[/yellow]")

        new_email = f"welcome_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/register",
                    json={
                        "email": new_email,
                        "password": "TestPassword123!",
                        "full_name": "Welcome Test User",
                    }
                )

                if response.status_code in [200, 201]:
                    panel = Panel(
                        f"""[bold yellow]MANUAL VERIFICATION:[/bold yellow]

1. Check inbox for: [blue]{new_email}[/blue]

2. Look for welcome email with:
   - Friendly greeting
   - Getting started guide
   - Key features overview
   - Support links

Note: Welcome emails may not be implemented yet.
That's okay - this is just to verify if they exist.
""",
                        title="👋 Welcome Email",
                        border_style="yellow"
                    )
                    console.print(panel)

                    received = Prompt.ask(
                        "\nDid you receive a welcome email (separate from verification)?",
                        choices=["yes", "no", "skip"],
                        default="skip"
                    )

                    if received == "yes":
                        self.log_result("Welcome Email", "PASS", "Email received")
                    elif received == "no":
                        self.log_result("Welcome Email", "FAIL", "Email not received")
                    else:
                        self.log_result("Welcome Email", "SKIP", "Not implemented or skipped")

        except Exception as e:
            console.print(f"[red]✗[/red] Error: {e}")
            self.log_result("Welcome Email", "FAIL", str(e))

    async def test_notification_email(self):
        """Test notification emails."""
        console.print("\n[bold blue]Test 4:[/bold blue] Notification Emails")

        console.print("[yellow]Testing notification email delivery...[/yellow]")
        console.print("\n[bold]Note:[/bold] This tests if the system CAN send notification emails.")
        console.print("Actual notification triggers (new invitation, etc.) should be tested separately.\n")

        result = Prompt.ask(
            "Have you tested notification emails in your application?",
            choices=["yes", "no", "skip"],
            default="skip"
        )

        if result == "yes":
            self.log_result("Notification Emails", "PASS", "Manual verification passed")
        elif result == "no":
            self.log_result("Notification Emails", "FAIL", "Manual verification failed")
        else:
            self.log_result("Notification Emails", "SKIP", "Not tested")

    def test_email_formatting(self):
        """Test email formatting and appearance."""
        console.print("\n[bold blue]Test 5:[/bold blue] Email Formatting & Appearance")

        panel = Panel(
            """[bold yellow]MANUAL CHECKLIST:[/bold yellow]

Review all emails you received and verify:

1. ✓ Professional sender name
2. ✓ Correct "From" address
3. ✓ Clear subject lines
4. ✓ Proper HTML formatting
5. ✓ Mobile-responsive design
6. ✓ No broken images
7. ✓ Links work correctly
8. ✓ Unsubscribe link (if applicable)
9. ✓ Footer with company info
10. ✓ Consistent branding
""",
            title="📋 Email Quality Checklist",
            border_style="yellow"
        )
        console.print(panel)

        quality_rating = Prompt.ask(
            "\nHow would you rate the email quality?",
            choices=["excellent", "good", "needs-improvement", "poor"],
            default="good"
        )

        if quality_rating in ["excellent", "good"]:
            self.log_result("Email Formatting", "PASS", f"Quality: {quality_rating}")
        else:
            self.log_result("Email Formatting", "FAIL", f"Quality: {quality_rating}")

    def generate_report(self):
        """Generate test report."""
        console.print("\n" + "="*70)
        console.print("[bold]Email Test Results Summary[/bold]")
        console.print("="*70)

        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")

        table = Table()
        table.add_column("Test", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Message", style="white")

        for result in self.results:
            status_map = {"PASS": "green", "FAIL": "red", "SKIP": "yellow"}
            status_color = status_map.get(result["status"], "white")
            table.add_row(
                result["test"],
                f"[{status_color}]{result['status']}[/{status_color}]",
                result["message"]
            )

        console.print(table)
        console.print(f"\n[bold]Total:[/bold] {len(self.results)} tests")
        console.print(f"[green]Passed:[/green] {passed}")
        console.print(f"[red]Failed:[/red] {failed}")
        console.print(f"[yellow]Skipped:[/yellow] {skipped}")

        # Save report
        report_file = f"email_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "results": self.results,
                "summary": {
                    "total": len(self.results),
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                },
                "timestamp": datetime.now().isoformat(),
            }, f, indent=2)

        console.print(f"\n[green]✓[/green] Detailed report saved to: {report_file}")

    async def run(self, test_email: str | None = None):
        """Run the interactive email test."""
        console.print(Panel.fit(
            "[bold cyan]Interactive Email Delivery Test[/bold cyan]\n"
            "This will guide you through testing all email functionality",
            border_style="cyan"
        ))

        self.test_email = test_email

        # Check server
        if not await self.check_server():
            return

        # Check SMTP
        if not self.check_smtp_config():
            return

        # Run tests
        await self.test_verification_email()
        await self.test_password_reset_email()
        await self.test_welcome_email()
        await self.test_notification_email()
        self.test_email_formatting()

        # Generate report
        self.generate_report()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Interactive Email Delivery Tester")
    parser.add_argument(
        "--email",
        help="Email address to use for testing"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API"
    )

    args = parser.parse_args()

    tester = EmailTester(base_url=args.base_url)
    await tester.run(test_email=args.email)


if __name__ == "__main__":
    asyncio.run(main())
