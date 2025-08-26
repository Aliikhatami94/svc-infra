from pathlib import Path
from typing import Any


def _find_repo_root(start: Path) -> Path:
    """Walk up from start to locate the repository root (presence of pyproject.toml)."""
    cur = start.resolve()
    while True:
        if (cur / "pyproject.toml").exists():
            return cur
        if cur.parent == cur:
            # Reached filesystem root; fallback to original start
            return start.resolve()
        cur = cur.parent


def detect_package_context() -> dict[str, Any]:
    """
    Discover any packages that expose a CLI entry under src/svc_infra/**/cli.py.

    Returns a dictionary with keys:
      - root: repository root path
      - packages: list of { package, module, path, readme }
        where:
          package = conventional name like 'svc-infra-<module>'
          module  = folder name under src/svc_infra (e.g., db, auth)
          path    = absolute path to the package folder
          readme  = README.md contents if present, else ''
    """
    cwd = Path.cwd()
    root = _find_repo_root(cwd)

    cli_files = list((root / "src" / "svc_infra").glob("**/cli.py"))

    packages: list[dict[str, str]] = []
    for cli_file in cli_files:
        pkg_dir = cli_file.parent
        module = pkg_dir.name
        # Build conventional package name
        pkg_name = f"svc-infra-{module}"
        readme_path = pkg_dir / "README.md"
        readme = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        packages.append({
            "package": pkg_name,
            "module": module,
            "path": str(pkg_dir.resolve()),
            "readme": readme,
        })

    return {
        "root": str(root),
        "packages": packages,
    }


if __name__ == '__main__':
    ctx = detect_package_context()
    readme_snippets = "\n\n".join(
        f"# {pkg['package']} readme\n\n{pkg['readme'][:2000]}\n---"
        for pkg in ctx["packages"]
    )

    # prompt = f"{readme_snippets}\n\n{your_os_hint}{PLAN_POLICY}"
    print(readme_snippets)