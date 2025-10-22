"""PyPI package version checking tasks."""

import httpx
import re
from pathlib import Path

from app.tasks.celery_app import celery_app
from app.core.logging_config import get_logger

logger = get_logger(__name__)


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
        content = pyproject_path.read_text()

        # Parse dependencies manually (no external toml library needed)
        dependencies = []
        in_deps = False
        for line in content.split('\n'):
            if 'dependencies = [' in line:
                in_deps = True
                continue
            if in_deps:
                if ']' in line:
                    break
                if line.strip() and line.strip().startswith('"'):
                    # Extract dependency from quoted string
                    match = re.search(r'"([^"]+)"', line)
                    if match:
                        dependencies.append(match.group(1))
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
                logger.warning(
                    "package_check_failed",
                    package=package_name,
                    error=str(e)
                )
                continue

        # Log results
        if outdated_packages:
            logger.info(
                "packages_with_updates_found",
                count=len(outdated_packages),
                packages=outdated_packages
            )

        return outdated_packages

    except Exception as e:
        logger.error(
            "package_version_check_failed",
            error=str(e),
            exc_info=True
        )
        return {}
