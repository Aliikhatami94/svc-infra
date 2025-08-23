import argparse
from .alembic_helpers import ensure_initted, make_migration, upgrade, downgrade


def main() -> None:
    p = argparse.ArgumentParser(description="svc_infra.db Alembic helper CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Initialize alembic and write async env template")
    sub.add_parser("makemigrations", help="Create a new migration").add_argument(
        "-m", "--message", default="auto", help="Migration message"
    )
    sub.add_parser("upgrade", help="Upgrade to a target revision").add_argument(
        "target", nargs="?", default="head"
    )
    sub.add_parser("downgrade", help="Downgrade to a target revision").add_argument(
        "target", nargs="?", default="-1"
    )

    args = p.parse_args()
    if args.cmd == "init":
        ensure_initted()
    elif args.cmd == "makemigrations":
        make_migration(args.message)
    elif args.cmd == "upgrade":
        upgrade(args.target)
    else:
        downgrade(args.target)


if __name__ == "__main__":
    main()

