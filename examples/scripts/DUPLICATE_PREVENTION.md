# 🛡️ Duplicate Prevention Feature

## Overview

The scaffolding scripts now **prevent accidental overwrites** of existing models, protecting your customizations from being lost.

## Visual Comparison

### ❌ Before (Dangerous)

```bash
$ python scripts/scaffold_models.py
✅ User model scaffolded successfully

# Run again by mistake...
$ python scripts/scaffold_models.py
✅ User model scaffolded successfully  # 💀 YOUR CODE WAS OVERWRITTEN!
```

### ✅ After (Safe)

```bash
$ python scripts/scaffold_models.py
✅ User model scaffolded successfully

# Run again by mistake...
$ python scripts/scaffold_models.py

⚠️  User model already exists:
  📁 /path/to/models/user.py
  📁 /path/to/schemas/user.py

Skipping to prevent overwriting existing code.
Use --overwrite flag if you want to replace existing files.

📊 Scaffolding Summary
⚠️  Skipped (already exist): User, Project, Task
  💡 Tip: Use --overwrite to replace existing files
```

## Implementation Details

### Core Function: `check_model_exists()`

Located in `scripts/scaffold_models.py`:

```python
def check_model_exists(model_name: str, models_dir: Path, schemas_dir: Path) -> tuple[bool, list[str]]:
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
```

### Integration Points

Each scaffolding function now includes duplicate checking:

1. **scaffold_user_model()**
2. **scaffold_project_model()**
3. **scaffold_task_model()**

Each function:
- Checks for existing files before scaffolding
- Shows clear warning with file paths if duplicates exist
- Returns `False` to indicate skipped (not failed)
- Only proceeds if `overwrite=True` or no files exist

### User Experience

#### Default Behavior (Safe Mode)
```bash
$ python scripts/scaffold_models.py

⚠️  User model already exists:
  📁 /path/to/models/user.py
  📁 /path/to/schemas/user.py

Skipping to prevent overwriting existing code.
Use --overwrite flag if you want to replace existing files.
```

#### With --overwrite Flag
```bash
$ python scripts/scaffold_models.py --overwrite

Running: Generate User model for authentication
  $ poetry run svc-infra sql scaffold --kind auth ...
✅ User model scaffolded successfully
```

### Summary Output

The main() function now provides a comprehensive summary:

```
📊 Scaffolding Summary
══════════════════════════════════════════════════════════════════════

✅ Successfully scaffolded: Project, Task
⚠️  Skipped (already exist): User

  💡 Tip: Use --overwrite to replace existing files
```

## Safety Features

1. **Default Safe**: No overwrites without explicit flag
2. **Clear Warnings**: Shows which files exist and where
3. **Explicit Opt-In**: `--overwrite` required to replace
4. **Granular Control**: Use `--user-only` or `--entities-only`
5. **Visual Feedback**: Color-coded output (green=success, yellow=warning)

## Testing

### Automated Tests

Run `scripts/test_duplicate_prevention.py` to verify:
- ✅ Detects existing models correctly
- ✅ Identifies missing models correctly
- ✅ Handles partial existence (model XOR schema)

### Manual Testing

1. Run scaffold script twice:
   ```bash
   python scripts/scaffold_models.py  # First run - creates files
   python scripts/scaffold_models.py  # Second run - skips files
   ```

2. Verify output shows warnings and skips

3. Test overwrite:
   ```bash
   python scripts/scaffold_models.py --overwrite  # Replaces files
   ```

## Documentation Updates

All documentation has been updated to reflect duplicate prevention:

1. **README.md**: Added "Safe by default" note
2. **SCAFFOLDING.md**:
   - Added 🛡️ Duplicate Prevention section
   - Updated all command examples
   - Added warnings about --overwrite
3. **scaffold_models.py docstring**: Added DUPLICATE PREVENTION section
4. **quick_setup.py**: Updated help text to indicate safety

## Best Practices

When using the scaffolding scripts:

1. ✅ **First run**: Use without flags (safe mode)
2. ✅ **Review code**: Inspect generated files before customizing
3. ✅ **Version control**: Commit before using --overwrite
4. ✅ **Targeted scaffolding**: Use --user-only or --entities-only
5. ✅ **Read summary**: Check what was created/skipped

## Edge Cases Handled

- ✅ Both model and schema exist → Skip
- ✅ Only model exists → Skip (partial existence)
- ✅ Only schema exists → Skip (partial existence)
- ✅ Neither exists → Scaffold normally
- ✅ --overwrite flag → Bypass all checks
- ✅ Multiple models → Independent checking

## Files Modified

1. `examples/scripts/scaffold_models.py`
   - Added `check_model_exists()` function
   - Updated all scaffold_*_model() functions
   - Enhanced main() with better summary

2. `examples/scripts/quick_setup.py`
   - Updated help text to indicate safety
   - Added warning to --overwrite flag

3. `examples/README.md`
   - Added safety note to quick setup section

4. `examples/SCAFFOLDING.md`
   - Added duplicate prevention section
   - Added safety warnings
   - Updated all examples

## Testing Scripts Created

1. `scripts/test_duplicate_prevention.py` - Automated unit tests
2. `scripts/demo_duplicate_prevention.py` - Interactive demonstration

## Result

Users can now safely run scaffolding scripts multiple times without fear of losing their customizations. The system provides clear feedback and requires explicit intent (--overwrite) to replace existing code.
