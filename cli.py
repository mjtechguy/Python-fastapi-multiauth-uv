#!/usr/bin/env python3
"""
SaaS Backend CLI - Interactive testing tool for the API

Usage:
    python cli.py --help
    python cli.py auth register
    python cli.py auth login
    python cli.py files upload myfile.txt
    python cli.py health check-all
"""

import json
import os
from pathlib import Path
from typing import Optional
import httpx
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.panel import Panel
from rich.syntax import Syntax


app = typer.Typer(help="SaaS Backend API Testing CLI")
console = Console()

# Configuration
TOKEN_FILE = Path.home() / ".saas_cli_tokens.json"
DEFAULT_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


# ============================================================================
# Token Management
# ============================================================================

def save_tokens(access_token: str, refresh_token: str):
    """Save tokens to file."""
    TOKEN_FILE.write_text(json.dumps({
        "access_token": access_token,
        "refresh_token": refresh_token
    }))
    console.print("[green]✓[/green] Tokens saved", style="bold")


def load_tokens() -> Optional[dict]:
    """Load tokens from file."""
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def get_headers() -> dict:
    """Get authorization headers."""
    tokens = load_tokens()
    if tokens:
        return {"Authorization": f"Bearer {tokens['access_token']}"}
    return {}


# ============================================================================
# Pretty Printing
# ============================================================================

def print_response(response: httpx.Response):
    """Pretty print HTTP response."""
    # Status
    status_color = "green" if 200 <= response.status_code < 300 else "red"
    console.print(f"\n[{status_color}]Status:[/{status_color}] {response.status_code}")

    # Headers (selected)
    if "content-type" in response.headers:
        console.print(f"[cyan]Content-Type:[/cyan] {response.headers['content-type']}")

    # Body
    try:
        data = response.json()
        console.print("\n[yellow]Response:[/yellow]")
        syntax = Syntax(json.dumps(data, indent=2), "json", theme="monokai")
        console.print(syntax)
    except:
        console.print(f"\n[yellow]Response:[/yellow]\n{response.text}")


def print_error(message: str):
    """Print error message."""
    console.print(f"[red]✗ Error:[/red] {message}", style="bold")


def print_success(message: str):
    """Print success message."""
    console.print(f"[green]✓ Success:[/green] {message}", style="bold")


# ============================================================================
# Authentication Commands
# ============================================================================

auth_app = typer.Typer(help="Authentication commands")
app.add_typer(auth_app, name="auth")


@auth_app.command()
def register(
    email: str = typer.Option(..., "--email", "-e", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
    full_name: str = typer.Option(..., "--name", "-n", prompt=True),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """Register a new user."""
    console.print("\n[bold cyan]🚀 Registering new user...[/bold cyan]\n")

    data = {
        "email": email,
        "password": password,
        "full_name": full_name
    }

    with httpx.Client(base_url=base_url) as client:
        response = client.post("/api/v1/auth/register", json=data)
        print_response(response)

        if response.status_code == 201:
            print_success("User registered successfully!")


@auth_app.command()
def login(
    email: str = typer.Option(..., "--email", "-e", prompt=True),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """Login and save access token."""
    console.print("\n[bold cyan]🔑 Logging in...[/bold cyan]\n")

    with httpx.Client(base_url=base_url) as client:
        response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password}
        )
        print_response(response)

        if response.status_code == 200:
            tokens = response.json()
            save_tokens(tokens["access_token"], tokens["refresh_token"])
            print_success("Logged in successfully!")


@auth_app.command()
def me(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Get current user info."""
    console.print("\n[bold cyan]👤 Getting user info...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/auth/me")
        print_response(response)


@auth_app.command()
def refresh(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Refresh access token."""
    tokens = load_tokens()
    if not tokens:
        print_error("No tokens found. Please login first.")
        raise typer.Exit(1)

    console.print("\n[bold cyan]🔄 Refreshing token...[/bold cyan]\n")

    with httpx.Client(base_url=base_url) as client:
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]}
        )
        print_response(response)

        if response.status_code == 200:
            new_tokens = response.json()
            save_tokens(new_tokens["access_token"], new_tokens["refresh_token"])
            print_success("Token refreshed!")


@auth_app.command()
def logout():
    """Logout and clear tokens."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print_success("Logged out successfully!")
    else:
        console.print("[yellow]No active session found[/yellow]")


# ============================================================================
# Organization Commands
# ============================================================================

org_app = typer.Typer(help="Organization management")
app.add_typer(org_app, name="org")


@org_app.command()
def create(
    name: str = typer.Option(..., "--name", "-n", prompt=True),
    slug: str = typer.Option(..., "--slug", "-s", prompt=True),
    description: str = typer.Option("", "--description", "-d"),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """Create a new organization."""
    console.print("\n[bold cyan]🏢 Creating organization...[/bold cyan]\n")

    data = {
        "name": name,
        "slug": slug,
        "description": description
    }

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.post("/api/v1/organizations", json=data)
        print_response(response)


@org_app.command("list")
def list_orgs(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """List all organizations."""
    console.print("\n[bold cyan]📋 Listing organizations...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/organizations")
        print_response(response)


@org_app.command()
def get(
    org_id: str = typer.Argument(..., help="Organization ID"),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """Get organization details."""
    console.print(f"\n[bold cyan]🔍 Getting organization {org_id}...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get(f"/api/v1/organizations/{org_id}")
        print_response(response)


# ============================================================================
# File Commands
# ============================================================================

files_app = typer.Typer(help="File management")
app.add_typer(files_app, name="files")


@files_app.command()
def upload(
    file_path: Path = typer.Argument(..., help="Path to file"),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """Upload a file."""
    if not file_path.exists():
        print_error(f"File not found: {file_path}")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]📤 Uploading {file_path.name}...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers(), timeout=60) as client:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            response = client.post("/api/v1/files/upload", files=files)
            print_response(response)


@files_app.command("list")
def list_files(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """List uploaded files."""
    console.print("\n[bold cyan]📁 Listing files...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/files")
        print_response(response)


# ============================================================================
# Session Commands
# ============================================================================

sessions_app = typer.Typer(help="Session management")
app.add_typer(sessions_app, name="sessions")


@sessions_app.command("list")
def list_sessions(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """List active sessions."""
    console.print("\n[bold cyan]🔐 Listing sessions...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/sessions")
        print_response(response)


@sessions_app.command()
def stats(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Get session statistics."""
    console.print("\n[bold cyan]📊 Getting session stats...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/sessions/stats")
        print_response(response)


# ============================================================================
# Webhook Commands
# ============================================================================

webhooks_app = typer.Typer(help="Webhook management")
app.add_typer(webhooks_app, name="webhooks")


@webhooks_app.command()
def events(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """List available webhook events."""
    console.print("\n[bold cyan]📢 Available webhook events...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/webhooks/events")
        print_response(response)


@webhooks_app.command()
def create(
    url: str = typer.Option(..., "--url-endpoint", "-u", prompt=True),
    events: str = typer.Option(..., "--events", "-e", prompt=True, help="Comma-separated events"),
    description: str = typer.Option("", "--description", "-d"),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """Create a webhook."""
    console.print("\n[bold cyan]🪝 Creating webhook...[/bold cyan]\n")

    data = {
        "url": url,
        "events": [e.strip() for e in events.split(",")],
        "description": description
    }

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.post("/api/v1/webhooks", json=data)
        print_response(response)


@webhooks_app.command("list")
def list_webhooks(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """List webhooks."""
    console.print("\n[bold cyan]📋 Listing webhooks...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/webhooks")
        print_response(response)


# ============================================================================
# Quota Commands
# ============================================================================

quota_app = typer.Typer(help="Usage quota management")
app.add_typer(quota_app, name="quota")


@quota_app.command()
def status(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Get quota status."""
    console.print("\n[bold cyan]📊 Getting quota status...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/quota/status")
        print_response(response)


@quota_app.command()
def logs(
    page: int = typer.Option(1, "--page", "-p"),
    page_size: int = typer.Option(20, "--size", "-s"),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """Get usage logs."""
    console.print("\n[bold cyan]📜 Getting usage logs...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get(f"/api/v1/quota/usage-logs?page={page}&page_size={page_size}")
        print_response(response)


# ============================================================================
# Health Check Commands
# ============================================================================

health_app = typer.Typer(help="Health checks")
app.add_typer(health_app, name="health")


@health_app.command()
def check_all(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Check all services."""
    console.print("\n[bold cyan]💚 Checking all services...[/bold cyan]\n")

    with httpx.Client(base_url=base_url) as client:
        response = client.get("/api/v1/health/all")
        print_response(response)


@health_app.command()
def database(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Check database health."""
    with httpx.Client(base_url=base_url) as client:
        response = client.get("/api/v1/health/db")
        print_response(response)


@health_app.command()
def redis(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Check Redis health."""
    with httpx.Client(base_url=base_url) as client:
        response = client.get("/api/v1/health/redis")
        print_response(response)


@health_app.command()
def celery(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Check Celery workers health."""
    with httpx.Client(base_url=base_url) as client:
        response = client.get("/api/v1/health/celery")
        print_response(response)


@health_app.command()
def storage(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Check storage service health."""
    with httpx.Client(base_url=base_url) as client:
        response = client.get("/api/v1/health/storage")
        print_response(response)


# ============================================================================
# DLQ Commands
# ============================================================================

dlq_app = typer.Typer(help="Dead Letter Queue management")
app.add_typer(dlq_app, name="dlq")


@dlq_app.command()
def stats(base_url: str = typer.Option(DEFAULT_BASE_URL, "--url")):
    """Get DLQ statistics."""
    console.print("\n[bold cyan]📊 DLQ Statistics...[/bold cyan]\n")

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/dead-letter/statistics")
        print_response(response)


@dlq_app.command("list")
def list_tasks(
    status: Optional[str] = typer.Option(None, "--status", "-s"),
    base_url: str = typer.Option(DEFAULT_BASE_URL, "--url"),
):
    """List failed tasks."""
    console.print("\n[bold cyan]📋 Listing failed tasks...[/bold cyan]\n")

    params = {}
    if status:
        params["status"] = status

    with httpx.Client(base_url=base_url, headers=get_headers()) as client:
        response = client.get("/api/v1/dead-letter", params=params)
        print_response(response)


# ============================================================================
# Main
# ============================================================================

@app.callback()
def main():
    """
    SaaS Backend API Testing CLI

    Test and interact with your SaaS backend API from the command line.
    """
    pass


if __name__ == "__main__":
    app()
