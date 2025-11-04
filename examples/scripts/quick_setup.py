#!/usr/bin/env python3
"""
Quick setup script to scaffold models and run migrations.

This is a simplified all-in-one script that:
1. Generates User, Project, and Task models
2. Initializes Alembic migrations
3. Creates a migration
4. Applies the migration
5. Provides instructions for enabling features

Usage:
    python quick_setup.py
    python quick_setup.py --skip-migrations  # Only scaffold, skip migrations
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run(cmd: str, description: str = None) -> bool:
    """Run a command and return success status."""
    if description:
        print(f"\n🔧 {description}...")

    print(f"   $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)

    if result.returncode == 0:
        print("   ✅ Done")
        return True
    else:
        print(f"   ❌ Failed (exit code: {result.returncode})")
        return False


def main():
    """Main entry point for quick setup."""
    parser = argparse.ArgumentParser(
        description="Quick setup for svc-infra-template (safe: won't overwrite existing models)",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Only scaffold models, skip migrations",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing model files (USE WITH CAUTION)",
    )

    args = parser.parse_args()

    # Ensure we're running from the examples directory
    script_dir = Path(__file__).parent
    examples_dir = script_dir.parent

    print("=" * 70)
    print("🚀 SVC-INFRA QUICK SETUP")
    print("=" * 70)
    print(f"Working directory: {examples_dir}\n")

    # Step 1: Scaffold models
    print("\n📦 Step 1: Scaffolding Models")
    print("-" * 70)

    scaffold_script = script_dir / "scaffold_models.py"
    base_cmd = f"python3 {scaffold_script}"
    if args.overwrite:
        base_cmd += " --overwrite"

    if not run(base_cmd, "Generate User, Project, and Task models"):
        print("\n⚠️  Model scaffolding failed. Check output above.")
        return 1

    if args.skip_migrations:
        print("\n✅ Models scaffolded. Skipping migrations (--skip-migrations)")
        print("\nTo run migrations manually (from examples directory):")
        print("  1. poetry run svc-infra sql init --project-root .")
        print("  2. poetry run svc-infra sql revision --project-root . -m 'Initial'")
        print("  3. poetry run svc-infra sql upgrade --project-root . head")
        return 0

    # Check if SQL_URL is configured
    env_file = examples_dir / ".env"
    if env_file.exists():
        import os

        # Load .env if it exists
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    if key.strip() == "SQL_URL" and value.strip():
                        os.environ["SQL_URL"] = value.strip()
                        break

    if not os.environ.get("SQL_URL"):
        print("\n⚠️  SQL_URL not found in environment")
        print("   Using default: sqlite+aiosqlite:////tmp/svc_infra_template.db")
        os.environ["SQL_URL"] = "sqlite+aiosqlite:////tmp/svc_infra_template.db"

    # Step 2: Initialize Alembic (if not already done)
    print("\n📦 Step 2: Initialize Database Migrations")
    print("-" * 70)

    alembic_dir = examples_dir / "alembic"
    if alembic_dir.exists():
        print("   ℹ️  Alembic already initialized, skipping...")
    else:
        # Run from examples directory with PROJECT_ROOT set
        if not run(
            f"cd {examples_dir} && PROJECT_ROOT=. poetry run svc-infra sql init",
            "Initialize Alembic",
        ):
            print("\n⚠️  Alembic initialization failed.")
            return 1

    # Step 3: Create migration
    print("\n📦 Step 3: Create Migration")
    print("-" * 70)

    if not run(
        f'cd {examples_dir} && PROJECT_ROOT=. poetry run svc-infra sql revision -m "Add user and entity tables"',
        "Generate migration for new models",
    ):
        print("\n⚠️  Migration creation failed.")
        print("This might mean:")
        print("  • Database URL not configured (check SQL_URL in .env)")
        print("  • Models have errors (check syntax)")
        return 1

    # Step 4: Apply migration
    print("\n📦 Step 4: Apply Migration")
    print("-" * 70)

    if not run(
        f"cd {examples_dir} && PROJECT_ROOT=. poetry run svc-infra sql upgrade head",
        "Apply migration to database",
    ):
        print("\n⚠️  Migration failed.")
        print("Check your database connection and SQL_URL in .env")
        return 1

    # Success!
    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)

    print("\n📝 Next Steps:")
    print("-" * 70)
    print("\n1. Update main.py:")
    print("   • Uncomment the add_auth_users() section")
    print("   • Import your User model:")
    print("     from svc_infra_template.models.user import User")
    print("   • Import your schemas:")
    print("     from svc_infra_template.schemas.user import UserRead, UserCreate, UserUpdate")
    print("   • Update the add_auth_users() call with your models")

    print("\n2. Enable features in .env:")
    print("   AUTH_ENABLED=true")
    print("   TENANCY_ENABLED=true")
    print("   GDPR_ENABLED=true")

    print("\n3. Start the server:")
    print("   make run")
    print("   # or: poetry run python -m svc_infra_template.main")

    print("\n4. Test the API:")
    print("   • Visit http://localhost:8001/docs")
    print("   • Try POST /auth/register")
    print("   • Try POST /auth/login")
    print("   • Try GET /users/me")
    print("   • Try CRUD endpoints: /_sql/projects, /_sql/tasks")

    print("\n5. Customize your models:")
    print("   • Add custom fields to User (phone, avatar_url, etc.)")
    print("   • Add relationships between models")
    print("   • Add custom validators")
    print("   • Create new migrations: poetry run svc-infra sql revision -m 'description'")

    print("\n" + "=" * 70)
    print("🎉 Happy coding!")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
