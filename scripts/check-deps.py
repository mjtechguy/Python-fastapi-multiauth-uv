#!/usr/bin/env python3
"""Check PyPI for latest versions - WORKING VERSION."""

import json
import re
import urllib.request
import time
from pathlib import Path

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def get_latest_version(package: str) -> str:
    """Get latest version from PyPI."""
    try:
        url = f"https://pypi.org/pypi/{package}/json"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data["info"]["version"]
    except Exception:
        return ""


def parse_version(version_str: str) -> list:
    """Parse semantic version into list of ints."""
    try:
        parts = [int(x) for x in version_str.split('.')[:3]]
        while len(parts) < 3:
            parts.append(0)
        return parts[:3]
    except:
        return [0, 0, 0]


def compare_versions(current: str, latest: str) -> tuple:
    """Return (color, status, category)."""
    cv = parse_version(current)
    lv = parse_version(latest)

    if cv == lv:
        return GREEN, "✅ Current", "current"
    elif cv[0] < lv[0]:
        return RED, "🔴 MAJOR", "major"
    elif cv[1] < lv[1]:
        return YELLOW, "🟡 MINOR", "minor"
    else:
        return BLUE, "🔵 PATCH", "patch"


def main():
    """Check all dependencies."""
    print(f"\n{BOLD}📦 PyPI Dependency Version Checker{RESET}\n")

    # Read pyproject.toml
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"{RED}❌ pyproject.toml not found{RESET}")
        return

    # Parse dependencies section
    content = pyproject_path.read_text()
    lines = content.split('\n')

    # Find dependencies array (better parsing)
    dep_lines = []
    in_deps = False

    for line in lines:
        if line.strip() == 'dependencies = [':
            in_deps = True
            continue
        if in_deps:
            if line.strip() == ']':
                break
            # Extract dependency from quoted string
            if '"' in line and not line.strip().startswith('#'):
                match = re.search(r'"([^"]+)"', line)
                if match:
                    dep_lines.append(match.group(1))

    print(f"Found {len(dep_lines)} dependencies to check\n")
    print(f"{BOLD}{'Package':<35} {'Current':<15} {'Latest':<15} Status{RESET}")
    print("-" * 85)

    results = {"current": [], "major": [], "minor": [], "patch": [], "error": []}

    for i, dep in enumerate(dep_lines):
        # Parse dependency (handle extras like pydantic[email])
        match = re.match(r'^([a-zA-Z0-9\-_]+)(?:\[.+?\])?(>=|==|~=)(.+)$', dep)
        if not match:
            continue

        package = match.group(1)
        operator = match.group(2)
        current_version = match.group(3).strip()

        # Get latest version
        latest_version = get_latest_version(package)

        if not latest_version:
            results["error"].append(package)
            print(f"{package:<35} {current_version:<15} {RED}ERROR{RESET}")
            continue

        # Compare versions
        color, status, category = compare_versions(current_version, latest_version)
        results[category].append((package, current_version, latest_version))

        print(f"{package:<35} {color}{current_version:<15}{RESET} {color}{latest_version:<15}{RESET} {color}{status}{RESET}")

        # Rate limiting - be nice to PyPI
        if (i + 1) % 5 == 0:
            time.sleep(0.5)

    # Summary
    print("\n" + "=" * 85)
    print(f"\n{BOLD}📊 SUMMARY:{RESET}\n")
    print(f"  {GREEN}✅ Up to date:{RESET} {len(results['current'])}")
    print(f"  {BLUE}🔵 Patch updates:{RESET} {len(results['patch'])}")
    print(f"  {YELLOW}🟡 Minor updates:{RESET} {len(results['minor'])}")
    print(f"  {RED}🔴 Major updates:{RESET} {len(results['major'])}")
    if results['error']:
        print(f"  ❌ Errors: {len(results['error'])}")

    # Details
    if results['major']:
        print(f"\n{BOLD}{RED}🔴 MAJOR UPDATES (check for breaking changes!):{RESET}")
        for pkg, cur, new in results['major']:
            print(f"   • {pkg}: {cur} → {new}")

    if results['minor']:
        print(f"\n{BOLD}{YELLOW}🟡 MINOR UPDATES (new features, generally safe):{RESET}")
        for pkg, cur, new in results['minor'][:10]:
            print(f"   • {pkg}: {cur} → {new}")
        if len(results['minor']) > 10:
            print(f"   ... and {len(results['minor']) - 10} more")

    if results['patch']:
        print(f"\n{BOLD}{BLUE}🔵 PATCH UPDATES (bug fixes only, safe):{RESET}")
        for pkg, cur, new in results['patch'][:10]:
            print(f"   • {pkg}: {cur} → {new}")
        if len(results['patch']) > 10:
            print(f"   ... and {len(results['patch']) - 10} more")

    # Recommendation
    total_updates = len(results['major']) + len(results['minor']) + len(results['patch'])
    if total_updates == 0:
        print(f"\n{GREEN}{BOLD}🎉 All dependencies are up to date!{RESET}")
    else:
        print(f"\n{BOLD}💡 UPDATE RECOMMENDATIONS:{RESET}")
        if results['minor'] or results['patch']:
            print(f"   Safe to update: Minor and patch versions")
        if results['major']:
            print(f"   {RED}Review carefully:{RESET} Major version updates")

    print()


if __name__ == "__main__":
    main()
