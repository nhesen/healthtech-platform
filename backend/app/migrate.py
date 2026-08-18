"""Idempotent database migration command used by local and cloud deployments."""
from .database import DATABASE_KIND, DB_PATH
from .main import SCHEMA, db, migrate


def main() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
    target = DB_PATH if DATABASE_KIND == "sqlite" else "configured PostgreSQL database"
    print(f"PASS migrations applied to {target}")


if __name__ == "__main__":
    main()
