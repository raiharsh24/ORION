"""
Database migration utility wrapping Alembic.

Usage:
    python -m app.kernel.migrate upgrade   # Apply all pending migrations
    python -m app.kernel.migrate downgrade  # Rollback last migration
    python -m app.kernel.migrate status     # Show current migration state
    python -m app.kernel.migrate create <message>  # Create new migration
"""
import sys
import os
import sqlite3
from loguru import logger

def run_database_migrations(db_path: str) -> None:
    """
    Programmatically run Alembic migrations on the given SQLite database path.
    Preserves existing databases by checking if tables already exist and stamping them.
    """
    try:
        from alembic.config import Config
        from alembic import command
    except ModuleNotFoundError:
        logger.warning("Alembic package not available. Initializing SQLite tables manually...")
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS memory_kv (key TEXT PRIMARY KEY, value TEXT)")
            conn.commit()
            conn.close()
            logger.info("Manual SQLite database tables initialized successfully.")
            return
        except sqlite3.Error as e:
            logger.error(f"Failed to manually initialize SQLite database: {e}")
            raise

    # Ensure the parent directory of the database file exists
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Check database state before running migrations to preserve existing tables
    has_memory_kv = False
    has_alembic_version = False
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            cursor = conn.cursor()
            # Check if memory_kv table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_kv'")
            has_memory_kv = cursor.fetchone() is not None

            # Check if alembic_version table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            has_alembic_version = cursor.fetchone() is not None
            conn.close()
        except sqlite3.Error as e:
            logger.warning(f"Error checking database table status: {e}")

    # Resolve paths relative to this file's directory
    # migrate.py is at app/kernel/migrate.py
    # alembic.ini is at services/friday-api/alembic.ini (two directories up)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ini_path = os.path.join(base_dir, "alembic.ini")
    script_loc = os.path.join(base_dir, "alembic")

    # Set up Alembic Config
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{os.path.abspath(db_path)}")
    alembic_cfg.set_main_option("script_location", script_loc)

    # If the user has an existing database with the old tables, stamp the version to 001 (initial_schema)
    if has_memory_kv and not has_alembic_version:
        logger.info(f"Database at {db_path} contains existing 'memory_kv' table but is unversioned. Stamping to revision '001'...")
        try:
            command.stamp(alembic_cfg, "001")
        except Exception as e:
            logger.error(f"Failed to stamp database to revision '001': {e}")
            raise

    # Run migrations to target 'head'
    logger.info(f"Applying database migrations to {db_path}...")
    try:
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully.")
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        raise


def get_default_db_path() -> str:
    """Resolve the default database path based on configuration / environment."""
    persist_dir = os.getenv("FRIDAY_PERSIST_DIR", ".friday_kb")
    return os.path.join(persist_dir, "friday_memory.db")


def run_alembic_cli(args: list[str], db_path: str) -> None:
    from alembic.config import Config
    from alembic import command

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ini_path = os.path.join(base_dir, "alembic.ini")
    script_loc = os.path.join(base_dir, "alembic")

    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{os.path.abspath(db_path)}")
    alembic_cfg.set_main_option("script_location", script_loc)

    if not args:
        print(__doc__)
        sys.exit(1)

    cmd_name = args[0]
    extra = args[1:]

    if cmd_name == "upgrade":
        revision = extra[0] if extra else "head"
        command.upgrade(alembic_cfg, revision)
    elif cmd_name == "downgrade":
        revision = extra[0] if extra else "-1"
        command.downgrade(alembic_cfg, revision)
    elif cmd_name == "status":
        command.current(alembic_cfg)
    elif cmd_name == "create":
        if not extra:
            print("Error: migration message required")
            sys.exit(1)
        command.revision(alembic_cfg, message=extra[0], autogenerate=True)
    elif cmd_name == "history":
        command.history(alembic_cfg)
    else:
        print(f"Unknown command: {cmd_name}")
        print(__doc__)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    db_path = get_default_db_path()
    run_alembic_cli(sys.argv[1:], db_path)


if __name__ == "__main__":
    main()

