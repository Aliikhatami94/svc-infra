#!/usr/bin/env python3
"""
📚 REFERENCE IMPLEMENTATION: Automated Model Scaffolding

This script demonstrates how to automate model generation by calling the
svc-infra CLI commands directly. It serves as both:
1. A working automation tool for quick setup
2. An educational reference showing CLI usage patterns

The script calls ACTUAL CLI COMMANDS (not Python imports):
  ✅ poetry run svc-infra sql scaffold --kind auth ...
  ✅ poetry run svc-infra sql scaffold --kind entity ...

NOT: python -m svc_infra.cli ...

Note: In development, we prefix with 'poetry run' to use the local svc-infra.
In production (when svc-infra is installed globally), you can drop 'poetry run':
  ✅ svc-infra sql scaffold ...

This way you can:
- Learn the CLI commands by seeing them executed
- Copy commands for manual use or scripts
- Customize the script for your own needs
- Use it as a starting point for automation

Generates:
1. User model (authentication) - for add_auth_users()
2. Project & Task models (business entities)

🛡️ DUPLICATE PREVENTION:
The script automatically checks for existing models before scaffolding.
If a model file already exists, it will be skipped to protect your code.
Use --overwrite flag to force replacement (use with caution).

Usage:
    python scaffold_models.py              # Generate all models (safe)
    python scaffold_models.py --user-only  # Only generate User model
    python scaffold_models.py --overwrite  # Overwrite existing files (CAUTION!)

After running:
1. Review generated files and customize
2. See auth_reference.py for complete auth wiring example
3. Run migrations:
   svc-infra sql init --project-root .
   svc-infra sql revision -m "Add user and entity tables" --project-root .
   svc-infra sql upgrade head --project-root .
4. Enable features in .env (AUTH_ENABLED=true)
"""

import argparse
import subprocess
import sys
from pathlib import Path


class Colors:
    """ANSI color codes for pretty output."""

    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str):
    """Print a styled header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def check_model_exists(
    model_name: str, models_dir: Path, schemas_dir: Path
) -> tuple[bool, list[str]]:
    """
    Check if a model already exists.

    Returns:
        tuple: (exists, list of existing files)
    """
    model_file = models_dir / f"{model_name.lower()}.py"
    schema_file = schemas_dir / f"{model_name.lower()}.py"

    existing = []
    if model_file.exists():
        existing.append(str(model_file))
    if schema_file.exists():
        existing.append(str(schema_file))

    return len(existing) > 0, existing


def run_command(cmd: str | list[str], description: str) -> bool:
    """Run a shell command and return success status."""
    print(f"\n{Colors.BOLD}Running:{Colors.END} {description}")

    # If cmd is a list, join it for display, but keep it as list for subprocess
    if isinstance(cmd, list):
        display_cmd = " ".join(cmd)
        shell_mode = False
    else:
        display_cmd = cmd
        shell_mode = True

    print(f"  $ {display_cmd}")

    try:
        result = subprocess.run(
            cmd,
            shell=shell_mode,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            print_success(f"{description} - Success")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print_error(f"{description} - Failed")
            if result.stderr:
                print(result.stderr)
            if result.stdout:
                print(result.stdout)
            return False

    except Exception as e:
        print_error(f"{description} - Exception: {e}")
        return False


def scaffold_user_model(overwrite: bool = False) -> bool:
    """
    Scaffold User model for authentication using fastapi-users base.

    This generates:
    - src/svc_infra_template/models/user.py
    - src/svc_infra_template/schemas/user.py

    The User model will include:
    - UUID primary key (from fastapi-users)
    - email, hashed_password, is_active, is_superuser, is_verified
    - tenant_id (for multi-tenancy)
    - Soft delete support (deleted_at)
    """
    print_header("Scaffolding User Model (Authentication)")

    # Use absolute paths from examples directory
    examples_root = Path(__file__).parent.parent
    models_dir = examples_root / "src/svc_infra_template/models"
    schemas_dir = examples_root / "src/svc_infra_template/schemas"

    # Create directories if they don't exist
    models_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    # Check for duplicates
    if not overwrite:
        exists, existing_files = check_model_exists("user", models_dir, schemas_dir)
        if exists:
            print_warning("User model already exists:")
            for file in existing_files:
                print(f"  📁 {file}")
            print("\nSkipping to prevent overwriting existing code.")
            print("Use --overwrite flag if you want to replace existing files.")
            return False

    # Use the actual svc-infra CLI command (via poetry run in development)
    cmd = (
        f"poetry run svc-infra sql scaffold "
        f"--kind auth "
        f"--entity-name User "
        f"--table-name users "
        f"--models-dir {models_dir} "
        f"--schemas-dir {schemas_dir} "
        f"--models-filename user.py "
        f"--schemas-filename user.py"
    )

    if overwrite:
        cmd += " --overwrite"

    success = run_command(cmd, "Generate User model for authentication")

    if success:
        print_success("User model scaffolded successfully")
        print(f"\n  📁 Models:  {models_dir}/user.py")
        print(f"  📁 Schemas: {schemas_dir}/user.py")
        print("\n  Next steps:")
        print("  1. Review and customize the User model")
        print("  2. Add any custom fields (e.g., phone_number, avatar_url)")
        print("  3. Run migrations to create the users table")
        print("  4. Uncomment auth code in main.py")
        print("  5. Set AUTH_ENABLED=true in .env")

    return success


def scaffold_project_model(overwrite: bool = False) -> bool:
    """
    Scaffold Project model for business logic.

    This generates:
    - src/svc_infra_template/models/project.py (or updates existing)
    - src/svc_infra_template/schemas/project.py (or updates existing)

    The Project model will include:
    - tenant_id (for multi-tenancy)
    - Soft delete support (deleted_at)
    - Standard audit fields (created_at, updated_at)
    """
    print_header("Scaffolding Project Model")

    # Use absolute paths from examples directory
    examples_root = Path(__file__).parent.parent
    models_dir = examples_root / "src/svc_infra_template/models"
    schemas_dir = examples_root / "src/svc_infra_template/schemas"

    # Check for duplicates
    if not overwrite:
        exists, existing_files = check_model_exists("project", models_dir, schemas_dir)
        if exists:
            print_warning("Project model already exists:")
            for file in existing_files:
                print(f"  📁 {file}")
            print("\nSkipping to prevent overwriting existing code.")
            print("Use --overwrite flag if you want to replace existing files.")
            return False

    # Use the actual svc-infra CLI command (via poetry run in development)
    cmd = (
        f"poetry run svc-infra sql scaffold "
        f"--kind entity "
        f"--entity-name Project "
        f"--table-name projects "
        f"--models-dir {models_dir} "
        f"--schemas-dir {schemas_dir} "
        f"--models-filename project.py "
        f"--schemas-filename project.py"
    )

    if overwrite:
        cmd += " --overwrite"

    success = run_command(cmd, "Generate Project model")

    if success:
        print_success("Project model scaffolded successfully")
        print(f"\n  📁 Models:  {models_dir}/project.py")
        print(f"  📁 Schemas: {schemas_dir}/project.py")

    return success


def scaffold_task_model(overwrite: bool = False) -> bool:
    """
    Scaffold Task model for business logic.

    This generates:
    - src/svc_infra_template/models/task.py (or updates existing)
    - src/svc_infra_template/schemas/task.py (or updates existing)

    The Task model will include:
    - tenant_id (for multi-tenancy)
    - Standard audit fields (created_at, updated_at)
    """
    print_header("Scaffolding Task Model")

    # Use absolute paths from examples directory
    examples_root = Path(__file__).parent.parent
    models_dir = examples_root / "src/svc_infra_template/models"
    schemas_dir = examples_root / "src/svc_infra_template/schemas"

    # Check for duplicates
    if not overwrite:
        exists, existing_files = check_model_exists("task", models_dir, schemas_dir)
        if exists:
            print_warning("Task model already exists:")
            for file in existing_files:
                print(f"  📁 {file}")
            print("\nSkipping to prevent overwriting existing code.")
            print("Use --overwrite flag if you want to replace existing files.")
            return False

    # Use the actual svc-infra CLI command (via poetry run in development)
    cmd = (
        f"poetry run svc-infra sql scaffold "
        f"--kind entity "
        f"--entity-name Task "
        f"--table-name tasks "
        f"--models-dir {models_dir} "
        f"--schemas-dir {schemas_dir} "
        f"--models-filename task.py "
        f"--schemas-filename task.py"
    )

    if overwrite:
        cmd += " --overwrite"

    success = run_command(cmd, "Generate Task model")

    if success:
        print_success("Task model scaffolded successfully")
        print(f"\n  📁 Models:  {models_dir}/task.py")
        print(f"  📁 Schemas: {schemas_dir}/task.py")

    return success


def print_next_steps():
    """Print instructions for what to do after scaffolding."""
    print_header("Next Steps")

    print(f"{Colors.BOLD}1. Review Generated Files{Colors.END}")
    print("   • Check src/svc_infra_template/models/*.py")
    print("   • Check src/svc_infra_template/schemas/*.py")
    print("   • Customize fields, add relationships, constraints\n")

    print(f"{Colors.BOLD}2. Initialize Database Migrations{Colors.END}")
    print("   cd /path/to/examples && poetry run svc-infra sql init\n")

    print(f"{Colors.BOLD}3. Create Migration{Colors.END}")
    print('   poetry run svc-infra sql revision -m "Add user and entity tables"\n')

    print(f"{Colors.BOLD}4. Apply Migration{Colors.END}")
    print("   poetry run svc-infra sql upgrade head\n")

    print(f"{Colors.BOLD}5. Enable Features in .env{Colors.END}")
    print("   AUTH_ENABLED=true           # Enable authentication")
    print("   TENANCY_ENABLED=true        # Enable multi-tenancy")
    print("   GDPR_ENABLED=true           # Enable data lifecycle\n")

    print(f"{Colors.BOLD}6. Update main.py{Colors.END}")
    print("   • Uncomment the add_auth_users() section")
    print("   • Import your User model and schemas")
    print("   • Configure OAuth providers if needed\n")

    print(f"{Colors.BOLD}7. Start Server{Colors.END}")
    print("   make run\n")

    print(f"{Colors.BOLD}8. Test Endpoints{Colors.END}")
    print("   • Visit http://localhost:8001/docs")
    print("   • Test POST /auth/register")
    print("   • Test POST /auth/login")
    print("   • Test GET /users/me\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scaffold models and schemas for svc-infra-template",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--user-only",
        action="store_true",
        help="Only scaffold User model (skip Project/Task)",
    )
    parser.add_argument(
        "--entities-only",
        action="store_true",
        help="Only scaffold Project/Task models (skip User)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files",
    )

    args = parser.parse_args()

    print_header("🏗️  SVC-INFRA Model Scaffolding")
    print("This script will generate SQLAlchemy models and Pydantic schemas")
    print("for authentication and business entities.\n")

    if args.overwrite:
        print_warning("--overwrite enabled: existing files will be replaced")

    # Track success and skipped
    successes = []
    failures = []
    skipped = []

    # Scaffold User model (for authentication)
    if not args.entities_only:
        result = scaffold_user_model(overwrite=args.overwrite)
        if result:
            successes.append("User")
        elif result is False:
            skipped.append("User")

    # Scaffold business entity models
    if not args.user_only:
        result = scaffold_project_model(overwrite=args.overwrite)
        if result:
            successes.append("Project")
        elif result is False:
            skipped.append("Project")

        result = scaffold_task_model(overwrite=args.overwrite)
        if result:
            successes.append("Task")
        elif result is False:
            skipped.append("Task")

    # Print summary
    print_header("📊 Scaffolding Summary")

    if successes:
        print_success(f"Successfully scaffolded: {', '.join(successes)}")

    if skipped:
        print_warning(f"Skipped (already exist): {', '.join(skipped)}")
        print("\n  💡 Tip: Use --overwrite to replace existing files")

    if failures:
        print_error(f"Failed: {', '.join(failures)}")

    # Print next steps only if we created something new
    if successes:
        print_next_steps()
        print_success("Scaffolding complete! 🎉")
        return 0
    elif skipped and not failures:
        print("\n✨ All models already exist. Nothing to do!")
        return 0
    else:
        print_error("Scaffolding failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
