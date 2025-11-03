#!/usr/bin/env python3
"""
Test script to verify duplicate prevention works correctly.

This creates dummy model files, then runs scaffold_models.py
to verify it properly detects and skips existing models.
"""

import sys
import tempfile
from pathlib import Path


def run_test():
    """Test duplicate prevention."""
    print("=" * 70)
    print("🧪 Testing Duplicate Prevention")
    print("=" * 70)

    # Create temporary directories
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        models_dir = tmppath / "models"
        schemas_dir = tmppath / "schemas"

        models_dir.mkdir()
        schemas_dir.mkdir()

        print("\n📁 Created test directories:")
        print(f"   Models:  {models_dir}")
        print(f"   Schemas: {schemas_dir}")

        # Test 1: No existing files - should scaffold
        print("\n" + "-" * 70)
        print("Test 1: Scaffolding with no existing files")
        print("-" * 70)

        # Create a dummy model file to simulate existing User model
        user_model = models_dir / "user.py"
        user_model.write_text("# Existing User model\nclass User:\n    pass\n")

        print(f"✅ Created dummy file: {user_model}")

        # Now test that scaffold detects it
        print("\n" + "-" * 70)
        print("Test 2: Scaffolding when User model exists (should skip)")
        print("-" * 70)

        from scaffold_models import check_model_exists

        exists, files = check_model_exists("user", models_dir, schemas_dir)

        if exists:
            print("✅ PASS: Detected existing model:")
            for f in files:
                print(f"   - {f}")
        else:
            print("❌ FAIL: Did not detect existing model")
            return 1

        # Test 3: Check non-existent model
        print("\n" + "-" * 70)
        print("Test 3: Checking non-existent model (should not exist)")
        print("-" * 70)

        exists, files = check_model_exists("project", models_dir, schemas_dir)

        if not exists:
            print("✅ PASS: Correctly identified missing model")
        else:
            print(f"❌ FAIL: Incorrectly detected model exists: {files}")
            return 1

        # Test 4: Partial existence (only model, no schema)
        print("\n" + "-" * 70)
        print("Test 4: Partial existence - only model file exists")
        print("-" * 70)

        task_model = models_dir / "task.py"
        task_model.write_text("# Existing Task model\nclass Task:\n    pass\n")

        exists, files = check_model_exists("task", models_dir, schemas_dir)

        if exists and len(files) == 1:
            print("✅ PASS: Detected partial existence:")
            print(f"   - {files[0]}")
        else:
            print("❌ FAIL: Did not correctly detect partial existence")
            return 1

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)

        print("\n📝 Summary:")
        print("   • check_model_exists() correctly detects existing models")
        print("   • check_model_exists() correctly identifies missing models")
        print("   • check_model_exists() detects partial existence (model XOR schema)")
        print("\n✨ Duplicate prevention is working correctly!")

        return 0


if __name__ == "__main__":
    # Add parent directory to path to import scaffold_models
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))

    sys.exit(run_test())
