#!/usr/bin/env python3
"""
Interactive OAuth Flow Tester

This script guides you through testing OAuth authentication with Google, GitHub, and Microsoft.
It automates the setup and provides step-by-step instructions for manual validation.

Usage:
    python tests/manual/interactive_oauth_test.py [--provider google|github|microsoft]
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


class OAuthTester:
    """Interactive OAuth flow tester."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.session_data = {}

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
                console.print(f"[red]✗[/red] Server returned status {response.status_code}")
                self.log_result("Server Check", "FAIL", f"Status {response.status_code}")
                return False
        except Exception as e:
            console.print(f"[red]✗[/red] Cannot connect to server: {e}")
            console.print("\n[yellow]Please start the server:[/yellow]")
            console.print("  uvicorn app.main:app --reload")
            self.log_result("Server Check", "FAIL", str(e))
            return False

    def check_env_variables(self, provider: str) -> bool:
        """Check if OAuth credentials are configured."""
        console.print(f"\n[bold blue]Step 2:[/bold blue] Checking {provider.upper()} OAuth configuration...")

        required_vars = {
            "google": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"],
            "github": ["GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET"],
            "microsoft": ["MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"],
        }

        missing = []
        for var in required_vars.get(provider, []):
            if not os.getenv(var):
                missing.append(var)

        if missing:
            console.print(f"[red]✗[/red] Missing environment variables: {', '.join(missing)}")
            console.print("\n[yellow]Add to your .env file:[/yellow]")
            for var in missing:
                console.print(f"  {var}=your_{var.lower()}_here")
            self.log_result(f"{provider} OAuth Config", "FAIL", f"Missing: {missing}")
            return False

        console.print(f"[green]✓[/green] {provider.upper()} credentials configured!")
        self.log_result(f"{provider} OAuth Config", "PASS", "All variables present")
        return True

    async def get_oauth_url(self, provider: str) -> str | None:
        """Get OAuth authorization URL."""
        console.print(f"\n[bold blue]Step 3:[/bold blue] Getting {provider.upper()} OAuth URL...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/auth/oauth/{provider}/authorize"
                )

                if response.status_code == 200:
                    data = response.json()
                    auth_url = data.get("authorization_url")
                    console.print("[green]✓[/green] Got authorization URL")
                    self.log_result(f"{provider} OAuth URL", "PASS", "URL retrieved")
                    return auth_url
                console.print(f"[red]✗[/red] Failed to get OAuth URL: {response.status_code}")
                console.print(response.text)
                self.log_result(f"{provider} OAuth URL", "FAIL", response.text)
                return None
        except Exception as e:
            console.print(f"[red]✗[/red] Error: {e}")
            self.log_result(f"{provider} OAuth URL", "FAIL", str(e))
            return None

    def manual_oauth_flow(self, provider: str, auth_url: str):
        """Guide user through manual OAuth flow."""
        console.print(f"\n[bold blue]Step 4:[/bold blue] Manual {provider.upper()} OAuth Flow")

        panel = Panel(
            f"""[bold yellow]MANUAL STEPS:[/bold yellow]

1. Open this URL in your browser:
   [blue]{auth_url}[/blue]

2. Sign in with your {provider.title()} account

3. Authorize the application

4. You will be redirected to: http://localhost:8000/auth/callback

5. Copy the FULL callback URL from your browser
   (including the 'code' parameter)

[bold]Example callback URL:[/bold]
http://localhost:8000/auth/callback?code=abc123&state=xyz789
""",
            title=f"🔐 {provider.upper()} OAuth Flow",
            border_style="yellow"
        )
        console.print(panel)

    async def process_callback(self, provider: str, callback_url: str) -> bool:
        """Process OAuth callback."""
        console.print("\n[bold blue]Step 5:[/bold blue] Processing callback...")

        # Extract code from callback URL
        try:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(callback_url)
            params = parse_qs(parsed.query)
            code = params.get('code', [None])[0]
            state = params.get('state', [None])[0]

            if not code:
                console.print("[red]✗[/red] No authorization code in callback URL")
                self.log_result(f"{provider} Callback", "FAIL", "Missing code")
                return False

            console.print(f"[green]✓[/green] Extracted code: {code[:20]}...")

            # Exchange code for tokens
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/auth/oauth/{provider}/callback",
                    params={"code": code, "state": state} if state else {"code": code},
                    follow_redirects=False
                )

                if response.status_code in [200, 302]:
                    console.print("[green]✓[/green] OAuth callback successful!")

                    # Try to get tokens from response
                    if response.status_code == 200:
                        data = response.json()
                        self.session_data["access_token"] = data.get("access_token")
                        self.session_data["user"] = data.get("user", {})

                        console.print("\n[bold green]✓ User authenticated![/bold green]")
                        console.print(f"User: {self.session_data['user'].get('email', 'Unknown')}")

                    self.log_result(f"{provider} Callback", "PASS", "Authentication successful")
                    return True
                console.print(f"[red]✗[/red] Callback failed: {response.status_code}")
                console.print(response.text)
                self.log_result(f"{provider} Callback", "FAIL", response.text)
                return False

        except Exception as e:
            console.print(f"[red]✗[/red] Error processing callback: {e}")
            self.log_result(f"{provider} Callback", "FAIL", str(e))
            return False

    def validate_user_session(self):
        """Validate that user session is working."""
        console.print("\n[bold blue]Step 6:[/bold blue] Validating user session...")

        if not self.session_data.get("access_token"):
            console.print("[yellow]⚠[/yellow] No access token available for validation")
            return

        # Display user info
        user = self.session_data.get("user", {})

        table = Table(title="Authenticated User Info")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Email", user.get("email", "N/A"))
        table.add_row("Name", user.get("full_name", "N/A"))
        table.add_row("ID", str(user.get("id", "N/A")))
        table.add_row("Verified", str(user.get("is_verified", False)))

        console.print(table)

        self.log_result("User Session", "PASS", "Session validated")

    async def test_account_linking(self, provider: str):
        """Test linking additional OAuth accounts."""
        console.print("\n[bold blue]Step 7:[/bold blue] Testing account linking...")

        if not Confirm.ask(f"Do you want to test linking another {provider} account?"):
            console.print("[yellow]Skipped[/yellow]")
            return

        console.print("\n[yellow]To test account linking:[/yellow]")
        console.print("1. Log in with a different browser/incognito")
        console.print("2. Create a new account via regular signup")
        console.print(f"3. Link the {provider} account to that new account")
        console.print("4. Verify both accounts can access the same profile")

        result = Prompt.ask(
            "\nDid account linking work?",
            choices=["yes", "no", "skip"],
            default="skip"
        )

        if result == "yes":
            self.log_result(f"{provider} Account Linking", "PASS", "Manual verification passed")
        elif result == "no":
            self.log_result(f"{provider} Account Linking", "FAIL", "Manual verification failed")

    def generate_report(self):
        """Generate test report."""
        console.print("\n" + "="*70)
        console.print("[bold]Test Results Summary[/bold]")
        console.print("="*70)

        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")

        table = Table()
        table.add_column("Test", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Message", style="white")

        for result in self.results:
            status_color = "green" if result["status"] == "PASS" else "red"
            table.add_row(
                result["test"],
                f"[{status_color}]{result['status']}[/{status_color}]",
                result["message"]
            )

        console.print(table)
        console.print(f"\n[bold]Total:[/bold] {len(self.results)} tests")
        console.print(f"[green]Passed:[/green] {passed}")
        console.print(f"[red]Failed:[/red] {failed}")

        # Save detailed report
        report_file = f"oauth_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "results": self.results,
                "summary": {
                    "total": len(self.results),
                    "passed": passed,
                    "failed": failed,
                },
                "timestamp": datetime.now().isoformat(),
            }, f, indent=2)

        console.print(f"\n[green]✓[/green] Detailed report saved to: {report_file}")

    async def run(self, provider: str):
        """Run the interactive OAuth test."""
        console.print(Panel.fit(
            f"[bold cyan]Interactive {provider.upper()} OAuth Test[/bold cyan]\n"
            f"This will guide you through testing OAuth authentication",
            border_style="cyan"
        ))

        # Step 1: Check server
        if not await self.check_server():
            return

        # Step 2: Check environment variables
        if not self.check_env_variables(provider):
            return

        # Step 3: Get OAuth URL
        auth_url = await self.get_oauth_url(provider)
        if not auth_url:
            return

        # Step 4: Manual OAuth flow
        self.manual_oauth_flow(provider, auth_url)

        # Wait for user to complete OAuth
        if not Confirm.ask("\nHave you completed the OAuth flow in your browser?"):
            console.print("[yellow]Test cancelled[/yellow]")
            return

        # Step 5: Process callback
        callback_url = Prompt.ask("\nPaste the full callback URL here")
        if await self.process_callback(provider, callback_url):
            # Step 6: Validate session
            self.validate_user_session()

            # Step 7: Test account linking
            await self.test_account_linking(provider)

        # Generate report
        self.generate_report()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Interactive OAuth Flow Tester")
    parser.add_argument(
        "--provider",
        choices=["google", "github", "microsoft"],
        default="google",
        help="OAuth provider to test (default: google)"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    tester = OAuthTester(base_url=args.base_url)
    await tester.run(args.provider)


if __name__ == "__main__":
    asyncio.run(main())
