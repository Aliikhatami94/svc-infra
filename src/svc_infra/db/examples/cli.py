"""
Example usage of the `svc-infra-scaffold` CLI tool to scaffold authentication components.
This command generates boilerplate code for user authentication, including models, schemas, and routers.

svc-infra-scaffold scaffold-auth \
  --models-path "apps/core/models/user.py" \
  --schemas-path "apps/core/schemas/user.py" \
  --routers-path "apps/api/users/router.py" \
  --package-name users
"""