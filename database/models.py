"""
Database models for Investment Intelligence Platform.
Phase 2: Fundamental Engine — Financial Statement schema, normalized financials,
derived metrics, quality flags, formula registry.
"""
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Boolean, Text,
    func, MetaData, ForeignKey, Date, UniqueConstraint, Index, JSON, Numeric,
    CheckConstraint
)

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class DataSource(Base, TimestampMixin):
    __tablename__ = 'data_sources'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    provider = Column(String, nullable=False) # e.g. BLS, FRED, NSO
    country = Column(String)
    authority_level = Column(String) # PRIMARY_OFFICIAL, REPUTABLE_SECONDARY, etc.
    source_type = Column(String) # WEB/XLS, API
    base_url = Column(String)
    license_status = Column(String)
    terms_url = Column(String)
    access_method = Column(String)
    active = Column(Boolean, default=True)

class DataRun(Base):
    __tablename__ = 'data_runs'
    run_id = Column(String, primary_key=True)
    provider = Column(String, nullable=False)
    dataset = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String, nullable=False) # SUCCESS, FAILURE, PARTIAL
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_rejected = Column(Integer, default=0)
    errors = Column(String)
    warnings = Column(String)

class Asset(Base, TimestampMixin):
    __tablename__ = 'assets'
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    asset_type = Column(String, nullable=False) # STOCK, ETF, MUTUAL_FUND, INDEX
    exchange = Column(String)
    sector = Column(String)
    currency = Column(String, default="VND")
    isin = Column(String)
    status = Column(String, default="ACTIVE")
    listed_date = Column(Date)
    delisted_date = Column(Date)

class Price(Base, TimestampMixin):
    __tablename__ = 'prices'
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    observation_date = Column(Date, nullable=False)
    raw_open = Column(Float)
    raw_high = Column(Float)
    raw_low = Column(Float)
    raw_close = Column(Float, nullable=False)
    adjusted_close = Column(Float)
    adjustment_factor = Column(Float, default=1.0)
    volume = Column(Float)
    turnover = Column(Float)
    source = Column(String)
    data_quality_score = Column(Float)
    status = Column(String, default="VALID")
    __table_args__ = (UniqueConstraint('asset_id', 'observation_date', name='uq_asset_date'),)

class MacroSeries(Base, TimestampMixin):
    __tablename__ = 'macro_series'
    id = Column(String, primary_key=True, index=True) # e.g. us_cpi
    name = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    frequency = Column(String, nullable=False) # DAILY, MONTHLY, etc.
    unit = Column(String, nullable=False)
    currency = Column(String)
    scale = Column(String)
    source_id = Column(Integer, ForeignKey('data_sources.id'))

class MacroObservation(Base, TimestampMixin):
    __tablename__ = 'macro_observations'
    id = Column(Integer, primary_key=True, index=True)
    series_id = Column(String, ForeignKey('macro_series.id'), nullable=False)
    observation_date = Column(Date, nullable=False)
    release_date = Column(Date)
    revision_date = Column(Date)
    vintage = Column(String) # e.g. 2023-Q1-v1
    value = Column(Float, nullable=False)
    version = Column(Integer, default=1)
    published_at = Column(DateTime(timezone=True))
    supersedes_id = Column(Integer, ForeignKey('macro_observations.id'))
    status = Column(String, default="VALID") # VALID, ANOMALY
    anomaly = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('series_id', 'observation_date', 'version', name='uq_series_date_version'),)

class DataLineage(Base, TimestampMixin):
    __tablename__ = 'data_lineages'
    id = Column(Integer, primary_key=True, index=True)
    record_table = Column(String, nullable=False)
    record_id = Column(String, nullable=False)
    raw_source = Column(String)
    url = Column(String)
    retrieved_at = Column(DateTime(timezone=True))
    checksum = Column(String)


class Document(Base, TimestampMixin):
    """Local document registry for 6G retrieval; source metadata must stay explicit."""
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, nullable=False, index=True)
    ticker = Column(String, index=True)
    company = Column(String)
    source = Column(String, nullable=False)
    publication_date = Column(Date, index=True)
    period = Column(String)
    document_type = Column(String)
    language = Column(String, default='en')
    version = Column(String, default='1')
    checksum = Column(String)
    title = Column(String)
    raw_text = Column(Text)
    status = Column(String, default='READY')
    is_synthetic = Column(Boolean, default=False)
    metadata_json = Column(JSON, default=dict)


class DocumentChunk(Base, TimestampMixin):
    """Chunk-level document storage for local vector retrieval and evidence tracing."""
    __tablename__ = 'document_chunks'
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, ForeignKey('documents.document_id'), nullable=False, index=True)
    chunk_id = Column(String, unique=True, nullable=False, index=True)
    section = Column(String)
    page_reference = Column(String)
    text = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)
    embedding_model = Column(String, default='NOT_CONFIGURED')
    embedding_version = Column(String, default='NOT_CONFIGURED')
    embedding = Column(JSON)


# ─────────────────────────────────────────────────────────
# PHASE 2: FINANCIAL STATEMENTS
# ─────────────────────────────────────────────────────────

class FinancialStatement(Base, TimestampMixin):
    """
    Raw financial statement filing. One row per (company, period, statement_type, version).
    Supports restatement via version + supersedes_id.
    """
    __tablename__ = 'financial_statements'
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    statement_type = Column(String, nullable=False)
    # INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, NOTES, ANNUAL_REPORT, QUARTERLY

    # Period
    fiscal_period_start = Column(Date)
    fiscal_period_end = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer, index=True)
    fiscal_quarter = Column(Integer)  # 1-4, NULL for annual
    period_type = Column(String, nullable=False)  # ANNUAL, QUARTERLY, SEMI_ANNUAL, TTM

    # Dates
    statement_date = Column(Date)
    publication_date = Column(Date, index=True)

    # Consolidation
    consolidation = Column(String, default="CONSOLIDATED")
    # CONSOLIDATED, PARENT_ONLY, SUBSIDIARY

    # Source
    source_id = Column(Integer, ForeignKey('data_sources.id'))
    source_name = Column(String)
    source_url = Column(String)
    raw_file_checksum = Column(String)

    # Currency / Unit
    currency = Column(String, nullable=False, default="VND")
    unit_scale = Column(String, nullable=False, default="BILLION_VND")
    # UNIT, THOUSAND, MILLION, BILLION, BILLION_VND

    # Audit
    is_audited = Column(Boolean, default=False)
    auditor = Column(String)

    # Versioning / Restatement
    version = Column(Integer, default=1)
    supersedes_id = Column(Integer, ForeignKey('financial_statements.id'))
    is_superseded = Column(Boolean, default=False)
    restatement_reason = Column(Text)

    # Status
    status = Column(String, default="VALID")  # VALID, SUSPECT, SUPERSEDED

    # Raw JSON payload (original parsed data)
    raw_data = Column(JSON)

    __table_args__ = (
        UniqueConstraint('symbol', 'statement_type', 'fiscal_period_end',
                         'period_type', 'consolidation', 'version',
                         name='uq_statement_period_version'),
        Index('ix_statement_symbol_period', 'symbol', 'fiscal_period_end'),
    )


class FinancialLineItem(Base, TimestampMixin):
    """Individual line items from financial statements."""
    __tablename__ = 'financial_line_items'
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey('financial_statements.id'), nullable=False, index=True)

    raw_label = Column(String, nullable=False)
    canonical_metric = Column(String, index=True)
    canonical_section = Column(String)  # income, balance_sheet, cash_flow

    raw_value = Column(Numeric(precision=30, scale=6))
    value_status = Column(String, default="ACTUAL")
    # ACTUAL, DERIVED, ESTIMATED, IMPUTED

    sign_convention = Column(String)   # POSITIVE, NEGATIVE
    currency = Column(String)
    unit_scale = Column(String)

    is_one_off = Column(Boolean, default=False)
    one_off_reason = Column(String)
    is_non_recurring = Column(Boolean, default=False)

    data_quality = Column(String, default="VALID")
    mapping_version = Column(String)


class LineItemMapping(Base, TimestampMixin):
    """Configurable mapping: provider-specific label → canonical metric."""
    __tablename__ = 'line_item_mappings'
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    raw_label = Column(String, nullable=False)
    canonical_metric = Column(String, nullable=False)
    statement_type = Column(String, nullable=False)
    canonical_section = Column(String)
    sign_convention = Column(String, default="POSITIVE")
    version = Column(String, default="v1")
    is_active = Column(Boolean, default=True)
    notes = Column(Text)
    __table_args__ = (
        UniqueConstraint('source', 'raw_label', 'version', name='uq_mapping_source_label_ver'),
    )


# ─────────────────────────────────────────────────────────
# NORMALIZED FINANCIALS
# ─────────────────────────────────────────────────────────

class NormalizedIncome(Base, TimestampMixin):
    """Normalized income statement — canonical schema."""
    __tablename__ = 'normalized_income'
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey('financial_statements.id'), nullable=False)
    symbol = Column(String, nullable=False, index=True)
    fiscal_period_end = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer)
    fiscal_quarter = Column(Integer)
    period_type = Column(String, nullable=False)
    currency = Column(String, default="VND")
    unit_scale = Column(String, default="BILLION_VND")

    revenue = Column(Numeric(30, 6))
    cost_of_goods_sold = Column(Numeric(30, 6))
    gross_profit = Column(Numeric(30, 6))
    selling_expense = Column(Numeric(30, 6))
    general_admin_expense = Column(Numeric(30, 6))
    operating_expense = Column(Numeric(30, 6))
    operating_income = Column(Numeric(30, 6))
    ebit = Column(Numeric(30, 6))
    ebitda = Column(Numeric(30, 6))
    interest_income = Column(Numeric(30, 6))
    interest_expense = Column(Numeric(30, 6))
    other_income = Column(Numeric(30, 6))
    other_expense = Column(Numeric(30, 6))
    pre_tax_income = Column(Numeric(30, 6))
    income_tax = Column(Numeric(30, 6))
    net_income = Column(Numeric(30, 6))
    minority_interest = Column(Numeric(30, 6))
    net_income_parent = Column(Numeric(30, 6))
    eps_basic = Column(Numeric(30, 6))
    eps_diluted = Column(Numeric(30, 6))
    shares_basic = Column(Numeric(30, 6))
    shares_diluted = Column(Numeric(30, 6))

    # Quality metadata {metric: data_status}
    field_quality = Column(JSON)
    data_completeness = Column(Float)

    __table_args__ = (
        UniqueConstraint('symbol', 'fiscal_period_end', 'period_type',
                         name='uq_norm_income_symbol_period'),
    )


class NormalizedBalanceSheet(Base, TimestampMixin):
    """Normalized balance sheet — canonical schema."""
    __tablename__ = 'normalized_balance_sheets'
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey('financial_statements.id'), nullable=False)
    symbol = Column(String, nullable=False, index=True)
    fiscal_period_end = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer)
    fiscal_quarter = Column(Integer)
    period_type = Column(String, nullable=False)
    currency = Column(String, default="VND")
    unit_scale = Column(String, default="BILLION_VND")

    # Current assets
    cash = Column(Numeric(30, 6))
    short_term_investments = Column(Numeric(30, 6))
    accounts_receivable = Column(Numeric(30, 6))
    inventory = Column(Numeric(30, 6))
    other_current_assets = Column(Numeric(30, 6))
    total_current_assets = Column(Numeric(30, 6))

    # Non-current assets
    ppe = Column(Numeric(30, 6))
    intangibles = Column(Numeric(30, 6))
    long_term_investments = Column(Numeric(30, 6))
    other_non_current_assets = Column(Numeric(30, 6))
    total_assets = Column(Numeric(30, 6))

    # Current liabilities
    accounts_payable = Column(Numeric(30, 6))
    short_term_debt = Column(Numeric(30, 6))
    other_current_liabilities = Column(Numeric(30, 6))
    total_current_liabilities = Column(Numeric(30, 6))

    # Non-current liabilities
    long_term_debt = Column(Numeric(30, 6))
    other_non_current_liabilities = Column(Numeric(30, 6))
    total_liabilities = Column(Numeric(30, 6))

    # Equity
    share_capital = Column(Numeric(30, 6))
    retained_earnings = Column(Numeric(30, 6))
    other_equity = Column(Numeric(30, 6))
    minority_interest = Column(Numeric(30, 6))
    total_equity = Column(Numeric(30, 6))
    equity_parent = Column(Numeric(30, 6))

    # Bank-specific
    loans_and_advances = Column(Numeric(30, 6))
    customer_deposits = Column(Numeric(30, 6))
    provisions = Column(Numeric(30, 6))
    npl_gross = Column(Numeric(30, 6))
    npl_ratio = Column(Numeric(30, 6))

    field_quality = Column(JSON)
    data_completeness = Column(Float)

    __table_args__ = (
        UniqueConstraint('symbol', 'fiscal_period_end', 'period_type',
                         name='uq_norm_bs_symbol_period'),
    )


class NormalizedCashFlow(Base, TimestampMixin):
    """Normalized cash flow statement — canonical schema."""
    __tablename__ = 'normalized_cash_flows'
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey('financial_statements.id'), nullable=False)
    symbol = Column(String, nullable=False, index=True)
    fiscal_period_end = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer)
    fiscal_quarter = Column(Integer)
    period_type = Column(String, nullable=False)
    currency = Column(String, default="VND")
    unit_scale = Column(String, default="BILLION_VND")

    cash_from_operations = Column(Numeric(30, 6))
    cash_from_investing = Column(Numeric(30, 6))
    cash_from_financing = Column(Numeric(30, 6))

    capex = Column(Numeric(30, 6))
    dividends_paid = Column(Numeric(30, 6))
    debt_issued = Column(Numeric(30, 6))
    debt_repaid = Column(Numeric(30, 6))
    share_issuance = Column(Numeric(30, 6))
    share_buyback = Column(Numeric(30, 6))
    depreciation_amortization = Column(Numeric(30, 6))

    free_cash_flow = Column(Numeric(30, 6))  # = CFO - Capex

    field_quality = Column(JSON)
    data_completeness = Column(Float)

    __table_args__ = (
        UniqueConstraint('symbol', 'fiscal_period_end', 'period_type',
                         name='uq_norm_cf_symbol_period'),
    )


# ─────────────────────────────────────────────────────────
# DERIVED METRICS & SNAPSHOTS
# ─────────────────────────────────────────────────────────

class FundamentalMetric(Base, TimestampMixin):
    """Derived metrics (ratios, growth rates) with full provenance."""
    __tablename__ = 'fundamental_metrics'
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    fiscal_period_end = Column(Date, nullable=False, index=True)
    period_type = Column(String, nullable=False)

    metric_id = Column(String, nullable=False, index=True)
    metric_category = Column(String)
    metric_name = Column(String)
    calculation_version = Column(String, nullable=False)

    value = Column(Numeric(30, 8))
    unit = Column(String)
    value_status = Column(String, default="VALID")
    # VALID, NOT_MEANINGFUL, MISSING_DATA, NEGATIVE_DENOMINATOR, INSUFFICIENT_HISTORY
    not_meaningful_reason = Column(String)

    input_statement_ids = Column(JSON)
    input_metric_ids = Column(JSON)
    dependency_graph = Column(JSON)

    as_of_publication_date = Column(Date)
    data_quality_score = Column(Float)
    data_status = Column(String, default="VALID")
    depends_on_suspect = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint('symbol', 'fiscal_period_end', 'period_type', 'metric_id',
                         'calculation_version', name='uq_metric_symbol_period_metric'),
        Index('ix_metric_symbol_metric_id', 'symbol', 'metric_id'),
    )


class FundamentalSnapshot(Base, TimestampMixin):
    """Full company fundamental snapshot — JSON blob for fast retrieval."""
    __tablename__ = 'fundamental_snapshots'
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    as_of_date = Column(Date, nullable=False, index=True)
    period_type = Column(String, nullable=False, default="TTM")
    fiscal_period_end = Column(Date)
    snapshot_data = Column(JSON, nullable=False)
    calculation_version = Column(String, default="v1")
    data_quality_score = Column(Float)
    is_current = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint('symbol', 'as_of_date', 'period_type',
                         name='uq_snapshot_symbol_date'),
    )


class CorporateAction(Base, TimestampMixin):
    """Corporate actions affecting share counts and adjusted prices."""
    __tablename__ = 'corporate_actions'
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    action_date = Column(Date, nullable=False, index=True)
    action_type = Column(String, nullable=False)
    # STOCK_SPLIT, STOCK_DIVIDEND, RIGHTS_ISSUE, BUYBACK, CASH_DIVIDEND
    ratio = Column(Float)
    value = Column(Numeric(30, 6))
    currency = Column(String)
    record_date = Column(Date)
    ex_date = Column(Date)
    payment_date = Column(Date)
    source = Column(String)
    notes = Column(Text)

    __table_args__ = (
        Index('ix_corporate_action_symbol_date', 'symbol', 'action_date'),
    )


class QualityFlag(Base, TimestampMixin):
    """Quality/warning flags per company per period."""
    __tablename__ = 'quality_flags'
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    fiscal_period_end = Column(Date, nullable=False)
    flag_type = Column(String, nullable=False)
    # HighDebt, CashFlowDivergence, MarginCompression, ReceivableGrowth,
    # InventoryBuild, EarningsConcentration, OneOffProfit, NegativeFCF,
    # ROEDecline, NegativeEquity, RevenueAcceleration, EarningsAcceleration
    severity = Column(String, default="WARNING")  # INFO, WARNING, ALERT
    description = Column(Text)
    evidence = Column(JSON)
    auto_generated = Column(Boolean, default=True)
    calculation_version = Column(String)

    __table_args__ = (
        UniqueConstraint('symbol', 'fiscal_period_end', 'flag_type',
                         name='uq_flag_symbol_period_type'),
    )


class PeerGroup(Base, TimestampMixin):
    """Peer group definition for sector benchmarking."""
    __tablename__ = 'peer_groups'
    id = Column(Integer, primary_key=True, index=True)
    peer_group_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    sector = Column(String)
    industry = Column(String)
    market_cap_band = Column(String)  # LARGE, MID, SMALL
    country = Column(String, default="VN")
    members = Column(JSON)  # list of symbols


class FormulaRegistry(Base, TimestampMixin):
    """Registry of all metric formulas with versioning."""
    __tablename__ = 'formula_registry'
    id = Column(Integer, primary_key=True, index=True)
    metric_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    name_vi = Column(String)
    formula = Column(Text, nullable=False)
    description = Column(Text)
    description_vi = Column(Text)
    scope = Column(String, default="GENERAL")
    sector = Column(String)
    unit = Column(String)
    version = Column(String, nullable=False)
    is_current = Column(Boolean, default=True)
    caveats = Column(Text)
    example = Column(Text)

    __table_args__ = (
        UniqueConstraint('metric_id', 'version', name='uq_formula_metric_version'),
    )


# ─────────────────────────────────────────────────────────
# PHASE 1: INDEX MEMBERSHIP, STAGING, EVENTS & DATA QUALITY
# ─────────────────────────────────────────────────────────

class IndexMembership(Base, TimestampMixin):
    """
    Historical index constituents for point-in-time index reconstruction.
    Allows querying: Was symbol X a member of index Y at time T?
    """
    __tablename__ = 'index_memberships'
    id = Column(Integer, primary_key=True, index=True)
    index_symbol = Column(String, nullable=False, index=True) # e.g. VN30, VN100
    symbol = Column(String, nullable=False, index=True)       # e.g. FPT, VCB
    start_date = Column(Date, nullable=False, index=True)     # Inclusion date
    end_date = Column(Date, nullable=True, index=True)        # Exclusion date (NULL if currently active)
    weight = Column(Float, nullable=True)                     # Weight in index (0.0 to 1.0)
    source_id = Column(Integer, ForeignKey('data_sources.id'), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index('ix_index_membership_query', 'index_symbol', 'symbol', 'start_date', 'end_date'),
    )


class StagingRecord(Base, TimestampMixin):
    """
    Intermediate staging table for Raw -> Staging -> Validation -> Canonical pipeline.
    All incoming raw records land here before canonical promotion.
    """
    __tablename__ = 'staging_records'
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, ForeignKey('data_runs.run_id'), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey('data_sources.id'), nullable=True)
    provider = Column(String, nullable=False, index=True)
    dataset = Column(String, nullable=False)
    raw_payload = Column(JSON, nullable=False)
    status = Column(String, default="PENDING", index=True) # PENDING, VALIDATED, REJECTED, PROMOTED
    validation_errors = Column(JSON, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    observed_period = Column(String, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)


class EventRecord(Base, TimestampMixin):
    """
    Canonical news, regulatory, corporate, or geopolitical events.
    """
    __tablename__ = 'events'
    id = Column(String, primary_key=True, index=True) # e.g. evt-2026-001
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    event_type = Column(String, nullable=False, index=True) # Macro, Earnings, Regulation, Geopolitical
    materiality = Column(String, default="INFORMATIONAL") # INFORMATIONAL, RELEVANT, MATERIAL, CRITICAL
    severity = Column(Float, default=50.0) # 0 to 100
    sentiment = Column(String, default="NEUTRAL") # POSITIVE, NEGATIVE, NEUTRAL, MIXED, UNCLEAR
    countries = Column(JSON, default=list)
    affected_sectors = Column(JSON, default=list)
    impacts = Column(JSON, default=list)
    sources = Column(JSON, default=list)
    source_id = Column(Integer, ForeignKey('data_sources.id'), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=True)
    effective_at = Column(DateTime(timezone=True), nullable=True)
    as_of_date = Column(Date, nullable=True, index=True)


class DataQualityReportRecord(Base, TimestampMixin):
    """
    Structured data quality assessment for each ingestion run.
    """
    __tablename__ = 'data_quality_reports'
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, ForeignKey('data_runs.run_id'), nullable=False, index=True)
    provider = Column(String, nullable=False)
    dataset = Column(String, nullable=False)
    as_of_date = Column(Date, nullable=False)
    completeness_score = Column(Float, default=1.0) # 0.0 to 1.0
    freshness_score = Column(Float, default=1.0)    # 0.0 to 1.0
    duplicates_count = Column(Integer, default=0)
    anomalies_count = Column(Integer, default=0)
    impossible_values_count = Column(Integer, default=0)
    summary = Column(JSON, default=dict)
    status = Column(String, default="PASSED") # PASSED, WARNING, FAILED


# ─────────────────────────────────────────────────────────
# PHASE 6D: LOCAL PERSONAL PORTFOLIO & WATCHLIST
# ─────────────────────────────────────────────────────────

class PersonalPortfolio(Base, TimestampMixin):
    __tablename__ = "personal_portfolios"
    id = Column(String, primary_key=True, default="personal")
    name = Column(String, nullable=False, default="Personal Portfolio")
    base_currency = Column(String, nullable=False, default="VND")
    single_name_limit = Column(Numeric(8, 6), nullable=True)
    sector_limit = Column(Numeric(8, 6), nullable=True)
    material_change_threshold = Column(Numeric(8, 6), nullable=True)
    core_target = Column(Numeric(8, 6), nullable=True)
    satellite_target = Column(Numeric(8, 6), nullable=True)
    __table_args__ = (
        CheckConstraint("single_name_limit IS NULL OR (single_name_limit >= 0 AND single_name_limit <= 1)", name="single_name_limit_range"),
        CheckConstraint("sector_limit IS NULL OR (sector_limit >= 0 AND sector_limit <= 1)", name="sector_limit_range"),
        CheckConstraint("material_change_threshold IS NULL OR (material_change_threshold >= 0 AND material_change_threshold <= 1)", name="material_change_threshold_range"),
        CheckConstraint("core_target IS NULL OR (core_target >= 0 AND core_target <= 1)", name="core_target_range"),
        CheckConstraint("satellite_target IS NULL OR (satellite_target >= 0 AND satellite_target <= 1)", name="satellite_target_range"),
    )


class PortfolioHolding(Base, TimestampMixin):
    __tablename__ = "portfolio_holdings"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(String, ForeignKey("personal_portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    quantity = Column(Numeric(28, 8), nullable=False)
    average_cost = Column(Numeric(20, 6), nullable=False)
    acquisition_date = Column(Date, nullable=False)
    role = Column(String, nullable=False, default="UNASSIGNED")
    horizon = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    __table_args__ = (
        UniqueConstraint("portfolio_id", "asset_id", name="uq_portfolio_holding_asset"),
        CheckConstraint("quantity > 0", name="holding_quantity_positive"),
        CheckConstraint("average_cost > 0", name="holding_average_cost_positive"),
        CheckConstraint("role IN ('CORE', 'SATELLITE', 'UNASSIGNED')", name="holding_role_valid"),
        CheckConstraint("horizon IS NULL OR horizon IN ('MEDIUM_TERM', 'LONG_TERM')", name="holding_horizon_valid"),
    )


class ManualPortfolioTransaction(Base, TimestampMixin):
    __tablename__ = "manual_portfolio_transactions"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(String, ForeignKey("personal_portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    transaction_type = Column(String, nullable=False)
    quantity = Column(Numeric(28, 8), nullable=False)
    unit_price = Column(Numeric(20, 6), nullable=False)
    transaction_date = Column(Date, nullable=False)
    entry_source = Column(String, nullable=False, default="MANUAL")
    notes = Column(Text, nullable=True)
    __table_args__ = (
        CheckConstraint("transaction_type IN ('BUY', 'SELL', 'DIVIDEND', 'FEE')", name="manual_transaction_type_valid"),
        CheckConstraint("quantity > 0", name="manual_transaction_quantity_positive"),
        CheckConstraint("unit_price > 0", name="manual_transaction_price_positive"),
        CheckConstraint("entry_source = 'MANUAL'", name="manual_transaction_source_only"),
    )


class PortfolioTarget(Base, TimestampMixin):
    __tablename__ = "portfolio_targets"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(String, ForeignKey("personal_portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    target_weight = Column(Numeric(8, 6), nullable=False)
    __table_args__ = (
        UniqueConstraint("portfolio_id", "asset_id", name="uq_portfolio_target_asset"),
        CheckConstraint("target_weight >= 0 AND target_weight <= 1", name="portfolio_target_weight_range"),
    )


class DcaPlan(Base, TimestampMixin):
    __tablename__ = "personal_dca_plans"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(String, ForeignKey("personal_portfolios.id", ondelete="CASCADE"), nullable=False, unique=True)
    monthly_amount = Column(Integer, nullable=False, default=350000)
    core_pct = Column(Numeric(8, 6), nullable=False, default=0.75)
    satellite_pct = Column(Numeric(8, 6), nullable=False, default=0.25)
    __table_args__ = (
        CheckConstraint("monthly_amount >= 300000 AND monthly_amount <= 400000", name="dca_monthly_amount_range"),
        CheckConstraint("core_pct >= 0 AND core_pct <= 1", name="dca_core_pct_range"),
        CheckConstraint("satellite_pct >= 0 AND satellite_pct <= 1", name="dca_satellite_pct_range"),
        CheckConstraint("core_pct + satellite_pct <= 1", name="dca_reserve_nonnegative"),
    )


class PersonalPortfolioSnapshot(Base):
    __tablename__ = "personal_portfolio_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(String, ForeignKey("personal_portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    snapshot_data = Column(JSON, nullable=False)


class WatchlistItem(Base, TimestampMixin):
    __tablename__ = "watchlist_items"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, unique=True)
    thesis = Column(Text, nullable=True)
    horizon = Column(String, nullable=True)
    invalidation = Column(Text, nullable=True)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    last_changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        CheckConstraint("horizon IS NULL OR horizon IN ('MEDIUM_TERM', 'LONG_TERM')", name="watchlist_horizon_valid"),
    )


class WatchlistThesisRevision(Base):
    __tablename__ = "watchlist_thesis_revisions"
    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist_items.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_thesis = Column(Text, nullable=True)
    new_thesis = Column(Text, nullable=True)
    change_reason = Column(Text, nullable=False)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WatchlistSnapshot(Base):
    __tablename__ = "watchlist_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlist_items.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    snapshot_data = Column(JSON, nullable=False)


class AssetDecisionSnapshot(Base):
    __tablename__ = "asset_decision_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    captured_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    snapshot_data = Column(JSON, nullable=False)


class AnalystBrief(Base):
    __tablename__ = "analyst_briefs"
    id = Column(Integer, primary_key=True, index=True)
    brief_type = Column(String, nullable=False, index=True)
    as_of_date = Column(Date, nullable=False, index=True)
    status = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    idempotency_key = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AnalystAutomationJob(Base):
    __tablename__ = "analyst_automation_jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_key = Column(String, nullable=False, unique=True)
    job_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)


class AnalystAlert(Base):
    __tablename__ = "analyst_alerts"
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String, nullable=False, unique=True)
    symbol = Column(String, nullable=True, index=True)
    kind = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="OPEN")
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

