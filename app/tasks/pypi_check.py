"""PyPI package version checking tasks."""

import httpx
import toml
from pathlib import Path

from app.tasks.celery_app import celery_app


@celery_app.task
def check_package_versions() -> dict[str, dict[str, str]]:
    """
    Check if installed packages have newer versions on PyPI.

    Returns:
        Dictionary of packages with updates available
    """
    try:
        # Read pyproject.toml
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "r") as f:
            pyproject_data = toml.load(f)

        dependencies = pyproject_data.get("project", {}).get("dependencies", [])
        outdated_packages = {}

        for dep in dependencies:
            # Parse dependency string (e.g., "fastapi>=0.100.0")
            if ">=" in dep:
                package_name, current_version = dep.split(">=")
            elif "==" in dep:
                package_name, current_version = dep.split("==")
            else:
                continue

            package_name = package_name.strip()
            current_version = current_version.strip()

            # Check PyPI for latest version
            try:
                with httpx.Client() as client:
                    response = client.get(
                        f"https://pypi.org/pypi/{package_name}/json", timeout=10.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        latest_version = data["info"]["version"]

                        if latest_version != current_version:
                            outdated_packages[package_name] = {
                                "current": current_version,
                                "latest": latest_version,
                            }

            except Exception as e:
                print(f"Error checking {package_name}: {e}")
                continue

        # Log results
        if outdated_packages:
            print(f"Found {len(outdated_packages)} packages with updates:")
            for pkg, versions in outdated_packages.items():
                print(f"  {pkg}: {versions['current']} -> {versions['latest']}")

        return outdated_packages

    except Exception as e:
        print(f"Error checking package versions: {e}")
        return {}
