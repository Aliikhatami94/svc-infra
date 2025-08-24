Quickstart commands (copy and paste):

```bash
# init (one-time per app repo)
poetry run svc-infra-db init --models-module app.models
# or if you exposed umbrella cli:
poetry run svc-infra db init --models-module app.models

# create a migration from diffs
poetry run svc-infra-db revision -m "init users" --autogenerate

# apply
poetry run svc-infra-db upgrade head

# rollback last
poetry run svc-infra-db downgrade -1

# status
poetry run svc-infra-db current
poetry run svc-infra-db history
```