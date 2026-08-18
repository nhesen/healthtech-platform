"""Explicit, repeatable command for restoring the synthetic demo dataset."""
from .main import DB_PATH, ROOT, SCHEMA, _remove_demo_uploads, db, migrate
from .demo_seed import demo_readiness, reset_demo_data


def main() -> None:
    with db() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
        paths = reset_demo_data(conn)
        status = demo_readiness(conn, ROOT / "demo_documents" / "hasan_lab_report.pdf")
    _remove_demo_uploads(paths)
    print(f"PASS demo seed v{status['version']} restored at {DB_PATH}")


if __name__ == "__main__":
    main()
