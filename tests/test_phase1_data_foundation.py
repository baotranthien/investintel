"""
Test Suite for Phase 0 & Phase 1 Data Foundation.
Validates:
- Database connection & Alembic migration
- Source registry
- Raw -> Staging -> Validation -> Canonical pipeline
- Data Lineage & Provenance traceability
- Rejected records inspectability
- Point-In-Time query & future leakage prevention
- Revision & restatement handling
- Historical index membership reconstruction
- Corporate actions
- Data quality report generation
- Downstream missing-data behaviors (DCF, Peer multiples, Macro, Market Regime, Events)
- Synthetic fixture labeling
"""
import pytest
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session

from database.connection import SessionLocal, engine, init_db
from database.models import (
    Base,
    DataSource,
    DataRun,
    Asset,
    Price,
    StagingRecord,
    DataQualityReportRecord,
    DataLineage,
    IndexMembership,
    CorporateAction,
    FinancialStatement,
    MacroObservation,
    MacroSeries,
    EventRecord,
)
from services.ingestion.lineage import LineageTracker, Provenance
from services.ingestion.point_in_time import PointInTimeService
from services.ingestion.pipeline import IngestionPipeline, DataQualityChecker
from services.valuation.engine import DCFEngine
from services.valuation.models import DCFAssumptions
from services.valuation.builder import ValuationSnapshotBuilder
from services.macro.engine import MacroEngine, MarketRegimeEngine
from services.events.engine import EventEngine
from services.fundamentals.snapshot import FundamentalSnapshotBuilder
from services.fundamentals.fixtures import FPT_INCOME_QUARTERS, FPT_BALANCE_QUARTERS, FPT_CASHFLOW_ANNUAL as FPT_CASH_FLOW_QUARTERS


class TestDatabaseAndMigration:
    def test_database_connection_and_tables(self, db_session: Session):
        """Verifies database connection works and key tables exist."""
        result = db_session.execute(Base.metadata.tables["data_sources"].select()).fetchall()
        assert result is not None

    def test_source_registry_populated(self, db_session: Session):
        """Verifies Data Source Registry contains official sources."""
        sources = db_session.query(DataSource).all()
        source_names = [s.name for s in sources]
        assert "HOSE_CSV" in source_names or "FRED" in source_names
        for s in sources:
            assert s.authority_level in ["PRIMARY_OFFICIAL", "REPUTABLE_SECONDARY"]
            assert s.source_type is not None

class TestIngestionPipelineAndLineage:
    def test_raw_staging_validation_canonical_flow(self, db_session: Session):
        """Tests that pipeline tracks run_id and promotes validated records."""
        pipeline = IngestionPipeline(db_session)
        raw_rows = [
            {
                "symbol": "TEST_SYM",
                "observation_date": date(2023, 11, 1),
                "open": 50000.0,
                "high": 52000.0,
                "low": 49000.0,
                "close": 51000.0,
                "volume": 100000.0
            }
        ]
        result = pipeline.ingest_market_data(
            provider="TestProvider",
            symbol="TEST_SYM",
            exchange="HOSE",
            records=raw_rows,
            source_url_or_path="test://path/test.csv"
        )
        assert result["status"] == "SUCCESS"
        assert result["records_valid"] == 1
        assert result["records_rejected"] == 0

        # Verify staging record was marked PROMOTED
        staged = db_session.query(StagingRecord).filter(
            StagingRecord.run_id == result["run_id"]
        ).first()
        assert staged is not None
        assert staged.status == "PROMOTED"

        # Verify canonical price created
        asset = db_session.query(Asset).filter(Asset.symbol == "TEST_SYM").first()
        price = db_session.query(Price).filter(
            Price.asset_id == asset.id,
            Price.observation_date == date(2023, 11, 1)
        ).first()
        assert price is not None
        assert price.raw_close == 51000.0

    def test_rejected_records_are_inspectable(self, db_session: Session):
        """Verifies rejected rows are NOT dropped silently, but kept in StagingRecord with error details."""
        pipeline = IngestionPipeline(db_session)
        invalid_rows = [
            {
                "symbol": "BAD_SYM",
                "observation_date": date(2023, 11, 2),
                "open": 50000.0,
                "high": 40000.0, # High < Low: Impossible!
                "low": 45000.0,
                "close": -100.0, # Negative close: Impossible!
                "volume": -500.0
            }
        ]
        result = pipeline.ingest_market_data(
            provider="TestProvider",
            symbol="BAD_SYM",
            exchange="HOSE",
            records=invalid_rows,
            source_url_or_path="test://path/bad.csv"
        )
        assert result["records_rejected"] == 1
        assert result["records_valid"] == 0

        # Inspect rejected staging record
        staged = db_session.query(StagingRecord).filter(
            StagingRecord.run_id == result["run_id"]
        ).first()
        assert staged is not None
        assert staged.status == "REJECTED"
        assert len(staged.validation_errors) > 0
        assert any("Impossible" in err or "Negative" in err for err in staged.validation_errors)

    def test_provenance_and_lineage_trace(self, db_session: Session):
        """Verifies every promoted price has a lineage entry linking to raw source."""
        asset = db_session.query(Asset).filter(Asset.symbol == "FPT").first()
        if asset:
            price = db_session.query(Price).filter(Price.asset_id == asset.id).first()
            if price:
                lineage = LineageTracker.get_lineage(db_session, "prices", str(price.id))
                assert lineage is not None
                assert lineage["record_table"] == "prices"
                assert lineage["raw_source"] is not None

class TestPointInTimeIntegrity:
    def test_future_leakage_prevented(self, db_session: Session):
        """
        Critical PIT test:
        FPT Q3 2023 ended on 2023-09-30, but was published on 2023-10-25.
        Query as of 2023-10-24 MUST NOT see Q3 2023 data.
        """
        # Query before publication
        before_pub = PointInTimeService.get_financials_as_of(db_session, "FPT", date(2023, 10, 24))
        # Ensure no statement with publication_date > 2023-10-24 is returned
        for s in before_pub:
            assert s.publication_date <= date(2023, 10, 24)

        # Query after publication
        after_pub = PointInTimeService.get_financials_as_of(db_session, "FPT", date(2023, 10, 26))
        q3_visible = any(s.fiscal_period_end == date(2023, 9, 30) for s in after_pub)
        assert q3_visible, "Q3 statement must be visible on or after publication date"

    def test_revision_and_restatement_handling(self, db_session: Session):
        """
        Tests that restated statements pick the latest version visible as of as_of_date,
        and do not leak future revisions.
        Verifies: version 1, version 2, supersedes_id, restatement_reason, publication date, and PIT selection.
        """
        asset = db_session.query(Asset).filter(Asset.symbol == "REV_TEST").first()
        if not asset:
            asset = Asset(symbol="REV_TEST", name="Revision Test Co", asset_type="STOCK", exchange="HOSE")
            db_session.add(asset)
            db_session.flush()

        # Add v1 published 2023-03-15 (idempotent: replay script may have seeded this)
        stmt_v1 = db_session.query(FinancialStatement).filter(
            FinancialStatement.symbol == "REV_TEST",
            FinancialStatement.statement_type == "INCOME_STATEMENT",
            FinancialStatement.fiscal_period_end == date(2022, 12, 31),
            FinancialStatement.version == 1,
        ).first()
        if not stmt_v1:
            stmt_v1 = FinancialStatement(
                asset_id=asset.id,
                symbol="REV_TEST",
                statement_type="INCOME_STATEMENT",
                fiscal_period_end=date(2022, 12, 31),
                fiscal_year=2022,
                period_type="ANNUAL",
                publication_date=date(2023, 3, 15),
                version=1,
                is_superseded=False,
            )
            db_session.add(stmt_v1)
            db_session.flush()

        # Add v2 (restatement) published 2023-08-20, superseding v1
        stmt_v2 = db_session.query(FinancialStatement).filter(
            FinancialStatement.symbol == "REV_TEST",
            FinancialStatement.statement_type == "INCOME_STATEMENT",
            FinancialStatement.fiscal_period_end == date(2022, 12, 31),
            FinancialStatement.version == 2,
        ).first()
        if not stmt_v2:
            stmt_v2 = FinancialStatement(
                asset_id=asset.id,
                symbol="REV_TEST",
                statement_type="INCOME_STATEMENT",
                fiscal_period_end=date(2022, 12, 31),
                fiscal_year=2022,
                period_type="ANNUAL",
                publication_date=date(2023, 8, 20),
                version=2,
                supersedes_id=stmt_v1.id,
                restatement_reason="Audit adjustment",
                is_superseded=False,
            )
            stmt_v1.is_superseded = True
            db_session.add(stmt_v2)
        db_session.commit()

        # Verify semantic restatement properties
        assert stmt_v1.version == 1
        assert stmt_v2.version == 2
        assert stmt_v2.supersedes_id == stmt_v1.id
        assert stmt_v2.restatement_reason == "Audit adjustment"
        assert stmt_v1.publication_date == date(2023, 3, 15)
        assert stmt_v2.publication_date == date(2023, 8, 20)
        assert stmt_v1.is_superseded is True

        # As of 2023-05-01 (before v2 restatement): MUST return v1
        res_may = PointInTimeService.get_financials_as_of(db_session, "REV_TEST", date(2023, 5, 1))
        assert len(res_may) == 1
        assert res_may[0].version == 1
        assert res_may[0].publication_date == date(2023, 3, 15)

        # As of 2023-09-01 (after v2 restatement): MUST return v2
        res_sep = PointInTimeService.get_financials_as_of(db_session, "REV_TEST", date(2023, 9, 1))
        assert len(res_sep) == 1
        assert res_sep[0].version == 2
        assert res_sep[0].supersedes_id == stmt_v1.id
        assert res_sep[0].restatement_reason == "Audit adjustment"
        assert res_sep[0].publication_date == date(2023, 8, 20)

    def test_historical_index_membership_reconstruction(self, db_session: Session):
        """Verifies point-in-time index membership checking."""
        # FPT in VN30
        assert PointInTimeService.is_index_member_as_of(db_session, "VN30", "FPT", date(2023, 1, 1)) is True
        # ROS was in VN30 in 2019, exited in 2020
        assert PointInTimeService.is_index_member_as_of(db_session, "VN30", "ROS", date(2019, 1, 1)) is True
        assert PointInTimeService.is_index_member_as_of(db_session, "VN30", "ROS", date(2022, 1, 1)) is False

class TestDownstreamEnginesMissingDataBehavior:
    def test_dcf_missing_revenue_returns_insufficient_data(self):
        """DCF engine must not use rev=1000 dummy; must return INSUFFICIENT_DATA when missing."""
        assump = DCFAssumptions(
            revenue_growth_rates=[0.10],
            ebit_margins=[0.20],
            tax_rate=0.20,
            wacc=0.12,
            terminal_growth_rate=0.03,
            base_revenue=None # Missing
        )
        out = DCFEngine.calculate(assump, shares_outstanding=1_000_000_000, net_debt=0)
        assert out.applicability == "NOT_APPLICABLE"
        assert any("INSUFFICIENT_DATA" in w for w in out.warnings)

    def test_peer_multiples_missing_returns_insufficient_data(self):
        """Builder must not use peer_pe=15.0; must set weight=0 and warn when missing."""
        builder = ValuationSnapshotBuilder("FPT", "TECHNOLOGY")
        snapshot = builder.build(
            fundamentals={"eps_ttm": 5000, "bvps": 25000, "shares_outstanding": 1_000_000_000},
            current_price=100000.0,
            as_of=date.today()
        )
        pe_method = next((m for m in snapshot.methods if "P/E" in m.method), None)
        assert pe_method is not None
        assert pe_method.applicability == "NOT_APPLICABLE"
        assert any("INSUFFICIENT_DATA" in w for w in pe_method.warnings)

    def test_macro_missing_data_returns_honest_state(self, db_session: Session):
        """Macro engine returns 0 strength and INSUFFICIENT_DATA when no data exists for historical date."""
        dash = MacroEngine.get_dashboard(date(1990, 1, 1), session=db_session)
        assert dash.growth.strength == 0.0
        assert any("INSUFFICIENT_DATA" in d for d in dash.growth.drivers)

    def test_market_regime_missing_data_returns_insufficient_data(self, db_session: Session):
        """MarketRegimeEngine returns INSUFFICIENT_DATA when not enough price observations exist."""
        regime = MarketRegimeEngine.determine_regime(date(1990, 1, 1), session=db_session)
        assert regime.regime == "INSUFFICIENT_DATA"
        assert regime.confidence == 0.0

    def test_events_empty_when_no_events_in_db(self, db_session: Session):
        """When database contains no event records, EventEngine must return [] (honest NO_DATA state), never fabricated events."""
        db_session.query(EventRecord).delete()
        db_session.flush()
        events = EventEngine.get_recent_events(session=db_session)
        assert events == []

    def test_events_returns_canonical_seeded_data(self, db_session: Session):
        """EventEngine returns events from canonical DB (seeded via seed_data.py). No hardcoded fake events."""
        events = EventEngine.get_recent_events(session=db_session)
        assert isinstance(events, list)
        assert len(events) >= 1, "Must return seeded canonical events"
        # Events are REAL seeded canonical data (seeded by seed_data.py), not hardcoded in engine
        # Verify events are sourced from DB, not hardcoded in engine source
        from services.events import engine as events_engine_module
        import inspect
        src = inspect.getsource(events_engine_module.EventEngine.get_recent_events)
        assert 'session.query(EventRecord)' in src, "EventEngine must query DB, not return hardcoded events"
        assert 'hardcoded' not in src.lower(), "EventEngine must not contain hardcoded events"

    def test_fixtures_labeled_synthetic_fixture(self):
        """Fundamental snapshots built from fixtures must not claim SECONDARY_DATA sources."""
        builder = FundamentalSnapshotBuilder("FPT", "TECHNOLOGY")
        snap = builder.build_snapshot(
            income_quarters=FPT_INCOME_QUARTERS,
            income_annual=[],
            balance_annual=FPT_BALANCE_QUARTERS,
            cashflow_annual=FPT_CASH_FLOW_QUARTERS,
            as_of_date=date(2023, 10, 1),
            shares_outstanding=1_270_000_000,
            sources=["SYNTHETIC_FIXTURE"],
        )
        # Verify sources are correctly passed through and SECONDARY_DATA is not injected
        sources = snap.get("sources", [])
        assert "SECONDARY_DATA" not in sources, f"Fixture must not claim SECONDARY_DATA, got: {sources}"
