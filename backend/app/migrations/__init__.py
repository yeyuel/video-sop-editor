from app.migrations.runner import run_migrations

run_sqlite_migrations = run_migrations

__all__ = ["run_migrations", "run_sqlite_migrations"]
