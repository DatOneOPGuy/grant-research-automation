"""Alembic environment.

The URL comes from DATABASE_URL at runtime, never from alembic.ini -- the ini
is committed and a DSN carries a password. Run from this directory (the same
WorkingDirectory the systemd unit requires), so `import config` resolves the
way it does for the app.
"""

from logging.config import fileConfig

from alembic import context
from models_db import Base
from sqlalchemy import engine_from_config, pool

import config as app_config

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

if not app_config.DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Migrations need an explicit target; there "
        "is no default to fall back to.")

alembic_config.set_main_option(
    "sqlalchemy.url", app_config.DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=app_config.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection,
                          target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
