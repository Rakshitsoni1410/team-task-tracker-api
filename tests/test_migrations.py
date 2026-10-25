"""The Alembic migration must build exactly the schema the models describe."""
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from alembic import command
from app.database import Base

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {"users", "projects", "project_members", "tasks"}


@pytest.fixture
def migrated_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
    yield engine, cfg
    engine.dispose()


def test_upgrade_creates_all_tables(migrated_engine):
    engine, _ = migrated_engine
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_migration_matches_models_with_no_drift(migrated_engine):
    engine, _ = migrated_engine
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], f"models and migration disagree: {diff}"


def test_downgrade_removes_everything(migrated_engine):
    engine, cfg = migrated_engine
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.downgrade(cfg, "base")
    assert not (EXPECTED_TABLES & set(inspect(engine).get_table_names()))
