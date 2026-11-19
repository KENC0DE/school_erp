from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

import core.models_registry  # noqa: F401
from alembic import context
from app.settings import get_settings
from core.db.base import Base
from core.modules.registry import ModuleRegistry
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata

# One branch per module plus `core` (ARCH §4.6). Set ALEMBIC_MODULE to choose
# which branch's tables autogenerate should consider.
registry = ModuleRegistry.load()
MODULE_KEYS = [manifest.key for manifest in registry.all()]
SELECTED_MODULE = os.getenv("ALEMBIC_MODULE", "core").strip() or "core"

# Tables whose names do not start with their module key. Document Studio uses
# the architecture's `doc_` prefix and the `issued_documents` table name, but all
# of them belong to the `documents` branch.
TABLE_ALIASES = {
    "doc_templates": "documents",
    "doc_template_versions": "documents",
    "doc_fields_registry": "documents",
    "issued_documents": "documents",
}


def table_module(name: str) -> str:
    if name in TABLE_ALIASES:
        return TABLE_ALIASES[name]
    for key in MODULE_KEYS:
        if name.startswith(f"{key}_"):
            return key
    return "core"


def include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    if type_ == "table":
        if name == "alembic_version":
            return False
        return table_module(name) == SELECTED_MODULE
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
