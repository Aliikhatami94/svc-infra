## svc_infra auth CLI

Scaffold FastAPI Users models and schemas.

### Usage

- Script: `svc-infra auth`
- Poetry: `poetry run svc-infra auth --help`

### Quick start

- Models:

  ```bash
  poetry run svc-infra auth scaffold-auth-models --dest-dir src/my_app/auth
  ```

- Schemas:

  ```bash
  poetry run svc-infra auth scaffold-auth-schemas --dest-dir src/my_app/auth
  ```

- All at once:

  ```bash
  poetry run svc-infra auth scaffold-auth --models-dir src/my_app/auth --schemas-dir src/my_app/auth
  ```

### Commands

- `scaffold-auth --models-dir PATH --schemas-dir PATH [--overwrite]`
- `scaffold-auth-models --dest-dir PATH [--overwrite]`
- `scaffold-auth-schemas --dest-dir PATH [--overwrite]`

### Notes

- Writes `models.py` and `schemas.py` at the target paths.
- Creates directories if missing.
- Shows `SKIP` when a file exists (use `--overwrite`), otherwise `Wrote`.
