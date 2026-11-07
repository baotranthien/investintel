import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"trading-pytest-{uuid4().hex}.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"

from database.connection import engine, init_db


@pytest.fixture(scope="session", autouse=True)
def initialize_database():
    """Ensure schema exists and the active SQLite test database is canonical-seeded once per session."""
    init_db()

    from services.ingestion.seed_data import run_seed
    run_seed()

    from scripts.seed_bank_and_commodity_data import (
        seed_energy_stock_prices,
        seed_plx_quarterly_statements,
        seed_bmp_prices,
        seed_bmp_corporate_actions,
        seed_bank_metrics,
        seed_macro_commodities,
    )
    from database.connection import SessionLocal
    db = SessionLocal()
    try:
        seed_energy_stock_prices(db)
        seed_plx_quarterly_statements(db)
        seed_bmp_prices(db)
        seed_bmp_corporate_actions(db)
        seed_bank_metrics(db)
        seed_macro_commodities(db)
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """
    Function-scoped database session fixture with transaction isolation.
    Uses nested transaction (savepoint) so that each test can call session.commit()
    without leaking changes to the database or subsequent tests.
    On teardown, the outer transaction is rolled back, leaving the database pristine.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
